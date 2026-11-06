"""Settings remain usable at large zoom and do not apply edits before confirmation."""

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QWidget

from datadesk.i18n import language, set_language
from datadesk.settings_ui import SettingsDialog
from datadesk.theme import PALETTES, apply_theme, scaled_style


@pytest.fixture(autouse=True)
def restore_preferences(qapp):
    original_language = language()
    original_palette = qapp.palette()
    original_theme = qapp.property("datadeskTheme")
    original_preference = qapp.property("datadeskThemePreference")
    yield
    set_language(original_language)
    qapp.setPalette(original_palette)
    qapp.setProperty("datadeskTheme", original_theme)
    qapp.setProperty("datadeskThemePreference", original_preference)


@pytest.mark.parametrize("locale", ["tr", "en"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_settings_are_translated_and_reachable_at_150_percent(qtbot, qapp, locale, theme):
    set_language(locale)
    apply_theme(qapp, theme)
    parent = QWidget()
    parent.resize(640, 480)
    parent.setStyleSheet(scaled_style(150, theme))
    qtbot.addWidget(parent)
    parent.show()
    dialog = SettingsDialog(parent, language=locale, theme=theme, zoom=150)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()

    assert dialog.windowTitle() == ("DataDesk · Settings" if locale == "en" else "DataDesk · Ayarlar")
    assert dialog.theme_combo.itemText(0) == ("Light" if locale == "en" else "Açık")
    assert dialog.theme_combo.itemText(2) == ("System" if locale == "en" else "Sistem")
    assert dialog.language_combo.itemText(0) == "Türkçe"
    assert dialog.language_combo.itemText(1) == "English"
    assert dialog.preferences() == {"language": locale, "theme": theme, "zoom": 150}
    assert dialog.content_scroll.horizontalScrollBar().maximum() == 0
    assert dialog.width() <= parent.width()
    assert dialog.height() <= parent.height()

    for control in (dialog.language_combo, dialog.theme_combo, dialog.zoom_combo):
        dialog.content_scroll.ensureWidgetVisible(control, 8, 8)
        QApplication.processEvents()
        viewport = dialog.content_scroll.viewport()
        bounds = QRect(control.mapTo(viewport, QPoint()), control.size())
        assert viewport.rect().contains(bounds)
        assert control.width() >= control.minimumSizeHint().width()
        assert control.palette().color(QPalette.ColorRole.Text).name() == PALETTES[theme]["text"]
        assert control.font().pixelSize() == 20

    for action in dialog.buttons.buttons():
        bounds = QRect(action.mapTo(dialog, QPoint()), action.size())
        assert dialog.rect().contains(bounds)
        assert action.width() >= action.minimumSizeHint().width()
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Apply).text() == (
        "Apply" if locale == "en" else "Uygula"
    )
    text = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert ("cell contents stay the same" if locale == "en" else "hücre içerikleri değişmez") in text


def test_cancel_discards_candidate_selections_without_changing_application(qtbot, qapp):
    set_language("tr")
    apply_theme(qapp, "light")
    dialog = SettingsDialog(language="tr", theme="light", zoom=100)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))
    dialog.zoom_combo.setCurrentIndex(dialog.zoom_combo.findData(150))
    assert language() == "tr"
    assert qapp.property("datadeskTheme") == "light"
    with qtbot.waitSignal(dialog.rejected):
        qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel), Qt.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert language() == "tr"
    assert qapp.palette().color(QPalette.ColorRole.Base).name() == PALETTES["light"]["surface"]


def test_apply_accepts_stable_codes_and_preserves_a_nonstandard_zoom(qtbot):
    set_language("en")
    dialog = SettingsDialog(language="en", theme="system", zoom=110)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.preferences() == {"language": "en", "theme": "system", "zoom": 110}
    assert dialog.zoom_combo.currentText() == "110%"
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("tr"))
    with qtbot.waitSignal(dialog.accepted):
        qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Apply), Qt.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.preferences() == {"language": "tr", "theme": "system", "zoom": 110}
    assert language() == "en"
