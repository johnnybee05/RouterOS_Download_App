"""Regrese na chyby třídy „zastaralý stav po změně výběru“ v GUI.

Všechny testy tady vznikly z konkrétní chyby, která se v aplikaci opravdu
projevila. Okno se staví bez smyčky událostí – ``QTimer.singleShot(0, …)``
v konstruktoru tím pádem nikdy nevystřelí a stav se dá kontrolovat přímo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI testy potřebují PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from rosdl.core import Channel, MikrotikClient, Settings, Version  # noqa: E402
from rosdl.core.cache import JsonCache  # noqa: E402
from rosdl.core.client import NewestInfo  # noqa: E402
from rosdl.core.models import ArchPackages, PackageEntry  # noqa: E402
from rosdl.gui.main_window import MainWindow  # noqa: E402
from rosdl.gui.theme import ThemeManager  # noqa: E402

from .conftest import FakeServer  # noqa: E402

V = Version.parse("7.24.4")


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path):  # noqa: ANN201
    server = FakeServer()
    settings = Settings()
    settings.architectures = ["arm64"]
    settings.extras = []
    settings.target_dir = str(tmp_path)

    theme = ThemeManager(qapp, "light")
    theme.apply()
    win = MainWindow(settings, theme)
    win.http.close()
    win.http = server.http()
    win.client = MikrotikClient(
        win.http,
        versions_cache=JsonCache("v.json", 3600, directory=tmp_path),
        packages_cache=JsonCache("p.json", 3600, directory=tmp_path),
    )
    win._version = V
    yield win
    win.http.close()
    win.deleteLater()


def packages(arch: str, *names: str) -> dict[str, ArchPackages]:
    return {
        arch: ArchPackages(
            arch=arch,
            version=V,
            entries={
                n: PackageEntry(n, arch, f"{n}-7.24.4-{arch}.npk", 1000) for n in names
            },
        )
    }


def select_archs(win: MainWindow, *archs: str) -> None:
    """Zaškrtne architektury bez rozjetí načítání na pozadí."""
    win.list_arch.blockSignals(True)
    win.list_arch.set_checked(archs)
    win.list_arch.blockSignals(False)


# --------------------------------------------------------------------------- #
# Závody mezi workery
# --------------------------------------------------------------------------- #
def test_stale_arch_result_is_discarded(window: MainWindow) -> None:
    """Rychlá změna architektury: starší odpověď nesmí přepsat novější.

    Kontrolovat jen verzi nestačí – oba workery běží nad toutéž verzí.
    """
    select_archs(window, "x86")
    window._packages = {}

    window._on_packages_loaded((V, packages("arm64", "container")))
    assert window._union_packages() == []

    window._on_packages_loaded((V, packages("x86", "dude")))
    assert window._union_packages() == ["dude"]


def test_stale_version_result_is_discarded(window: MainWindow) -> None:
    select_archs(window, "x86")
    window._on_packages_loaded((V, packages("x86", "dude")))

    window._version = Version.parse("7.23.7")
    window._on_packages_loaded((V, packages("x86", "container")))

    assert window._union_packages() == ["dude"]


def test_stale_channel_answer_does_not_change_version(window: MainWindow) -> None:
    """Odpověď kanálu, ze kterého uživatel mezitím odešel, se musí zahodit."""
    window.combo_version.blockSignals(True)
    window.combo_version.setEditText("7.24.4")
    window.combo_version.blockSignals(False)

    stale = window._selection_generation
    window._selection_generation += 1  # uživatel přepnul kanál

    window._on_newest_loaded(
        NewestInfo(version=Version.parse("7.12.1"), released=None),
        stale,
        Channel.TESTING,
    )

    assert window.combo_version.currentText() == "7.24.4"


def test_stale_channel_history_does_not_replace_list(window: MainWindow) -> None:
    window.combo_version.blockSignals(True)
    window.combo_version.clear()
    window.combo_version.addItem("7.24.4")
    window.combo_version.blockSignals(False)

    stale = window._selection_generation
    window._selection_generation += 1

    window._on_versions_loaded([Version.parse("6.1"), Version.parse("6.0")], stale)

    assert window.combo_version.findText("6.1") < 0
    assert window.combo_version.findText("7.24.4") >= 0


# --------------------------------------------------------------------------- #
# Chybové cesty nesmí nechat na obrazovce cizí data
# --------------------------------------------------------------------------- #
def test_changelog_error_survives_theme_switch(window: MainWindow) -> None:
    """Překreslení při změně motivu vracelo changelog předchozí verze."""
    window._changelog_text = "What's new in 7.24.4 (2026-09-16):\n*) starý text;\n"
    window._on_changelog_failed(V, "404")

    window.theme.set_mode("dark")
    try:
        assert window.text_changelog.toPlainText().startswith("Chyba")
    finally:
        window.theme.set_mode("light")


def test_changelog_error_updates_release_label(window: MainWindow) -> None:
    """Popisek data nesmí zůstat viset na „zjišťuji…“."""
    window._load_changelog(V)
    assert "zjišťuji" in window.label_release.text()

    window._on_changelog_failed(V, "404")
    assert "zjišťuji" not in window.label_release.text()


def test_loading_changelog_drops_previous_text(window: MainWindow) -> None:
    window._changelog_text = "What's new in 7.20.1 (2025-01-01):\n"
    window._load_changelog(V)
    window.theme.set_mode("dark")
    try:
        assert "7.20.1" not in window.text_changelog.toPlainText()
    finally:
        window.theme.set_mode("light")


def test_package_failure_clears_stale_list(window: MainWindow) -> None:
    """Po chybě nesmí v seznamu zůstat balíčky předchozí verze."""
    select_archs(window, "x86")
    window._on_packages_loaded((V, packages("x86", "container", "dude")))
    assert window.list_extras.count() == 2

    window._on_packages_failed(V, "Spojení selhalo")

    assert window.list_extras.count() == 0
    assert "nepodařilo" in window.label_extras_note.text().lower()


# --------------------------------------------------------------------------- #
# Zaškrtnuté balíčky
# --------------------------------------------------------------------------- #
def test_unchecking_everything_survives_rerender(window: MainWindow) -> None:
    """Odškrtnutí „Nic“ se po překreslení vracelo zpátky z nastavení."""
    select_archs(window, "x86")
    window._selected_extras = {"container", "dude"}
    window._on_packages_loaded((V, packages("x86", "container", "dude")))
    assert window.list_extras.checked_keys() == ["container", "dude"]

    window.list_extras.set_all(False)
    window._render_extras()

    assert window.list_extras.checked_keys() == []
    assert window._selected_extras == set()


def test_selection_survives_version_without_that_package(
    window: MainWindow,
) -> None:
    """Volba se nesmí ztratit jen proto, že v jiné verzi balíček není."""
    select_archs(window, "x86")
    window._on_packages_loaded((V, packages("x86", "container", "dude")))
    window.list_extras.set_checked(["container"])

    # verze, která container nemá
    window._on_packages_loaded((V, packages("x86", "dude")))
    assert window._selected_extras == {"container"}
    assert window.list_extras.checked_keys() == []

    # a zpátky
    window._on_packages_loaded((V, packages("x86", "container", "dude")))
    assert window.list_extras.checked_keys() == ["container"]


def test_settings_store_remembered_selection(window: MainWindow) -> None:
    select_archs(window, "x86")
    window._on_packages_loaded((V, packages("x86", "container")))
    window.list_extras.set_checked(["container"])
    window._selected_extras.add("wifi-qcom")  # z jiné verze

    saved = window._collect_settings()

    assert saved.extras == ["container", "wifi-qcom"]


# --------------------------------------------------------------------------- #
def test_failed_worker_is_forgotten(window: MainWindow) -> None:
    """Neúspěšné workery se hromadily v seznamu až do zavření okna."""
    from rosdl.gui.workers import Worker

    worker = Worker(lambda: None)
    window._active_workers.append(worker)
    worker.signals.failed.connect(lambda *_, w=worker: window._forget_worker(w))

    worker.signals.failed.emit("chyba")

    assert worker not in window._active_workers


def test_worker_does_not_duplicate_final_status(window: MainWindow) -> None:
    """DownloadWorker přeposílal koncový stav i z on_file_finished."""
    from rosdl.core.downloader import DownloadTask, FileResult, Status
    from rosdl.gui.workers import DownloadWorker

    task = DownloadTask(remote=window.client.main_file(V, "arm64"), dest=Path("x.npk"))
    worker = DownloadWorker(window.client, [task])

    seen: list[Status] = []
    worker.signals.file_status.connect(lambda _t, s: seen.append(s))

    worker.on_file_status(task, Status.DONE)
    worker.on_file_finished(FileResult(task=task, status=Status.DONE))

    assert seen == [Status.DONE]


def test_close_waits_for_workers_before_closing_http(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zavřít klienta pod rukama běžícímu přenosu = ReadError z půlky streamu."""
    order: list[str] = []
    monkeypatch.setattr(window.http, "close", lambda: order.append("close"))
    monkeypatch.setattr(
        window.pool, "waitForDone", lambda _ms: order.append("wait") or True
    )

    window.close()

    assert order == ["wait", "close"]


def test_close_skips_http_close_when_workers_hang(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zatuhlé vlákno čeká na read timeout – klienta pak radši nezavřeme."""
    closed: list[str] = []
    monkeypatch.setattr(window.http, "close", lambda: closed.append("close"))
    monkeypatch.setattr(window.pool, "waitForDone", lambda _ms: False)

    window.close()

    assert closed == []
