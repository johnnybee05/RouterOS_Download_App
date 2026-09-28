"""Stahování balíčků: .part soubory, souběžnost, opakování, ověření SHA256."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Collection, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock

import httpx

from .client import MikrotikClient
from .errors import (
    Cancelled,
    ChecksumMismatch,
    NetworkError,
    NotFoundError,
    PackageNotAvailableError,
    RosdlError,
    SizeMismatch,
)
from .http import BACKOFF, DEFAULT_ATTEMPTS, CancelToken, Http
from .models import RemoteFile
from .util import sha256_file

MAX_PARALLEL_DOWNLOADS = 3
CHUNK_SIZE = 256 * 1024
PART_SUFFIX = ".part"


class Status(str, Enum):
    PENDING = "pending"
    VERIFYING = "verifying"
    DOWNLOADING = "downloading"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DownloadTask:
    remote: RemoteFile
    dest: Path

    @property
    def part_path(self) -> Path:
        return self.dest.with_name(self.dest.name + PART_SUFFIX)


@dataclass
class FileResult:
    task: DownloadTask
    status: Status
    downloaded: int = 0
    total: int | None = None
    error: str | None = None
    sha256: str | None = None


@dataclass
class Report:
    results: list[FileResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(
            r.status in (Status.DONE, Status.SKIPPED) for r in self.results
        )

    def count(self, status: Status) -> int:
        return sum(1 for r in self.results if r.status is status)


class Listener:
    """Odběratel průběhu. GUI i CLI si podědí jen to, co potřebují."""

    def on_log(self, level: str, message: str) -> None: ...

    def on_file_status(self, task: DownloadTask, status: Status) -> None: ...

    def on_file_progress(
        self, task: DownloadTask, downloaded: int, total: int | None, speed: float
    ) -> None: ...

    def on_file_finished(self, result: FileResult) -> None: ...

    def on_total_progress(self, downloaded: int, total: int | None) -> None: ...


class _SpeedMeter:
    """Klouzavý průměr rychlosti za poslední ~3 s."""

    WINDOW = 3.0

    def __init__(self) -> None:
        self._samples: list[tuple[float, int]] = []

    def add(self, nbytes: int) -> float:
        now = time.monotonic()
        self._samples.append((now, nbytes))
        cutoff = now - self.WINDOW
        while len(self._samples) > 2 and self._samples[0][0] < cutoff:
            self._samples.pop(0)
        if len(self._samples) < 2:
            return 0.0
        span = self._samples[-1][0] - self._samples[0][0]
        if span <= 0:
            return 0.0
        return sum(n for _, n in self._samples[1:]) / span


class Downloader:
    def __init__(
        self,
        client: MikrotikClient,
        *,
        max_workers: int = MAX_PARALLEL_DOWNLOADS,
        verify_sha256: bool = True,
        attempts: int = DEFAULT_ATTEMPTS,
    ) -> None:
        self.client = client
        self.http: Http = client.http
        self.max_workers = max(1, max_workers)
        self.verify_sha256 = verify_sha256
        self.attempts = max(1, attempts)
        self._lock = Lock()
        self._total_done = 0
        self._total_size: int | None = None

    # ------------------------------------------------------------------ #
    def run(
        self,
        tasks: Sequence[DownloadTask],
        listener: Listener | None = None,
        token: CancelToken | None = None,
    ) -> Report:
        listener = listener or Listener()
        token = token or CancelToken()
        report = Report()

        self._total_done = 0
        self._total_size = _sum_known_sizes(tasks)

        workers = min(self.max_workers, len(tasks)) or 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(
                lambda t: self._run_one(t, listener, token), tasks
            ):
                report.results.append(result)
                listener.on_file_finished(result)
        return report

    # ------------------------------------------------------------------ #
    def _run_one(
        self, task: DownloadTask, listener: Listener, token: CancelToken
    ) -> FileResult:
        try:
            return self._download(task, listener, token)
        except Cancelled:
            listener.on_file_status(task, Status.CANCELLED)
            return FileResult(task=task, status=Status.CANCELLED)
        except NotFoundError as exc:
            message = str(
                PackageNotAvailableError(
                    task.remote.package or task.remote.name,
                    task.remote.version,
                    task.remote.arch,
                    exc.url,
                )
            )
            listener.on_log("error", message)
            listener.on_file_status(task, Status.FAILED)
            return FileResult(task=task, status=Status.FAILED, error=message)
        except RosdlError as exc:
            listener.on_log("error", f"{task.remote.name}: {exc}")
            listener.on_file_status(task, Status.FAILED)
            return FileResult(task=task, status=Status.FAILED, error=str(exc))
        except OSError as exc:
            message = f"Chyba zápisu do {task.dest}: {exc}"
            listener.on_log("error", message)
            listener.on_file_status(task, Status.FAILED)
            return FileResult(task=task, status=Status.FAILED, error=message)

    def _download(
        self, task: DownloadTask, listener: Listener, token: CancelToken
    ) -> FileResult:
        token.raise_if_cancelled()
        task.dest.parent.mkdir(parents=True, exist_ok=True)

        expected_sha = (
            self.client.fetch_sha256(task.remote, token=token)
            if self.verify_sha256
            else None
        )
        head = self.http.head(task.remote.url, token=token)
        if not head.ok:
            raise NotFoundError(task.remote.url)
        total = head.size if head.size is not None else task.remote.size

        # 1) Už tu soubor je a je v pořádku? Pak se nestahuje znovu.
        if task.dest.exists():
            listener.on_file_status(task, Status.VERIFYING)
            if self._already_good(task, total, expected_sha, token):
                listener.on_log("info", f"{task.remote.name}: už staženo, přeskočeno")
                listener.on_file_status(task, Status.SKIPPED)
                self._advance_total(total or 0, listener)
                return FileResult(
                    task=task, status=Status.SKIPPED, downloaded=total or 0, total=total
                )
            listener.on_log(
                "warning",
                f"{task.remote.name}: existující soubor nesouhlasí, stahuje se znovu",
            )

        # 2) Stažení (s pokusem o navázání na .part).
        listener.on_file_status(task, Status.DOWNLOADING)
        digest = self._stream_with_retries(
            task, total, head.accept_ranges, listener, token
        )

        actual_size = task.part_path.stat().st_size
        if total is not None and actual_size != total:
            task.part_path.unlink(missing_ok=True)
            raise SizeMismatch(task.dest.name, total, actual_size)

        actual_sha = digest.hexdigest() if digest is not None else None
        if expected_sha is not None:
            if actual_sha is None:
                actual_sha = sha256_file(
                    task.part_path, should_cancel=lambda: token.cancelled
                )
                if actual_sha is None:
                    raise Cancelled("Operace byla zrušena.")
            if actual_sha != expected_sha:
                task.part_path.unlink(missing_ok=True)
                raise ChecksumMismatch(task.dest.name, expected_sha, actual_sha)
            listener.on_log("info", f"{task.remote.name}: SHA256 ověřeno")
        elif total is not None:
            listener.on_log(
                "info",
                f"{task.remote.name}: SHA256 není k dispozici, ověřena velikost",
            )

        task.dest.unlink(missing_ok=True)
        task.part_path.replace(task.dest)
        listener.on_file_status(task, Status.DONE)
        return FileResult(
            task=task,
            status=Status.DONE,
            downloaded=actual_size,
            total=total,
            sha256=actual_sha,
        )

    # ------------------------------------------------------------------ #
    def _already_good(
        self,
        task: DownloadTask,
        total: int | None,
        expected_sha: str | None,
        token: CancelToken,
    ) -> bool:
        size = task.dest.stat().st_size
        if total is not None and size != total:
            return False
        if expected_sha is None:
            return total is not None
        actual = sha256_file(task.dest, should_cancel=lambda: token.cancelled)
        if actual is None:
            raise Cancelled("Operace byla zrušena.")
        return actual == expected_sha

    def _stream_with_retries(
        self,
        task: DownloadTask,
        total: int | None,
        accept_ranges: bool,
        listener: Listener,
        token: CancelToken,
    ) -> "hashlib._Hash | None":
        """Opakuje stahování, když spojení spadne uprostřed přenosu.

        ``Http`` opakuje jen samotný požadavek. Spadlé spojení během čtení
        těla je jiný případ – bez tohohle by výpadek Wi-Fi v půlce
        padesátimegového archivu shodil celou dávku. Díky ``.part`` se
        navazuje tam, kde přenos skončil.
        """
        last: NetworkError | None = None
        for attempt in range(self.attempts):
            token.raise_if_cancelled()
            if attempt:
                listener.on_log(
                    "warning",
                    f"{task.remote.name}: spojení přerušeno, pokus "
                    f"{attempt + 1} z {self.attempts}",
                )
                if token.wait(BACKOFF[min(attempt - 1, len(BACKOFF) - 1)]):
                    raise Cancelled("Operace byla zrušena.")
            try:
                return self._stream_to_part(
                    task, total, accept_ranges, listener, token
                )
            except NetworkError as exc:
                last = exc
        raise last if last is not None else NetworkError(task.remote.url)

    def _stream_to_part(
        self,
        task: DownloadTask,
        total: int | None,
        accept_ranges: bool,
        listener: Listener,
        token: CancelToken,
    ) -> "hashlib._Hash | None":
        """Stáhne do .part. Vrací průběžný hash, nebo None když navazoval."""
        part = task.part_path
        resume_from = 0
        digest: "hashlib._Hash | None" = hashlib.sha256()

        if part.exists():
            existing = part.stat().st_size
            if accept_ranges and total is not None and 0 < existing < total:
                resume_from = existing
                # Hash od začátku nemáme, spočítá se až na konci ze souboru.
                digest = None
                listener.on_log(
                    "info",
                    f"{task.remote.name}: navazuji na rozdělané stahování "
                    f"({existing} B)",
                )
            else:
                part.unlink(missing_ok=True)

        headers = {"Range": f"bytes={resume_from}-"} if resume_from else None
        meter = _SpeedMeter()
        downloaded = resume_from
        mode = "ab" if resume_from else "wb"

        resp = self.http.stream_get(task.remote.url, headers=headers, token=token)
        try:
            if resume_from and resp.status_code != 206:
                # Server Range odmítl – začínáme znovu od nuly.
                resume_from = 0
                downloaded = 0
                mode = "wb"
                digest = hashlib.sha256()
            self._advance_total(resume_from, listener)

            with part.open(mode) as fh:
                for chunk in resp.iter_bytes(CHUNK_SIZE):
                    if token.cancelled:
                        fh.flush()
                        raise Cancelled("Operace byla zrušena.")
                    fh.write(chunk)
                    if digest is not None:
                        digest.update(chunk)
                    downloaded += len(chunk)
                    speed = meter.add(len(chunk))
                    listener.on_file_progress(task, downloaded, total, speed)
                    self._advance_total(len(chunk), listener)
        except httpx.HTTPError as exc:
            # Pád spojení během čtení těla odpovědi neprochází přes
            # Http.request, takže by jinak probublal jako cizí výjimka
            # a shodil celou dávku místo jednoho souboru.
            raise NetworkError(
                f"Přenos {task.remote.name} byl přerušen: {exc}"
            ) from exc
        finally:
            resp.close()
        return digest

    def _advance_total(self, delta: int, listener: Listener) -> None:
        if delta <= 0:
            return
        with self._lock:
            self._total_done += delta
            done, total = self._total_done, self._total_size
        listener.on_total_progress(done, total)


def _sum_known_sizes(tasks: Sequence[DownloadTask]) -> int | None:
    sizes = [t.remote.size for t in tasks]
    if any(s is None for s in sizes):
        return None
    return sum(s for s in sizes if s is not None)


def cleanup_partials(
    directory: Path,
    *,
    recursive: bool = True,
    keep: Collection[Path] = (),
) -> list[Path]:
    """Smaže osiřelé ``.part`` soubory po zrušeném běhu.

    ``keep`` vyjme ty, na které se právě chystáme navázat – ty se dopočítají
    přes Range místo stahování od nuly.
    """
    if not directory.exists():
        return []
    keep_resolved = {p.resolve() for p in keep}
    pattern = f"**/*{PART_SUFFIX}" if recursive else f"*{PART_SUFFIX}"
    removed: list[Path] = []
    for path in directory.glob(pattern):
        if path.resolve() in keep_resolved:
            continue
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed


def plan_destination(
    root: Path, remote: RemoteFile, *, per_version: bool, per_arch: bool
) -> Path:
    """Sestaví cílovou cestu podle volby ``<cíl>/<verze>/<arch>/``."""
    path = root
    if per_version:
        path = path / str(remote.version)
    if per_arch:
        path = path / remote.arch
    return path / remote.name


def build_tasks(
    root: Path,
    remotes: Sequence[RemoteFile],
    *,
    per_version: bool = False,
    per_arch: bool = False,
) -> list[DownloadTask]:
    return [
        DownloadTask(
            remote=r,
            dest=plan_destination(
                root, r, per_version=per_version, per_arch=per_arch
            ),
        )
        for r in remotes
    ]


#: Typová nápověda pro volající, kteří chtějí jen jednoduchý callback.
ProgressCallback = Callable[[int, int | None], None]
