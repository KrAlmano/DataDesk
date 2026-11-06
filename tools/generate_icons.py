"""Render the shared SVG into native macOS and Windows application icons."""

from io import BytesIO
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]


def generate_icons(output=None):
    output = Path(output) if output else ROOT / "build" / "icons"
    output.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(ROOT / "datadesk" / "assets" / "icon.svg"))
    if not renderer.isValid():
        raise ValueError("DataDesk SVG icon could not be loaded")
    canvas = QImage(1024, 1024, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not canvas.save(buffer, "PNG"):
        raise ValueError("DataDesk icon could not be rendered")
    raster = Image.open(BytesIO(bytes(buffer.data()))).convert("RGBA")
    raster.save(output / "datadesk.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    raster.save(output / "datadesk.icns")
    return output


if __name__ == "__main__":
    print(generate_icons())
