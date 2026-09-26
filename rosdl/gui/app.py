"""Spuštění GUI."""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import APP_NAME, __version__
from ..core import Settings
from .main_window import MainWindow
from .resources import app_icon_path
from .theme import ThemeManager


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    icon = app_icon_path()
    if icon is not None:
        app.setWindowIcon(QIcon(str(icon)))

    settings = Settings.load()
    theme = ThemeManager(app, settings.theme)  # type: ignore[arg-type]
    theme.apply()

    window = MainWindow(settings, theme)
    window.show()
    # Titulkový pruh se dá přebarvit až když okno má HWND, tedy po show().
    theme.register_window(window)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
