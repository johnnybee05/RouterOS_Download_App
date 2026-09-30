"""Přepínání jazyka v okně.

Okno se staví bez smyčky událostí, takže se dá po ``_set_language`` rovnou
kontrolovat, co je na popiskách.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI testy potřebují PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from rosdl import i18n  # noqa: E402
from rosdl.core import Settings  # noqa: E402
from rosdl.gui.main_window import MainWindow  # noqa: E402
from rosdl.gui.theme import ThemeManager  # noqa: E402


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path):  # noqa: ANN201
    settings = Settings()
    settings.target_dir = str(tmp_path)
    settings.language = "cs"
    theme = ThemeManager(qapp, "light")
    theme.apply()
    win = MainWindow(settings, theme)
    yield win
    win.http.close()
    win.deleteLater()
    i18n.set_language("cs")


def test_window_starts_in_the_stored_language(window: MainWindow) -> None:
    assert i18n.current_language() == "cs"
    assert window.button_download.text() == "Stáhnout"
    assert window.box_arch.title() == "Architektury"


def test_switching_language_retranslates_the_window(window: MainWindow) -> None:
    window._set_language("en")

    assert window.button_download.text() == "Download"
    assert window.button_cancel.text() == "Cancel"
    assert window.box_arch.title() == "Architectures"
    assert window.box_extras.title() == "Extra packages"
    assert window.box_target.title() == "Target"
    assert window.menu_file.title() == "&File"
    assert window.menu_help.title() == "&Help"
    assert window.action_about.text() == "About"
    assert window.caption_major.text() == "Series:"
    assert window.edit_filter.placeholderText() == "Filter by name…"


def test_switching_back_restores_czech(window: MainWindow) -> None:
    window._set_language("en")
    window._set_language("cs")
    assert window.button_download.text() == "Stáhnout"
    assert window.check_verify.text() == "Ověřovat SHA256"


def test_theme_names_follow_the_language(window: MainWindow) -> None:
    window._set_language("en")
    assert [a.text() for a in window._theme_actions.values()] == [
        "System",
        "Light",
        "Dark",
    ]
    window._set_language("cs")
    assert window._theme_actions["dark"].text() == "Tmavý"


def test_language_menu_offers_system_and_every_language(window: MainWindow) -> None:
    assert set(window._language_actions) == {"", *i18n.available_languages()}
    assert window._language_actions[""].text() == "Podle systému"
    # Jazyky se nabízejí ve svém vlastním jméně, ať je pozná i ten,
    # kdo do aplikace omylem nastavil jazyk, kterému nerozumí.
    assert window._language_actions["en"].text() == "English"
    assert window._language_actions["cs"].text() == "Čeština"


def test_transfer_table_header_is_retranslated(window: MainWindow) -> None:
    window._set_language("en")
    header = window.table_transfers.headerItem()
    assert [header.text(i) for i in range(4)] == [
        "File",
        "Size",
        "Status",
        "Progress",
    ]


def test_running_transfer_keeps_its_row_but_changes_wording(
    window: MainWindow,
) -> None:
    """Přepnutí jazyka během stahování nesmí ztratit řádky ani průběh."""
    window.table_transfers.set_rows([("k", "routeros-7.24.4.npk", "13,3 MB")])
    window.table_transfers.set_status("k", "downloading")
    window.table_transfers.set_progress("k", 42)

    window._set_language("en")

    item = window.table_transfers._rows["k"]
    assert item.text(window.table_transfers.COL_STATUS) == "downloading"
    assert item.text(window.table_transfers.COL_NAME) == "routeros-7.24.4.npk"
    window._set_language("cs")
    assert item.text(window.table_transfers.COL_STATUS) == "stahuji"


def test_architecture_tooltips_are_retranslated(window: MainWindow) -> None:
    window._set_language("en")
    keys = window.list_arch.keys()
    index = keys.index("x86")
    assert "virtual machines" in window.list_arch.item(index).toolTip()


def test_chosen_language_is_saved(window: MainWindow) -> None:
    window._set_language("en")
    assert window._collect_settings().language == "en"


def test_system_choice_is_saved_as_empty(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Volba „podle systému“ se nesmí uložit jako konkrétní jazyk.

    Jinak by uživatel, který ji jednou zvolil, zůstal navěky u jazyka,
    jaký měl systém v té chvíli.
    """
    monkeypatch.setattr("rosdl.gui.main_window.resolve_language", lambda _c: "en")
    window._language_actions[""].setChecked(True)
    window._set_language("")
    assert window._collect_settings().language == ""
    assert i18n.current_language() == "en"


def test_log_entries_already_written_are_left_alone(window: MainWindow) -> None:
    """Log je záznam toho, co se stalo – zpětně se nepřekládá."""
    window.log.append_entry("info", "Připraveno")
    before = window.log.toPlainText()
    window._set_language("en")
    assert "Připraveno" in before
    assert window.log.toPlainText() == before
