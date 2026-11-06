"""Check usable controls and complete data across window sizes and display scales."""

import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event

import pandas as pd
import pytest
from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtWidgets import QApplication

from datadesk import ui
from datadesk.core import FilterRule


@pytest.fixture
def workspace(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(
        ui, "QSettings", lambda *_: QSettings(str(tmp_path / "layout.ini"), QSettings.Format.IniFormat)
    )
    window = ui.MainWindow(workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window, before_close_func=lambda w: setattr(w, "dirty", False))
    window.set_document(
        pd.DataFrame(
            {
                "Müşteri kodu": [f"{i:08d}" for i in range(120)],
                "Müşteri adı": [f"İstanbul müşterisi {i}" for i in range(120)],
                "Tutar": [i * 123.45 for i in range(120)],
            }
        ),
        "Uluslararası satış ve tahsilat raporunun bütün bölgeleri kapsayan uzun dosya adı.xlsx",
    )
    window.show()
    QApplication.processEvents()
    yield window
    window.search_timer.stop()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.dirty = False
    window.close()


def relative_rect(widget, parent):
    return QRect(widget.mapTo(parent, QPoint(0, 0)), widget.size())


def assert_inside(widget, parent):
    assert widget.isVisible(), widget.objectName() or type(widget).__name__
    assert parent.rect().contains(relative_rect(widget, parent)), (
        widget.objectName() or type(widget).__name__,
        relative_rect(widget, parent),
        parent.rect(),
    )


def settle(qtbot, window):
    for _ in range(3):
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not window.busy and not window.tasks, timeout=10000)


