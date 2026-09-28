"""Chování GUI kolem aktualizace: kdy se nabídne a kdy se drží zpátky.

Okno i dialog se staví bez smyčky událostí, modální okna se nahrazují
monkeypatchem – jinak by test na prvním ``exec()`` zamrzl.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI testy potřebují PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from rosdl.core import MikrotikClient, Settings  # noqa: E402
from rosdl.core.updater import ReleaseInfo, parse_release  # noqa: E402
from rosdl.gui import main_window as mw  # noqa: E402
from rosdl.gui import update_dialog as ud  # noqa: E402
from rosdl.gui.main_window import MainWindow  # noqa: E402
from rosdl.gui.theme import ThemeManager  # noqa: E402
from rosdl.gui.update_dialog import UpdateDialog  # noqa: E402

from .conftest import FakeServer  # noqa: E402


def release(tag: str = "v9.9.9", *, asset: bool = True) -> ReleaseInfo:
    assets = (
        [
            {
                "name": "RosDownloader.exe",
                "size": 10,
                "browser_download_url": "https://example.test/RosDownloader.exe",
            }
        ]
        if asset
        else []
    )
    return parse_release(
        {
            "tag_name": tag,
            "name": f"RosDownloader {tag.lstrip('v')}",
            "body": "## Novinky\n\n- něco nového",
            "html_url": f"https://github.com/x/y/releases/tag/{tag}",
            "published_at": "2026-09-28T09:40:53Z",
            "assets": assets,
        }
    )


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path):  # noqa: ANN201
    server = FakeServer()
    settings = Settings()
    settings.target_dir = str(tmp_path)
    theme = ThemeManager(qapp, "light")
    theme.apply()
    win = MainWindow(settings, theme)
    win.http.close()
    win.http = server.http()
    win.client = MikrotikClient(win.http)
    yield win
    win.http.close()
    win.deleteLater()


@pytest.fixture
def shown(monkeypatch: pytest.MonkeyPatch) -> list[ReleaseInfo]:
    """Zachytí, co by se bylo nabídlo, místo otevření modálního okna."""
    seen: list[ReleaseInfo] = []
    monkeypatch.setattr(
        MainWindow, "_show_update_dialog", lambda self, rel: seen.append(rel)
    )
    return seen


@pytest.fixture
def quiet(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Hlášky z QMessageBox místo skutečných oken."""
    messages: list[str] = []

    def capture(_parent, title, text, *args, **kwargs):  # noqa: ANN001, ANN202
        messages.append(f"{title}: {text}")
        return QMessageBox.StandardButton.No

    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, capture)
    return messages


# --------------------------------------------------------------------------- #
class TestWhenTheOfferAppears:
    def test_newer_version_is_offered(self, window, shown) -> None:  # noqa: ANN001
        window._on_update_checked(release("v9.9.9"), False)
        assert [r.tag for r in shown] == ["v9.9.9"]

    def test_nothing_new_stays_quiet(self, window, shown, quiet) -> None:  # noqa: ANN001
        window._on_update_checked(None, False)
        assert shown == []
        assert quiet == []

    def test_manual_check_says_you_are_up_to_date(self, window, shown, quiet) -> None:  # noqa: ANN001
        window._on_update_checked(None, True)
        assert shown == []
        assert len(quiet) == 1

    def test_skipped_version_is_not_offered_again(self, window, shown) -> None:  # noqa: ANN001
        window.settings.skipped_update = "v9.9.9"
        window._on_update_checked(release("v9.9.9"), False)
        assert shown == []

    def test_skipped_version_still_shows_on_manual_check(self, window, shown) -> None:  # noqa: ANN001
        window.settings.skipped_update = "v9.9.9"
        window._on_update_checked(release("v9.9.9"), True)
        assert [r.tag for r in shown] == ["v9.9.9"]

    def test_failed_check_after_start_stays_quiet(self, window, quiet) -> None:  # noqa: ANN001
        window._on_update_check_failed("síť neodpovídá", False)
        assert quiet == []

    def test_failed_manual_check_says_why(self, window, quiet) -> None:  # noqa: ANN001
        window._on_update_check_failed("síť neodpovídá", True)
        assert quiet == ["Aktualizace: síť neodpovídá"]


