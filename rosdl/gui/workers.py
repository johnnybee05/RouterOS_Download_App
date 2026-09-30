"""Vlákna na pozadí. Veškerá síťová komunikace běží tady, nikdy v GUI vlákně."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..i18n import t
from ..core import (
    ArchPackages,
    CancelToken,
    ChangelogInfo,
    Cancelled,
    Channel,
    Downloader,
    Http,
    Listener,
    MikrotikClient,
    ReleaseInfo,
    RemoteFile,
    Report,
    RosdlError,
    Status,
    Version,
    check_for_update,
    download_update,
)
from ..core.client import filter_for_channel
from ..core.downloader import DownloadTask


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)  # hotovo, celkem
    log = Signal(str, str)  # úroveň, zpráva


class Worker(QRunnable):
    """Spustí funkci na pozadí a výsledek pošle signálem do GUI vlákna."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.signals = WorkerSignals()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.token = CancelToken()

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Cancelled:
            return
        except RosdlError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - do GUI nesmí probublat traceback
            self.signals.failed.emit(t("worker.unexpected", detail=exc))
        else:
            self.signals.finished.emit(result)

    def cancel(self) -> None:
        self.token.cancel()


# --------------------------------------------------------------------------- #
class NewestWorker(Worker):
    """Zjistí nejnovější verzi kanálu. Volá se hned po startu aplikace."""

    def __init__(self, client: MikrotikClient, major: int, channel: Channel) -> None:
        super().__init__(self._work, client, major, channel)

    def _work(
        self, client: MikrotikClient, major: int, channel: Channel
    ) -> Any:
        return client.newest(major, channel, token=self.token)


class VersionsWorker(Worker):
    """Dohledá historii verzí. Běží na pozadí, GUI mezitím funguje dál."""

    def __init__(
        self,
        client: MikrotikClient,
        major: int,
        newest: Version,
        channel: Channel,
    ) -> None:
        super().__init__(self._work, client, major, newest, channel)

    def _work(
        self,
        client: MikrotikClient,
        major: int,
        newest: Version,
        channel: Channel,
    ) -> list[Version]:
        versions = client.list_versions(
            major,
            newest,
            token=self.token,
            progress=lambda done, total: self.signals.progress.emit(done, total),
        )
        return filter_for_channel(versions, channel)


class ChangelogWorker(Worker):
    """Changelog vybrané verze i s datem jejího vydání."""

    def __init__(self, client: MikrotikClient, version: Version) -> None:
        super().__init__(self._work, client, version)

    def _work(self, client: MikrotikClient, version: Version) -> ChangelogInfo:
        return client.changelog_info(version, token=self.token)


class PackagesWorker(Worker):
    """Načte extra balíčky pro všechny zvolené architektury najednou."""

    def __init__(
        self, client: MikrotikClient, version: Version, archs: Sequence[str]
    ) -> None:
        super().__init__(self._work, client, version, list(archs))

    def _work(
        self, client: MikrotikClient, version: Version, archs: list[str]
    ) -> tuple[Version, dict[str, ArchPackages]]:
        result: dict[str, ArchPackages] = {}
        for index, arch in enumerate(archs, start=1):
            self.token.raise_if_cancelled()
            result[arch] = client.list_packages(version, arch, token=self.token)
            self.signals.progress.emit(index, len(archs))
        return version, result


class SizesWorker(Worker):
    """Doplní velikosti souborů, aby celkový průběh seděl ještě před startem."""

    def __init__(self, client: MikrotikClient, remotes: Sequence[RemoteFile]) -> None:
        super().__init__(self._work, client, list(remotes))

    def _work(
        self, client: MikrotikClient, remotes: list[RemoteFile]
    ) -> list[RemoteFile]:
        return client.fill_sizes(remotes, token=self.token)


class UpdateCheckWorker(Worker):
    """Zeptá se GitHubu, jestli nevyšla novější verze aplikace."""

    def __init__(self, http: Http, current: str) -> None:
        super().__init__(self._work, http, current)

    def _work(self, http: Http, current: str) -> ReleaseInfo | None:
        return check_for_update(http, current, token=self.token)


class UpdateDownloadWorker(Worker):
    """Stáhne .exe nového vydání a ověří ho proti SHA256."""

    def __init__(self, http: Http, release: ReleaseInfo) -> None:
        super().__init__(self._work, http, release)

    def _work(self, http: Http, release: ReleaseInfo) -> Any:
        return download_update(
            http,
            release,
            # Velikost je z HTTP hlavičky, takže může chybět; 0 znamená
            # „neznámo“ a ukazatel průběhu se přepne na nekonečný.
            progress=lambda done, total: self.signals.progress.emit(done, total or 0),
            token=self.token,
        )


# --------------------------------------------------------------------------- #
class DownloadSignals(QObject):
    log = Signal(str, str)
    file_status = Signal(object, object)  # DownloadTask, Status
    file_progress = Signal(object, int, object, float)
    total_progress = Signal(int, object)
    finished = Signal(object)  # Report
    failed = Signal(str)


class DownloadWorker(QRunnable, Listener):
    """Stahování na pozadí. Zároveň slouží jako Listener jádra."""

    def __init__(
        self,
        client: MikrotikClient,
        tasks: Sequence[DownloadTask],
        *,
        max_workers: int = 3,
        verify_sha256: bool = True,
    ) -> None:
        QRunnable.__init__(self)
        self.signals = DownloadSignals()
        self.token = CancelToken()
        self._client = client
        self._tasks = list(tasks)
        self._downloader = Downloader(
            client, max_workers=max_workers, verify_sha256=verify_sha256
        )

    def cancel(self) -> None:
        self.token.cancel()

    @Slot()
    def run(self) -> None:
        try:
            report = self._downloader.run(self._tasks, self, self.token)
        except Cancelled:
            self.signals.finished.emit(Report())
        except RosdlError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(t("worker.unexpected_download", detail=exc))
        else:
            self.signals.finished.emit(report)

    # -- Listener ------------------------------------------------------- #
    def on_log(self, level: str, message: str) -> None:
        self.signals.log.emit(level, message)

    def on_file_status(self, task: DownloadTask, status: Status) -> None:
        self.signals.file_status.emit(task, status)

    def on_file_progress(
        self, task: DownloadTask, downloaded: int, total: int | None, speed: float
    ) -> None:
        self.signals.file_progress.emit(task, downloaded, total, speed)

    def on_file_finished(self, result: Any) -> None:
        # Koncový stav (done/skipped/failed/cancelled) už přišel přes
        # on_file_status, takže tady se nic neposílá – jinak by GUI zapsalo
        # do logu „staženo“ dvakrát pro každý soubor.
        return

    def on_total_progress(self, downloaded: int, total: int | None) -> None:
        self.signals.total_progress.emit(downloaded, total)