def show_filters(qtbot, window):
    if not window.filter_scroll.isVisible():
        qtbot.mouseClick(window.filter_toggle, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
    assert window.filter_scroll.isVisible()


def reach_filter_control(window, control):
    # Let conditional fields finish layout before checking the product's
    # focus/scroll behavior for the complete control and its outline.
    QApplication.processEvents()
    if window.filter_scroll.widget().isAncestorOf(control):
        window.filter_scroll.ensureWidgetVisible(control, 8, 8)
        QApplication.processEvents()
        assert_inside(control, window.filter_scroll.viewport())
    else:
        # Main filter actions stay outside the form's scrolling viewport;
        # verify they are immediately available without any scroll operation.
        assert_inside(control, window.filter_container)
        assert_inside(control, window)


def test_first_window_fits_the_available_desktop(workspace):
    available = workspace.screen().availableGeometry()
    assert workspace.frameGeometry().width() <= available.width()
    assert workspace.frameGeometry().height() <= available.height()


@pytest.mark.parametrize("width,height", [(800, 600), (1024, 768), (1280, 720), (1440, 900), (1920, 1080)])
def test_table_search_and_export_remain_usable_when_window_resizes(qtbot, workspace, width, height):
    workspace.resize(width, height)
    qtbot.wait(20)
    assert workspace.width() <= width
    assert workspace.height() <= height
    assert_inside(workspace.export_button, workspace)
    assert_inside(workspace.search, workspace)
    assert_inside(workspace.add_button, workspace)
    assert_inside(workspace.undo_button, workspace)
    assert workspace.search.width() >= 100
    assert workspace.table.viewport().width() >= 260
    assert workspace.table.viewport().height() >= 120
    assert not relative_rect(workspace.file_label, workspace).intersects(
        relative_rect(workspace.search, workspace)
    )
    assert workspace.model.rowCount() == 120
    assert workspace.model.data(workspace.model.index(119, 0)) == "00000119"


def test_narrow_window_can_add_remove_filters_and_return_to_complete_table(qtbot, workspace):
    workspace.resize(800, 600)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    assert workspace.table_panel.isVisible()
    show_filters(qtbot, workspace)
    assert not workspace.table_panel.isVisible()
    workspace.column.setCurrentText("Tutar")
    workspace.operator.setCurrentIndex(workspace.operator.findData("between"))
    workspace.value.setText("1000")
    workspace.value2.setText("5000")
    for control in (
        workspace.column,
        workspace.operator,
        workspace.value,
        workspace.value2,
        workspace.filter_button,
    ):
        reach_filter_control(workspace, control)
    qtbot.mouseClick(workspace.filter_button, Qt.MouseButton.LeftButton)
    settle(qtbot, workspace)
    assert len(workspace.rules) == 1
    assert workspace.model.rowCount() == 32
    show_filters(qtbot, workspace)
    workspace.filter_tabs.setCurrentIndex(1)
    workspace.rule_list.setCurrentRow(0)
    reach_filter_control(workspace, workspace.remove_button)
    qtbot.mouseClick(workspace.remove_button, Qt.MouseButton.LeftButton)
    settle(qtbot, workspace)
    assert workspace.rules == []
    assert workspace.model.rowCount() == 120
    if not workspace.table_panel.isVisible():
        qtbot.mouseClick(workspace.filter_toggle, Qt.MouseButton.LeftButton)
    assert workspace.table_panel.isVisible()
    assert workspace.export_button.isEnabled()


@pytest.mark.parametrize("zoom", [75, 100, 125, 150])
def test_larger_text_keeps_actions_readable_and_filters_reachable(qtbot, workspace, zoom):
    workspace.resize(1280, 720)
    workspace.set_zoom(zoom)
    qtbot.wait(20)
    assert workspace.zoom_percent == zoom
    assert workspace.width() <= 1280
    assert workspace.height() <= 720
    assert_inside(workspace.export_button, workspace)
    assert_inside(workspace.search, workspace)
    assert_inside(workspace.filter_toggle, workspace)
    assert workspace.search.height() >= workspace.search.fontMetrics().height() + 8
    show_filters(qtbot, workspace)
    workspace.column.setCurrentText("Tutar")
    workspace.operator.setCurrentIndex(workspace.operator.findData("between"))
    workspace.value.setText("1000")
    workspace.value2.setText("5000")
    for control in (
        workspace.column,
        workspace.kind,
        workspace.number_format,
        workspace.operator,
        workspace.value,
        workspace.value2,
        workspace.filter_button,
    ):
        reach_filter_control(workspace, control)
        assert control.height() >= control.fontMetrics().height() + 6
    assert workspace.model.rowCount() == 120


def test_long_headings_and_filename_do_not_push_filter_controls_offscreen(qtbot, workspace):
    heading = "Müşteri fatura ve teslimat kayıtlarının ayrıntılı açıklaması " * 5
    workspace.set_document(
        pd.DataFrame({heading: ["İlk kayıt", "İkinci kayıt"], "Tutar": [1234.56, 2345.67]}),
        "Çok uzun rapor dosyası " * 20 + ".xlsx",
    )
    workspace.resize(800, 600)
    workspace.set_zoom(125)
    qtbot.wait(20)
    show_filters(qtbot, workspace)
    workspace.column.setCurrentText(heading)
    for control in (workspace.column, workspace.operator, workspace.value, workspace.filter_button):
        reach_filter_control(workspace, control)
    assert workspace.column.currentText() == heading
    assert workspace.model.frame.columns.tolist() == [heading, "Tutar"]
    assert_inside(workspace.export_button, workspace)


def test_keyboard_tab_reveals_the_complete_next_filter_field(qtbot, workspace):
    workspace.resize(800, 600)
    workspace.set_zoom(150)
    show_filters(qtbot, workspace)
    workspace.column.setCurrentText("Tutar")
    workspace.operator.setCurrentIndex(workspace.operator.findData("between"))
    workspace.activateWindow()
    workspace.value.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.waitUntil(workspace.value.hasFocus)
    qtbot.keyClick(workspace.value, Qt.Key.Key_Tab)
    qtbot.waitUntil(workspace.value2.hasFocus)
    qtbot.waitUntil(
        lambda: (
            workspace.filter_scroll.viewport()
            .rect()
            .contains(relative_rect(workspace.value2, workspace.filter_scroll.viewport()))
        )
    )
    assert workspace.filter_scroll.verticalScrollBar().value() > 0
    qtbot.keyClicks(workspace.value2, "5000")
    assert workspace.value2.text() == "5000"


@pytest.mark.parametrize("zoom", [100, 150])
def test_filter_action_and_validation_stay_visible_at_both_ends_of_form(qtbot, workspace, zoom):
    workspace.resize(800, 600)
    workspace.set_zoom(zoom)
    show_filters(qtbot, workspace)
    workspace.column.setCurrentText("Tutar")
    workspace.operator.setCurrentIndex(workspace.operator.findData("between"))
    workspace.value.setText("5000")
    workspace.value2.setText("1000")
    QApplication.processEvents()
    scroll = workspace.filter_scroll.verticalScrollBar()
    scroll.setValue(0)
    QApplication.processEvents()
    assert_inside(workspace.filter_button, workspace.filter_container)
    assert_inside(workspace.filter_button, workspace)
    position_at_start = relative_rect(workspace.filter_button, workspace)
    scroll.setValue(scroll.maximum())
    QApplication.processEvents()
    assert_inside(workspace.filter_button, workspace.filter_container)
    assert relative_rect(workspace.filter_button, workspace) == position_at_start
    qtbot.mouseClick(workspace.filter_button, Qt.MouseButton.LeftButton)
    settle(qtbot, workspace)
    assert workspace.filter_error.text()
    assert_inside(workspace.filter_error, workspace.filter_container)
    assert_inside(workspace.filter_error, workspace)
    assert_inside(workspace.filter_button, workspace)
    assert workspace.rules == []
    assert workspace.model.rowCount() == 120
    scroll.setValue(0)
    QApplication.processEvents()
    assert_inside(workspace.filter_error, workspace)
    assert_inside(workspace.filter_button, workspace)


def test_resizing_and_zooming_preserve_filters_raw_values_and_sorted_order(qtbot, workspace):
    workspace.apply_view(rules=[FilterRule("Tutar", "gte", "1000", kind="number")], sort=("Tutar", False))
    settle(qtbot, workspace)
    expected = workspace.model.frame.copy(deep=True)
    source = workspace.document.frame.copy(deep=True)
    for width, height, zoom in [(800, 600, 100), (1024, 768, 125), (1920, 1080, 150), (1440, 900, 100)]:
        workspace.resize(width, height)
        workspace.set_zoom(zoom)
        QApplication.processEvents()
        show_filters(qtbot, workspace)
        pd.testing.assert_frame_equal(workspace.model.frame, expected)
        pd.testing.assert_frame_equal(workspace.document.frame, source)
        assert len(workspace.rules) == 1
        assert workspace.sort_column == "Tutar"


def test_long_import_notice_and_busy_progress_preserve_useful_table_space(qtbot, workspace):
    workspace.resize(800, 600)
    message = "\n".join(
        f"{i}. sayfa: Tarih ve sayı biçimini kontrol edin; kaynak veriler korunuyor." for i in range(80)
    )
    workspace.notice.setText(message)
    workspace.notice.show()
    QApplication.processEvents()
    assert workspace.notice.text() == message
    assert workspace.notice.verticalScrollBar().maximum() > 0
    workspace.notice.verticalScrollBar().setValue(workspace.notice.verticalScrollBar().maximum())
    QApplication.processEvents()
    assert workspace.notice.verticalScrollBar().value() == workspace.notice.verticalScrollBar().maximum()
    assert_inside(workspace.notice, workspace)
    assert workspace.table.viewport().height() >= 120
    assert_inside(workspace.export_button, workspace)
    started, finish = Event(), Event()

    def wait_for_release():
        started.set()
        finish.wait(timeout=5)
        return True

    workspace._run_task("Dosya işleniyor", wait_for_release, lambda _: None)
    try:
        qtbot.waitUntil(started.is_set)
        QApplication.processEvents()
        assert workspace.progress.isVisible()
        assert workspace.table.viewport().height() >= 120
        assert_inside(workspace.search, workspace)
        assert not workspace.export_button.isEnabled()
        assert not workspace.model.editable
        assert workspace.model.rowCount() == 120
    finally:
        finish.set()
        settle(qtbot, workspace)
    assert workspace.export_button.isEnabled()
    assert workspace.model.rowCount() == 120


@pytest.mark.parametrize("scale", ["1", "1.5", "2"])
def test_high_dpi_render_keeps_logical_controls_and_all_rows(scale, tmp_path):
    # Each scale needs a fresh QApplication: Qt consumes this environment setting at startup.
    script = r"""
import json, sys
from pathlib import Path
from PySide6.QtCore import QPoint, QRect, QSettings
from PySide6.QtWidgets import QApplication
from datadesk.theme import configure_app
from datadesk.ui import MainWindow
app = QApplication([])
configure_app(app)
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, sys.argv[1])
w = MainWindow(workspace_root=Path(sys.argv[1]) / "workspace")
w.open_demo()
w.notice.hide()
w.resize(1024, 768)
w.show()
for _ in range(5): app.processEvents()
controls = {}
for name in ('export_button', 'search', 'add_button'):
    obj = getattr(w, name)
    rect = QRect(obj.mapTo(w, QPoint()), obj.size())
    controls[name] = obj.isVisible() and w.rect().contains(rect)
pixmap = w.grab()
print(json.dumps({
    'width': w.width(), 'height': w.height(), 'dpr': w.devicePixelRatioF(),
    'pixel_width': pixmap.width(), 'pixel_height': pixmap.height(),
    'controls': controls, 'rows': w.model.rowCount(),
    'last_id': w.model.data(w.model.index(119, 0)),
}))
w.dirty = False
w.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_SCALE_FACTOR": scale},
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    observed = json.loads(result.stdout.strip().splitlines()[-1])
    assert observed["width"] <= 1024
    assert observed["height"] <= 768
    assert observed["dpr"] == pytest.approx(float(scale))
    assert observed["pixel_width"] == round(observed["width"] * observed["dpr"])
    assert observed["pixel_height"] == round(observed["height"] * observed["dpr"])
    assert all(observed["controls"].values())
    assert observed["rows"] == 120
    assert observed["last_id"] == "DD-00120"
