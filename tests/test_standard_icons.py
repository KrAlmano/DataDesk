"""Native Qt dialogs use readable directional icons in both themes."""

import pytest
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QStyle

from datadesk.theme import apply_theme, configure_app


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_file_dialog_arrows_use_current_palette(qapp, theme):
    previous_palette = qapp.palette()
    configure_app(qapp, theme)
    try:
        for kind in (
            QStyle.StandardPixmap.SP_ArrowUp,
            QStyle.StandardPixmap.SP_ArrowBack,
            QStyle.StandardPixmap.SP_ArrowForward,
        ):
            icon = qapp.style().standardIcon(kind)
            for mode, group in (
                (QIcon.Mode.Normal, QPalette.ColorGroup.Active),
                (QIcon.Mode.Disabled, QPalette.ColorGroup.Disabled),
            ):
                pixels = icon.pixmap(32, 32, mode).toImage()
                expected = qapp.palette().color(group, QPalette.ColorRole.WindowText)
                colors = [
                    pixels.pixelColor(x, y)
                    for x in range(pixels.width())
                    for y in range(pixels.height())
                    if pixels.pixelColor(x, y).alpha() > 200
                ]
                assert colors
                assert any(
                    abs(c.red() - expected.red()) < 3
                    and abs(c.green() - expected.green()) < 3
                    and abs(c.blue() - expected.blue()) < 3
                    for c in colors
                )
    finally:
        apply_theme(qapp, "light")
        qapp.setPalette(previous_palette)
