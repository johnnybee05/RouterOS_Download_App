"""Vygeneruje ``assets/rosdl.ico`` z SVG ikony použité v GUI.

Ikona se nekreslí ručně – vychází ze stejného SVG jako ikony v okně, takže
aplikace i .exe vypadají stejně. Spouští se jen při změně ikony:

    python tools/make_icon.py
"""

from __future__ import annotations

import struct
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
BACKGROUND = "#1668c8"
FOREGROUND = "#ffffff"

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="0" y="0" width="64" height="64" rx="12" fill="{BACKGROUND}"/>
  <path d="M32 14v22m0 0 9-9m-9 9-9-9" stroke="{FOREGROUND}" stroke-width="5"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M14 42v4a4 4 0 0 0 4 4h28a4 4 0 0 0 4-4v-4" stroke="{FOREGROUND}"
        stroke-width="5" fill="none" stroke-linecap="round"/>
</svg>"""


def render(size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    QSvgRenderer(SVG.encode("utf-8")).render(painter)
    painter.end()

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def build_ico(images: dict[int, bytes]) -> bytes:
    """Složí ICO kontejner s PNG položkami (podporováno od Windows Vista)."""
    out = BytesIO()
    out.write(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for size, payload in images.items():
        width = 0 if size >= 256 else size
        out.write(
            struct.pack(
                "<BBBBHHII", width, width, 0, 0, 1, 32, len(payload), offset
            )
        )
        offset += len(payload)
    for payload in images.values():
        out.write(payload)
    return out.getvalue()


def main() -> int:
    QGuiApplication([])  # QImage/QPainter potřebují instanci aplikace
    images = {size: render(size) for size in SIZES}
    target = ROOT / "assets" / "rosdl.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_ico(images))
    print(f"zapsáno {target} ({target.stat().st_size} B, velikosti: "
          f"{', '.join(str(s) for s in SIZES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
