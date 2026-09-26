"""Stahování: .part soubory, přeskakování, ověření, zrušení, opakování."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rosdl.core import urls
from rosdl.core.cache import JsonCache
from rosdl.core.client import MikrotikClient
from rosdl.core.downloader import (
    Downloader,
    Listener,
    Status,
    build_tasks,
    cleanup_partials,
    plan_destination,
)
from rosdl.core.http import CancelToken
from rosdl.core.models import Version

from .conftest import FakeServer

V7 = Version.parse("7.24.4")
MAIN = b"ROUTEROS-MAIN" * 500
EXTRA = b"CONTAINER" * 300


class Recorder(Listener):
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []
        self.statuses: list[tuple[str, Status]] = []
        self.progress: list[tuple[str, int, int | None]] = []
        self.totals: list[tuple[int, int | None]] = []

    def on_log(self, level: str, message: str) -> None:
        self.logs.append((level, message))

    def on_file_status(self, task, status) -> None:  # noqa: ANN001
        self.statuses.append((task.remote.name, status))

    def on_file_progress(self, task, downloaded, total, speed) -> None:  # noqa: ANN001
        self.progress.append((task.remote.name, downloaded, total))

    def on_total_progress(self, downloaded, total) -> None:  # noqa: ANN001
        self.totals.append((downloaded, total))

    def messages(self, level: str) -> list[str]:
        return [m for lvl, m in self.logs if lvl == level]


@pytest.fixture
def client(server: FakeServer, tmp_path: Path) -> MikrotikClient:
    return MikrotikClient(
        server.http(),
        versions_cache=JsonCache("v.json", 3600, directory=tmp_path),
        packages_cache=JsonCache("p.json", 3600, directory=tmp_path),
    )


@pytest.fixture
def main_url() -> str:
    return urls.file_url(V7, "routeros-7.24.4-arm64.npk")


# --------------------------------------------------------------------------- #
# Základní běh
# --------------------------------------------------------------------------- #
def test_downloads_and_verifies_sha256(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    digest = server.add_with_sha256(main_url, MAIN)
    tasks = build_tasks(tmp_path, [client.main_file(V7, "arm64")])
    recorder = Recorder()

    report = Downloader(client).run(tasks, recorder)

    assert report.ok
    assert report.results[0].status is Status.DONE
    assert report.results[0].sha256 == digest
    dest = tmp_path / "routeros-7.24.4-arm64.npk"
    assert dest.read_bytes() == MAIN
    assert not list(tmp_path.glob("*.part"))
    assert any("SHA256 ověřeno" in m for m in recorder.messages("info"))


def test_downloads_without_sha256_checks_size(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add(main_url, MAIN)  # bez .sha256 sidecaru
    recorder = Recorder()

    report = Downloader(client).run(
        build_tasks(tmp_path, [client.main_file(V7, "arm64")]), recorder
    )

    assert report.ok
    assert (tmp_path / "routeros-7.24.4-arm64.npk").stat().st_size == len(MAIN)
    assert any("ověřena velikost" in m for m in recorder.messages("info"))


def test_subfolder_layout(client: MikrotikClient, tmp_path: Path) -> None:
    remote = client.main_file(V7, "arm64")
    dest = plan_destination(tmp_path, remote, per_version=True, per_arch=True)
    assert dest == tmp_path / "7.24.4" / "arm64" / "routeros-7.24.4-arm64.npk"

    flat = plan_destination(tmp_path, remote, per_version=False, per_arch=False)
    assert flat == tmp_path / "routeros-7.24.4-arm64.npk"


def test_parallel_downloads(
    server: FakeServer, client: MikrotikClient, tmp_path: Path
) -> None:
    remotes = []
    for arch in ("arm", "arm64", "mipsbe", "x86"):
        remote = client.main_file(V7, arch)
        server.add_with_sha256(remote.url, MAIN + arch.encode())
        remotes.append(remote)

    report = Downloader(client, max_workers=3).run(build_tasks(tmp_path, remotes))

    assert report.count(Status.DONE) == 4
    assert len(list(tmp_path.glob("*.npk"))) == 4


# --------------------------------------------------------------------------- #
# Přeskakování existujících souborů
# --------------------------------------------------------------------------- #
def test_skips_file_with_matching_hash(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add_with_sha256(main_url, MAIN)
    dest = tmp_path / "routeros-7.24.4-arm64.npk"
    dest.write_bytes(MAIN)

    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))

    assert report.results[0].status is Status.SKIPPED


def test_redownloads_file_with_wrong_hash(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    """Soubor správné velikosti, ale jiného obsahu, se musí stáhnout znovu."""
    server.add_with_sha256(main_url, MAIN)
    dest = tmp_path / "routeros-7.24.4-arm64.npk"
    dest.write_bytes(b"X" * len(MAIN))
    recorder = Recorder()

    report = Downloader(client).run(
        build_tasks(tmp_path, [client.main_file(V7, "arm64")]), recorder
    )

    assert report.results[0].status is Status.DONE
    assert dest.read_bytes() == MAIN
    assert any("nesouhlasí" in m for m in recorder.messages("warning"))


def test_redownloads_file_with_wrong_size(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add(main_url, MAIN)
    dest = tmp_path / "routeros-7.24.4-arm64.npk"
    dest.write_bytes(b"short")

    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))

    assert report.results[0].status is Status.DONE
    assert dest.read_bytes() == MAIN


# --------------------------------------------------------------------------- #
# Chyby
# --------------------------------------------------------------------------- #
def test_missing_package_gives_czech_message(
    client: MikrotikClient, tmp_path: Path
) -> None:
    """404 se musí přeložit na hlášku o neexistujícím balíčku, ne na stack trace."""
    entry_remote = client.main_file(V7, "arm64")
    recorder = Recorder()

    report = Downloader(client).run(build_tasks(tmp_path, [entry_remote]), recorder)

    assert report.results[0].status is Status.FAILED
    message = report.results[0].error or ""
    assert "neexistuje" in message
    assert "arm64" in message and "7.24.4" in message
    assert not list(tmp_path.glob("*"))


def test_checksum_mismatch_removes_part_file(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add(main_url, MAIN)
    server.add(main_url + ".sha256", f"{'0' * 64}  routeros-7.24.4-arm64.npk\n")

    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))

    assert report.results[0].status is Status.FAILED
    assert "součet nesouhlasí" in (report.results[0].error or "")
    assert not list(tmp_path.glob("*")), "po neúspěchu nesmí zůstat žádný soubor"


def test_retries_transient_failures(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add_with_sha256(main_url, MAIN)
    server.fail_times[main_url] = 2  # dvakrát 503, napotřetí projde

    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))

    assert report.ok
    assert (tmp_path / "routeros-7.24.4-arm64.npk").read_bytes() == MAIN


def test_gives_up_after_three_attempts(
    server: FakeServer, tmp_path: Path, main_url: str
) -> None:
    server = server
    server.add_with_sha256(main_url, MAIN)
    server.fail_times[main_url] = 99
    client = MikrotikClient(
        server.http(),
        versions_cache=JsonCache("v.json", 3600, directory=tmp_path),
        packages_cache=JsonCache("p.json", 3600, directory=tmp_path),
    )

    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))

    assert report.results[0].status is Status.FAILED
    assert not list(tmp_path.glob("*"))


# --------------------------------------------------------------------------- #
# Zrušení a .part soubory
# --------------------------------------------------------------------------- #
def test_cancel_leaves_only_part_file(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add_with_sha256(main_url, MAIN)
    token = CancelToken()
    token.cancel()

    report = Downloader(client).run(
        build_tasks(tmp_path, [client.main_file(V7, "arm64")]), token=token
    )

    assert report.results[0].status is Status.CANCELLED
    assert not list(tmp_path.glob("*.npk")), "hotový soubor nesmí vzniknout"


def test_cleanup_partials(tmp_path: Path) -> None:
    (tmp_path / "7.24.4" / "arm64").mkdir(parents=True)
    keep = tmp_path / "7.24.4" / "arm64" / "routeros-7.24.4-arm64.npk"
    keep.write_bytes(b"ok")
    part = tmp_path / "7.24.4" / "arm64" / "container-7.24.4-arm64.npk.part"
    part.write_bytes(b"half")

    removed = cleanup_partials(tmp_path)

    assert removed == [part]
    assert keep.exists()
    assert not part.exists()


def test_cleanup_partials_on_missing_dir(tmp_path: Path) -> None:
    assert cleanup_partials(tmp_path / "neexistuje") == []


def test_resumes_from_part_file(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    """Rozdělané .part se dopočítá přes Range místo stažení od nuly."""
    server.add_with_sha256(main_url, MAIN)
    part = tmp_path / "routeros-7.24.4-arm64.npk.part"
    part.write_bytes(MAIN[:1000])
    recorder = Recorder()

    report = Downloader(client).run(
        build_tasks(tmp_path, [client.main_file(V7, "arm64")]), recorder
    )

    assert report.ok
    assert (tmp_path / "routeros-7.24.4-arm64.npk").read_bytes() == MAIN
    assert any("navazuji" in m for m in recorder.messages("info"))
    ranged = [r for r in server.requests if r.headers.get("Range") == "bytes=1000-"]
    assert ranged, "měl proběhnout Range požadavek od 1000. bajtu"


def test_corrupt_part_file_is_detected_by_hash(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    """Navázání na poškozený .part musí spadnout na kontrole SHA256."""
    server.add_with_sha256(main_url, MAIN)
    part = tmp_path / "routeros-7.24.4-arm64.npk.part"
    part.write_bytes(b"Z" * 1000)

    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))

    assert report.results[0].status is Status.FAILED
    assert not part.exists()


def test_part_restarted_when_server_refuses_range(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add_with_sha256(main_url, MAIN)
    server.support_ranges = False
    (tmp_path / "routeros-7.24.4-arm64.npk.part").write_bytes(MAIN[:1000])

    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))

    assert report.ok
    assert (tmp_path / "routeros-7.24.4-arm64.npk").read_bytes() == MAIN


# --------------------------------------------------------------------------- #
# Průběh
# --------------------------------------------------------------------------- #
def test_progress_reaches_total(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add_with_sha256(main_url, MAIN)
    remote = client.main_file(V7, "arm64")
    remotes = client.fill_sizes([remote])
    recorder = Recorder()

    Downloader(client).run(build_tasks(tmp_path, remotes), recorder)

    assert recorder.totals[-1] == (len(MAIN), len(MAIN))
    assert recorder.progress[-1] == (remote.name, len(MAIN), len(MAIN))


def test_sha256_of_downloaded_file_matches_sidecar(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    server.add_with_sha256(main_url, MAIN)
    report = Downloader(client).run(build_tasks(tmp_path, [client.main_file(V7, "arm64")]))
    dest = tmp_path / "routeros-7.24.4-arm64.npk"
    assert report.results[0].sha256 == hashlib.sha256(dest.read_bytes()).hexdigest()


def test_cleanup_partials_keeps_resumable(tmp_path: Path) -> None:
    """``.part`` souborů, na které se chystáme navázat, se úklid nesmí dotknout."""
    keep = tmp_path / "routeros-7.24.4-arm64.npk.part"
    keep.write_bytes(b"half")
    orphan = tmp_path / "stary-7.20.1-arm.npk.part"
    orphan.write_bytes(b"junk")

    removed = cleanup_partials(tmp_path, keep=[keep])

    assert removed == [orphan]
    assert keep.exists()
    assert not orphan.exists()


def test_resume_after_cancel_produces_correct_file(
    server: FakeServer, client: MikrotikClient, tmp_path: Path, main_url: str
) -> None:
    """Zrušení, úklid osiřelých .part, navázání – výsledek musí sedět na hash."""
    server.add_with_sha256(main_url, MAIN)
    tasks = build_tasks(tmp_path, [client.main_file(V7, "arm64")])

    cancelled = CancelToken()
    cancelled.cancel()
    first = Downloader(client).run(tasks, token=cancelled)
    assert first.results[0].status is Status.CANCELLED

    # Simulace přerušení v půlce: .part s částí dat.
    tasks[0].part_path.write_bytes(MAIN[: len(MAIN) // 2])
    cleanup_partials(tmp_path, keep=[t.part_path for t in tasks])
    assert tasks[0].part_path.exists()

    second = Downloader(client).run(tasks)
    assert second.ok
    assert tasks[0].dest.read_bytes() == MAIN
    assert not tasks[0].part_path.exists()