class TestDuringADownload:
    def test_offer_waits_for_the_packages_to_finish(
        self,
        window,  # noqa: ANN001
        quiet: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        opened: list[object] = []
        monkeypatch.setattr(mw, "UpdateDialog", lambda *a, **k: opened.append(a))
        window._download_worker = object()  # stahování balíčků právě běží
        window._show_update_dialog(release())
        assert opened == []
        assert len(quiet) == 1


class TestApplyUpdate:
    def test_declining_the_restart_installs_nothing(
        self,
        window,  # noqa: ANN001
        quiet: list[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # `quiet` odpovídá na question() vždy No.
        calls: list[Path] = []
        monkeypatch.setattr(mw, "install_update", lambda p: calls.append(p))
        window._apply_update(tmp_path / "new.exe", release())
        assert calls == []
        assert window._pending_relaunch is False

    def test_accepting_installs_and_asks_for_restart(
        self,
        window,  # noqa: ANN001
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        calls: list[Path] = []
        monkeypatch.setattr(mw, "install_update", lambda p: calls.append(p))
        monkeypatch.setattr(MainWindow, "close", lambda self: None)

        window._apply_update(tmp_path / "new.exe", release())

        assert calls == [tmp_path / "new.exe"]
        assert window._pending_relaunch is True

    def test_failed_install_does_not_schedule_a_restart(
        self,
        window,  # noqa: ANN001
        quiet: list[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )

        def boom(_path: Path) -> None:
            raise mw.UpdateError("soubor je zamčený")

        monkeypatch.setattr(mw, "install_update", boom)
        window._apply_update(tmp_path / "new.exe", release())
        assert window._pending_relaunch is False
        assert quiet == ["Aktualizace: soubor je zamčený"]


class TestSettings:
    def test_menu_switch_writes_to_settings(self, window) -> None:  # noqa: ANN001
        window.action_auto_updates.setChecked(False)
        assert window.settings.check_updates_on_start is False
        window.action_auto_updates.setChecked(True)
        assert window.settings.check_updates_on_start is True

    def test_new_keys_survive_a_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        s = Settings()
        s.check_updates_on_start = False
        s.skipped_update = "v9.9.9"
        s.save(path)
        loaded = Settings.load(path)
        assert loaded.check_updates_on_start is False
        assert loaded.skipped_update == "v9.9.9"

    def test_older_settings_file_gets_the_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text('{"major": 7}', encoding="utf-8")
        loaded = Settings.load(path)
        assert loaded.check_updates_on_start is True
        assert loaded.skipped_update == ""


class TestUpdateDialog:
    def test_source_checkout_cannot_install_itself(
        self, window, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
    ) -> None:
        monkeypatch.setattr(ud, "is_frozen", lambda: False)
        dialog = UpdateDialog(
            None,
            release=release(),
            current="1.0.3",
            http=window.http,
            theme=window.theme,
        )
        assert not dialog.button_install.isEnabled()
        assert dialog.button_page.isEnabled()
        dialog.deleteLater()

    def test_release_without_exe_cannot_install_either(
        self, window, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
    ) -> None:
        monkeypatch.setattr(ud, "is_frozen", lambda: True)
        dialog = UpdateDialog(
            None,
            release=release(asset=False),
            current="1.0.3",
            http=window.http,
            theme=window.theme,
        )
        assert not dialog.button_install.isEnabled()
        dialog.deleteLater()

    def test_closing_during_a_download_cancels_it_first(
        self, window, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
    ) -> None:
        monkeypatch.setattr(ud, "is_frozen", lambda: True)
        dialog = UpdateDialog(
            None,
            release=release(),
            current="1.0.3",
            http=window.http,
            theme=window.theme,
        )

        class FakeWorker:
            cancelled = False

            def cancel(self) -> None:
                FakeWorker.cancelled = True

        dialog._worker = FakeWorker()
        dialog.reject()

        assert FakeWorker.cancelled
        assert dialog.isVisible() is False  # nezobrazený dialog nezavíráme
        assert dialog.result() == 0
        assert dialog.button_install.isEnabled()  # jde zkusit znovu
        dialog.deleteLater()

    def test_frozen_build_offers_the_install(
        self, window, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
    ) -> None:
        monkeypatch.setattr(ud, "is_frozen", lambda: True)
        dialog = UpdateDialog(
            None,
            release=release(),
            current="1.0.3",
            http=window.http,
            theme=window.theme,
        )
        assert dialog.button_install.isEnabled()
        assert "9.9.9" in dialog.label_title.text()
        assert "1.0.3" in dialog.label_meta.text()
        dialog.deleteLater()
