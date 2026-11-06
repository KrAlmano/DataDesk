"""Dialog actions and fields stay usable on a small, magnified workspace."""

import re

import pandas as pd
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QWidget

from datadesk.dialogs import ExportDialog, ImportDialog, RowDialog
from datadesk.io import FileInfo, LoadedTable
from datadesk.theme import STYLE, scaled_style


def test_confirmation_buttons_stack_before_their_text_is_clipped(qtbot):
    dialog = ExportDialog(["Kod", "Tutar"], 120)
    dialog.setStyleSheet(scaled_style(200))
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    buttons = dialog.buttons.buttons()
    required = max(button.minimumSizeHint().width() for button in buttons)
    dialog.resize(required + 60, 480)
    QApplication.processEvents()
    assert dialog.buttons.orientation() == Qt.Orientation.Vertical
    for button in buttons:
        assert button.width() >= button.minimumSizeHint().width()
        assert dialog.rect().contains(QRect(button.mapTo(dialog, QPoint()), button.size()))


def magnified_style(scale):
    return re.sub(
        r"([0-9]+(?:\.[0-9]+)?)px",
        lambda match: f"{float(match.group(1)) * scale:g}px",
        STYLE,
    )


def assert_reachable(dialog, widget):
    dialog.content_scroll.ensureWidgetVisible(widget, 8, 8)
    QApplication.processEvents()
    viewport = dialog.content_scroll.viewport()
    bounds = QRect(widget.mapTo(viewport, QPoint()), widget.size())
    # Qt may ensure only a spin box's focus-proxy editor is visible. Check that
    # the complete control can also be exposed using the available scroll range.
    scroll = dialog.content_scroll.verticalScrollBar()
    shift = max(0, bounds.bottom() - viewport.rect().bottom()) + min(0, bounds.top())
    scroll.setValue(scroll.value() + shift)
    QApplication.processEvents()
    bounds = QRect(widget.mapTo(viewport, QPoint()), widget.size())
    assert viewport.rect().contains(bounds), (widget.objectName(), bounds, viewport.rect())
    assert widget.width() >= widget.minimumSizeHint().width()


@pytest.mark.parametrize("scale", [1, 1.25, 1.5, 2])
@pytest.mark.parametrize("kind", ["import", "export", "row"])
def test_small_magnified_dialog_keeps_controls_and_final_actions_reachable(qtbot, scale, kind):
    parent = QWidget()
    parent.resize(800, 600)
    parent.setStyleSheet(magnified_style(scale))
    qtbot.addWidget(parent)
    parent.show()
    columns = [f"Çok uzun müşteri işlem açıklaması {index:02d}" for index in range(35)]
    if kind == "import":
        dialog = ImportDialog(
            "Türkçe müşteri raporu ve uzun açıklamalı dosya adı " * 5 + ".xlsx",
            FileInfo(sheets=["Uzun çalışma sayfası adı" * 6, "Asıl veriler"]),
            LoadedTable(pd.DataFrame([["Değer"] * 35], columns=columns), warnings=["Uyarı metni " * 70]),
            parent=parent,
        )
        controls = [dialog.sheet, dialog.header, dialog.preview_button, dialog.preview]
        accept = QDialogButtonBox.StandardButton.Open
    elif kind == "export":
        dialog = ExportDialog(columns, 100_000, parent=parent)
        controls = [dialog.format, dialog.columns]
        accept = QDialogButtonBox.StandardButton.Save
    else:
        dialog = RowDialog(columns, parent=parent)
        controls = [dialog.entries[columns[0]], dialog.entries[columns[-1]]]
        accept = QDialogButtonBox.StandardButton.Ok
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.resize(640, 480)
    QApplication.processEvents()
    assert dialog.width() == 640
    assert dialog.height() == 480
    assert dialog.content_scroll.horizontalScrollBar().maximum() == 0
    for widget in controls:
        assert_reachable(dialog, widget)
    # The body can move without moving the final confirmation out of sight.
    action = dialog.buttons.button(accept)
    action_bounds = QRect(action.mapTo(dialog, QPoint()), action.size())
    assert dialog.rect().contains(action_bounds)
    assert action.width() >= action.minimumSizeHint().width()
    if kind == "row":
        last = dialog.entries[columns[-1]]
        qtbot.mouseClick(last, Qt.MouseButton.LeftButton)
        qtbot.keyClicks(last, "record 35")
        assert dialog.values()[columns[-1]] == "record 35"
    elif kind == "export":
        dialog.columns.item(0).setCheckState(Qt.CheckState.Unchecked)
        assert dialog.options().columns == columns[1:]
    else:
        dialog.sheet.setCurrentIndex(1)
        dialog.header.setValue(3)
        assert dialog.options().sheet == "Asıl veriler"
        assert dialog.options().header_row == 3


def test_initial_dialog_fits_small_parent_and_available_screen(qtbot):
    parent = QWidget()
    parent.resize(640, 480)
    qtbot.addWidget(parent)
    parent.show()
    dialog = ExportDialog(["Kod", "İşlem"], 10, parent=parent)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert dialog.width() <= parent.width()
    assert dialog.height() <= parent.height()
    screen = dialog.screen().availableGeometry()
    assert dialog.width() < screen.width()
    assert dialog.height() < screen.height()


def test_long_row_headers_wrap_at_field_width_and_last_field_is_editable(qtbot):
    column = "Müşteri açıklaması ve ayrıntılı işlem bilgisi " * 12
    dialog = RowDialog([column, "Son kayıt"])
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.resize(640, 480)
    QApplication.processEvents()
    title = next(label for label in dialog.findChildren(QLabel) if label.text() == column)
    assert title.width() >= dialog.entries[column].width() * 0.9
    assert title.height() < dialog.content_scroll.viewport().height()
    assert_reachable(dialog, dialog.entries["Son kayıt"])
    dialog.entries["Son kayıt"].setText("Korunan değer")
    assert dialog.values()["Son kayıt"] == "Korunan değer"


def test_export_shows_only_the_options_relevant_to_selected_format(qtbot):
    dialog = ExportDialog(["Kod", "Ad"], 100)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.encoding.isHidden()
    assert dialog.delimiter.isHidden()
    assert dialog.safe_csv.isHidden()
    dialog.format.setCurrentIndex(dialog.format.findData(".csv"))
    assert not dialog.encoding.isHidden()
    assert not dialog.delimiter.isHidden()
    assert not dialog.safe_csv.isHidden()
    dialog.format.setCurrentIndex(dialog.format.findData(".tsv"))
    assert not dialog.encoding.isHidden()
    assert dialog.delimiter.isHidden()
    assert dialog.options().delimiter == "\t"
