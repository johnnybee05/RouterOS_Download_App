"""Hledání přibalených souborů ve zdrojácích i uvnitř .exe od PyInstalleru."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Cesta k přibalenému souboru.

    PyInstaller v režimu ``--onefile`` rozbalí data do dočasné složky
    a její cestu předá v ``sys._MEIPASS``; ve zdrojácích se jde od kořene
    projektu.
    """
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent.parent
    return root / relative


APP_ICON = "assets/rosdl.ico"


def app_icon_path() -> Path | None:
    path = resource_path(APP_ICON)
    return path if path.exists() else None
