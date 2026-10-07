"""Vygeneruje zdroj VERSIONINFO pro PyInstaller z ``rosdl.__version__``.

Bez tohoto zdroje nemá .exe ve vlastnostech vůbec nic – žádný popis, výrobce
ani verzi. To jednak vypadá podezřele (SmartScreen i heuristiky antivirů to
berou v potaz) a jednak se v dialogu "Neznámý vydavatel" nemá co ukázat.
Číslo verze se nebere odnikud jinud než z ``rosdl/__init__.py``, aby se při
vydání neverzovalo na dvou místech:

    python tools/make_version_file.py build/version_info.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rosdl import __version__  # noqa: E402

COMPANY = "johnnybee05"
PRODUCT = "RosDownloader"
# Tabulka níž je vedená jako en-US, takže i texty v ní jsou anglicky –
# jde o metadata souboru, ne o text, který by aplikace uživateli ukazovala.
DESCRIPTION = "RosDownloader – MikroTik RouterOS package downloader"
COPYRIGHT = "Copyright (c) 2026 johnnybee05 – MIT licence"
HOMEPAGE = "https://github.com/johnnybee05/RouterOS_Download_App"

#: VERSIONINFO zná jen čtyřčlennou číselnou verzi, takže se na čtyři složky
#: doplní nulami. ``1.2.1`` → ``(1, 2, 1, 0)``.
_VERSION_PARTS = 4

TEMPLATE = """\
# Vygenerováno tools/make_version_file.py – needituj ručně.
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers={numeric},
        prodvers={numeric},
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            # 0x0409 = en-US, 1200 = UTF-16. Aplikace je dvojjazyčná, ale
            # tahle tabulka je jen metadata souboru, ne text pro uživatele.
            StringTable("040904B0", [
                StringStruct("CompanyName", {company!r}),
                StringStruct("FileDescription", {description!r}),
                StringStruct("FileVersion", {display!r}),
                StringStruct("InternalName", {product!r}),
                StringStruct("LegalCopyright", {copyright!r}),
                StringStruct("OriginalFilename", {filename!r}),
                StringStruct("ProductName", {product!r}),
                StringStruct("ProductVersion", {display!r}),
                StringStruct("Comments", {homepage!r}),
            ]),
        ]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)
"""


def numeric_version(version: str) -> tuple[int, ...]:
    """``"1.2.1"`` → ``(1, 2, 1, 0)``; případné ``-rc1`` se zahodí."""
    release = version.split("-", 1)[0].split("+", 1)[0]
    parts = [int(part) for part in release.split(".")]
    parts += [0] * (_VERSION_PARTS - len(parts))
    return tuple(parts[:_VERSION_PARTS])


def render(version: str) -> str:
    numeric = numeric_version(version)
    return TEMPLATE.format(
        numeric=numeric,
        display=".".join(str(part) for part in numeric),
        company=COMPANY,
        product=PRODUCT,
        description=DESCRIPTION,
        copyright=COPYRIGHT,
        filename=f"{PRODUCT}.exe",
        homepage=HOMEPAGE,
    )


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else ROOT / "build" / "version_info.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(__version__), encoding="utf-8")
    print(f"zapsáno {target} (verze {__version__})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
