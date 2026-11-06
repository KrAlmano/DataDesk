"""Both appearances keep real controls, editors and status colors readable."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QStyleOptionSpinBox,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from datadesk.theme import PALETTES, apply_theme, palette_for, resolve_theme, scaled_style


def luminance(hex_color):
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(first, second):
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_status_selection_disabled_and_body_text_have_readable_contrast(theme):
    colors = PALETTES[theme]
    for foreground, background in [
        ("text", "surface"),
        ("text", "alternate"),
        ("muted", "surface"),
        ("muted", "chrome"),
        ("muted", "sidebar"),
        ("selection_text", "selection"),
        ("disabled_text", "disabled_bg"),
        ("notice_text", "notice_bg"),
        ("error_text", "error_bg"),
        ("on_primary", "primary"),
        ("on_primary", "primary_hover"),
        ("on_primary", "primary_pressed"),
        ("accent", "surface"),
    ]:
        assert contrast(colors[foreground], colors[background]) >= 4.5, (theme, foreground, background)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_table_editor_dialog_and_disabled_controls_follow_live_theme(qtbot, qapp, theme):
    original = qapp.palette()
    previous_theme = qapp.property("datadeskTheme")
    previous_preference = qapp.property("datadeskThemePreference")
    root = QWidget()
    layout = QVBoxLayout(root)
    entry = QLineEdit("00123 · İstanbul", root)
    disabled = QPushButton("Unavailable", root)
    disabled.setDisabled(True)
    combo = QComboBox(root)
    combo.addItems(["Excel", "CSV"])
    table = QTableView(root)
    model = QStandardItemModel(1, 1, root)
    model.setItem(0, 0, QStandardItem("Original"))
    table.setModel(model)
    for widget in (entry, disabled, combo, table):
        layout.addWidget(widget)
    dialog = QDialog(root)
    dialog_layout = QVBoxLayout(dialog)
    dialog_entry = QLineEdit("Visible in a dialog", dialog)
    dialog_layout.addWidget(dialog_entry)
    qtbot.addWidget(root)
    qtbot.addWidget(dialog)
    root.show()
    dialog.show()
    try:
        # Switch on the already-created widget tree, rather than only checking
        # colors of controls instantiated after the theme has been applied.
        for selected in (theme, "light" if theme == "dark" else "dark", theme):
            apply_theme(qapp, selected)
            root.setStyleSheet(scaled_style(100, selected))
            QApplication.processEvents()
            expected = PALETTES[selected]
            for widget in (entry, combo, table, dialog_entry):
                assert widget.palette().color(QPalette.ColorRole.Base).name() == expected["surface"]
                assert widget.palette().color(QPalette.ColorRole.Text).name() == expected["text"]
            assert (
                disabled.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText).name()
                == expected["disabled_text"]
            )
            table.edit(model.index(0, 0))
            QApplication.processEvents()
            editor = table.findChild(QLineEdit)
            assert editor is not None
            assert editor.palette().color(QPalette.ColorRole.Base).name() == expected["surface"]
            assert editor.palette().color(QPalette.ColorRole.Text).name() == expected["text"]
            qtbot.keyClick(editor, Qt.Key.Key_Escape)
            assert entry.text() == "00123 · İstanbul"
            assert model.item(0, 0).text() == "Original"
    finally:
        qapp.setPalette(original)
        qapp.setProperty("datadeskTheme", previous_theme)
        qapp.setProperty("datadeskThemePreference", previous_preference)


def test_system_preference_tracks_os_appearance_without_overriding_it():
    state = {"scheme": Qt.ColorScheme.Dark}
    hints = SimpleNamespace(colorScheme=lambda: state["scheme"])
    fake_app = SimpleNamespace(styleHints=lambda: hints)
    assert resolve_theme("system", fake_app) == "dark"
    assert (
        palette_for("system", fake_app).color(QPalette.ColorRole.Base).name() == PALETTES["dark"]["surface"]
    )
    state["scheme"] = Qt.ColorScheme.Light
    assert resolve_theme("system", fake_app) == "light"
    state["scheme"] = Qt.ColorScheme.Unknown
    assert resolve_theme("system", fake_app) == "light"
    assert resolve_theme("invalid", fake_app) == "light"
    assert resolve_theme("light", fake_app) == "light"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_scaled_theme_has_matching_packaged_chevron_and_no_unresolved_colors(qapp, theme):
    import re

    style = scaled_style(150, theme)
    assert not re.search(r"@[A-Z_]+@", style)
    assert "font-size: 20px" in style
    assert PALETTES[theme]["surface"] in style
    paths = re.findall(r'image: url\("([^"]+)"\)', style)
    assert any(path.endswith("chevron-dark.svg" if theme == "dark" else "chevron.svg") for path in paths)
    assert any(path.endswith(f"checkmark-disabled-{theme}.svg") for path in paths)
    for path in paths:
        assert not QIcon(path).pixmap(24, 16).isNull()


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("zoom", [100, 150])
def test_import_spin_arrows_and_checkboxes_keep_their_click_behavior(qtbot, theme, zoom):
    from datadesk.dialogs import ExportDialog, ImportDialog
    from datadesk.io import FileInfo

    importer = ImportDialog("Sales.xlsx", FileInfo(sheets=["Sales"]))
    importer.setStyleSheet(scaled_style(zoom, theme))
    qtbot.addWidget(importer)
    importer.show()
    QApplication.processEvents()
    spin = importer.header
    option = QStyleOptionSpinBox()
    spin.initStyleOption(option)
    for subcontrol, expected in [(QStyle.SC_SpinBoxUp, 2), (QStyle.SC_SpinBoxDown, 1)]:
        bounds = spin.style().subControlRect(QStyle.CC_SpinBox, option, subcontrol, spin)
        assert bounds.height() >= 12
        qtbot.mouseClick(spin, Qt.LeftButton, pos=bounds.center())
        assert spin.value() == expected

    checkbox = importer.no_header
    checkbox_option = QStyleOptionButton()
    checkbox.initStyleOption(checkbox_option)
    indicator = checkbox.style().subElementRect(QStyle.SE_CheckBoxIndicator, checkbox_option, checkbox)
    qtbot.mouseClick(checkbox, Qt.LeftButton, pos=indicator.center())
    assert checkbox.isChecked()
    assert not spin.isEnabled()
    qtbot.mouseClick(spin, Qt.LeftButton, pos=bounds.center())
    assert spin.value() == 1
    qtbot.mouseClick(checkbox, Qt.LeftButton, pos=indicator.center())
    assert not checkbox.isChecked()
    assert spin.isEnabled()
    checkbox.setDisabled(True)
    qtbot.mouseClick(checkbox, Qt.LeftButton, pos=indicator.center())
    assert not checkbox.isChecked()

    exporter = ExportDialog(["ID", "Amount"], 5)
    exporter.setStyleSheet(scaled_style(zoom, theme))
    qtbot.addWidget(exporter)
    exporter.show()
    QApplication.processEvents()
    columns = exporter.columns
    item = columns.item(0)
    view_option = QStyleOptionViewItem()
    view_option.initFrom(columns)
    view_option.rect = columns.visualItemRect(item)
    view_option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    view_option.checkState = item.checkState()
    check_rect = columns.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, view_option, columns)
    qtbot.mouseClick(columns.viewport(), Qt.LeftButton, pos=check_rect.center())
    assert item.checkState() == Qt.CheckState.Unchecked
    assert exporter.selected_columns() == ["Amount"]
    qtbot.mouseClick(columns.viewport(), Qt.LeftButton, pos=check_rect.center())
    assert item.checkState() == Qt.CheckState.Checked
    assert exporter.selected_columns() == ["ID", "Amount"]
    columns.setDisabled(True)
    qtbot.mouseClick(columns.viewport(), Qt.LeftButton, pos=check_rect.center())
    assert item.checkState() == Qt.CheckState.Checked
