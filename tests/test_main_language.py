"""Exercise the English table workflow without translating document content."""

import pandas as pd
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog

from datadesk import ui
from datadesk.i18n import language, render_text, set_language, tr
from datadesk.io import read_table


@pytest.fixture
def english_window(qtbot, tmp_path, monkeypatch):
    previous = language()
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui_language", "en")
    settings.setValue("ui_theme", "light")
    set_language("en")
    window = ui.MainWindow(settings=settings, workspace_root=tmp_path / "Dosyalar")
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "dirty", False))
    window.test_errors = []
    monkeypatch.setattr(window, "show_error", window.test_errors.append)
    window.show()
    yield window
    window.search_timer.stop()
    settle(qtbot, window)
    window.dirty = False
    window.close()
    set_language(previous)


def settle(qtbot, window):
    for _ in range(3):
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not window.busy and not window.tasks, timeout=10000)


def test_english_controls_menus_placeholders_and_data_type_choices(english_window):
    window = english_window
    assert window.files_button.text() == "Files"
    assert window.open_button.text() == "Open file…"
    assert window.export_button.text() == "Export"
    assert window.save_button.text() == "Save"
    assert window.page_tabs.tabText(0) == "Files"
    assert window.search.placeholderText() == "Search all columns…"
    assert window.value.placeholderText() == "Enter a value…"
    assert window.kind.itemText(window.kind.findData("number")) == "Treat as number"
    assert window.operator.itemText(window.operator.findData("not_empty")) == "Is not empty"
    assert window.match_combo.currentText() == "Match all (AND)"
    assert window.zoom_label.text() == "100%"
    menus = {action.text(): action.menu() for action in window.menuBar().actions()}
    assert {"File", "Edit", "View", "Help"} <= set(menus)
    assert "Save as…" in [action.text() for action in menus["File"].actions()]
    assert "Open sample data" in [action.text() for action in menus["File"].actions()]


def test_filter_action_localizes_descriptions_and_counts_but_keeps_data(qtbot, english_window):
    window = english_window
    original = pd.DataFrame({"Ad": ["Yeni tablo", "Dosyalar"], "Sütunlar": ["0001", "0002"]})
    window.set_document(original, "Dosyalar")
    assert window.title_label.text() == "Dosyalar"
    assert window.column.currentText() == "Ad"
    assert window.type_label.text() == "Detected type: Text"
    window.operator.setCurrentIndex(window.operator.findData("equals"))
    window.value.setText("Yeni tablo")
    window.filter_button.click()
    settle(qtbot, window)
    assert window.model.frame["Ad"].tolist() == ["Yeni tablo"]
    assert window.model.frame.columns.tolist() == ["Ad", "Sütunlar"]
    assert window.rule_list.item(0).text() == "Ad\nEquals Yeni tablo"
    assert window.rule_list.item(0).toolTip() == (
        "Ad\nEquals Yeni tablo\nType: Text · Number format: Automatic"
    )
    assert window.filter_tabs.tabText(1) == "Active (1)"
    assert window.compact_summary.text() == "Rows: 1 / 2 · Columns: 2 · Filters: 1"
    pd.testing.assert_frame_equal(window.document.frame, original)
    assert not window.test_errors


@pytest.mark.parametrize("text,expected", [("yes", True), ("no", False), ("YES", True), ("No", False)])
def test_boolean_cell_edit_accepts_english_answers(qtbot, english_window, text, expected):
    window = english_window
    window.set_document(pd.DataFrame({"Ad": [not expected]}), "Dosyalar")
    assert window.edit_cell(0, "Ad", text)
    settle(qtbot, window)
    assert bool(window.document.frame.at[0, "Ad"]) is expected
    assert not window.test_errors
    assert not window.edit_cell(0, "Ad", "maybe")
    assert window.test_errors == ["Enter Yes / No or True / False."]
    assert bool(window.document.frame.at[0, "Ad"]) is expected


@pytest.mark.parametrize("text,expected", [("Yes", True), ("No", False)])
def test_add_row_accepts_english_boolean_values(qtbot, english_window, monkeypatch, text, expected):
    class EnteredRow:
        def __init__(self, *_args):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return {"Ad": text}

    window = english_window
    window.set_document(pd.DataFrame({"Ad": [True]}), "Dosyalar")
    monkeypatch.setattr(ui, "RowDialog", EnteredRow)
    window.add_row()
    settle(qtbot, window)
    assert len(window.document.frame) == 2
    assert bool(window.document.frame.at[1, "Ad"]) is expected
    assert not window.test_errors


def test_export_notice_is_english_and_actual_values_survive(qtbot, english_window, tmp_path):
    window = english_window
    frame = pd.DataFrame({"Ad": ["Yeni tablo"], "Sütunlar": ["0001"]}, dtype=object)
    window.set_document(frame, "Dosyalar")
    output = tmp_path / "Dosyalar.csv"
    window.export_to(output)
    settle(qtbot, window)
    assert window.notice.text() == f"Export saved · Rows: 1\n{output}"
    assert window.statusBar().currentMessage() == f"Saved: {output}"
    pd.testing.assert_frame_equal(read_table(output).frame, frame)
    assert not window.test_errors


def test_background_errors_retain_translation_metadata(qapp):
    previous = language()
    set_language("en")
    try:
        message = tr("Evet / Hayır veya True / False girin.")

        def fail():
            raise ValueError(message)

        task = ui.Task(7, fail)
        results = []
        task.signals.finished.connect(lambda *args: results.append(args))
        task.run()
        assert len(results) == 1
        assert results[0][0:2] == (7, None)
        assert results[0][2] is message
        set_language("tr")
        assert render_text(results[0][2]) == "Evet / Hayır veya True / False girin."
    finally:
        set_language(previous)
