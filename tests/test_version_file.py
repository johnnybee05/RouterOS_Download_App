"""Zdroj VERSIONINFO pro .exe – viz ``tools/make_version_file.py``.

Chyba v něm se pozná až při sestavení, a to se pouští jen při vydání.
Proto se tady vygenerovaný text rovnou prohání parserem PyInstalleru:
diakritika v popisu nebo apostrof v textu by jinak shodily release.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from make_version_file import numeric_version, render  # noqa: E402


@pytest.mark.parametrize(
    ("version", "numeric"),
    [
        ("1.2.1", (1, 2, 1, 0)),
        ("1.2", (1, 2, 0, 0)),
        ("2", (2, 0, 0, 0)),
        ("1.2.1.9", (1, 2, 1, 9)),
        # Předvydání VERSIONINFO neumí, zůstane z něj jen číselná část.
        ("1.2.1-rc1", (1, 2, 1, 0)),
        ("1.2.1+g1234567", (1, 2, 1, 0)),
    ],
)
def test_numeric_version(version: str, numeric: tuple[int, ...]) -> None:
    assert numeric_version(version) == numeric


def test_render_is_parsable_by_pyinstaller(tmp_path: Path) -> None:
    pytest.importorskip("PyInstaller")
    from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file

    target = tmp_path / "version_info.txt"
    target.write_text(render("1.2.1"), encoding="utf-8")

    info = load_version_info_from_text_file(str(target))

    # 1.2.1.0 se do dvou 32bitových polí ukládá po dvojicích složek.
    assert info.ffi.fileVersionMS == (1 << 16) | 2
    assert info.ffi.fileVersionLS == (1 << 16) | 0


def test_render_contains_publisher_strings() -> None:
    text = render("1.2.1")

    # Prázdná metadata jsou pro SmartScreen a antiviry signál sám o sobě,
    # takže tyhle údaje tam musí být vždycky.
    for field in ("CompanyName", "FileDescription", "ProductName", "LegalCopyright"):
        assert field in text
    assert "1.2.1.0" in text
