"""Exercise asynchronous user workflows with a real Qt event loop."""

from threading import Event

import pandas as pd
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from datadesk import ui
from datadesk.core import FilterRule
from datadesk.dialogs import ExportDialog, ImportDialog
from datadesk.io import ExportOptions, FileInfo, LoadedTable, read_table


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    # Never read or modify the user's actual recent files/preferences.
    monkeypatch.setattr(
        ui, "QSettings", lambda *_: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    widget = ui.MainWindow()
    qtbot.addWidget(widget, before_close_func=lambda w: setattr(w, "dirty", False))
    widget.test_errors = []
    monkeypatch.setattr(widget, "show_error", widget.test_errors.append)
    yield widget
    widget.search_timer.stop()
    QApplication.processEvents()
    qtbot.waitUntil(lambda: not widget.busy, timeout=10000)
    widget.dirty = False
    widget.close()


def settle(qtbot, window):
    # Flush deferred editor refreshes before checking the background task.
    for _ in range(3):
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not window.busy and not window.tasks, timeout=10000)


def sales_frame():
    return pd.DataFrame(
        {
            "Kod": ["0001", "0002", "0003", "0004", "0005"],
            "Ad": ["Ali", "Ece", "Can", "Bora", "Deniz"],
            "Şehir": ["İstanbul", "Ankara", "İstanbul", "İstanbul", "İzmir"],
            "Tutar": ["15,5", "200", "100", "5", "50"],
        }
    )


def test_filter_sort_edit_clear_keeps_correct_source_row_and_undo(qtbot, window):
    original = sales_frame()
    window.set_document(original, "Satışlar")
    rule = FilterRule("Şehir", "equals", "istanbul")
    window.apply_view(rules=[rule], sort=("Tutar", True))
    settle(qtbot, window)
    assert window.model.frame["Kod"].tolist() == ["0004", "0001", "0003"]
    assert window.model.setData(window.model.index(0, 1), "Bora güncel")
    settle(qtbot, window)
    assert window.document.frame.loc[3, "Ad"] == "Bora güncel"
    assert window.document.frame.loc[0, "Ad"] == "Ali"
    window.reset_view()
    settle(qtbot, window)
    assert len(window.model.frame) == 5
    assert window.model.frame.loc[3, "Ad"] == "Bora güncel"
    assert window.rules == []
    window.undo()
    settle(qtbot, window)
    pd.testing.assert_frame_equal(window.document.frame, original)
    window.redo()
    settle(qtbot, window)
    assert window.document.frame.loc[3, "Ad"] == "Bora güncel"


def test_delete_in_filtered_sorted_view_undo_does_not_delete_other_row(qtbot, window, monkeypatch):
    window.set_document(sales_frame(), "Satışlar")
    window.apply_view(rules=[FilterRule("Şehir", "equals", "istanbul")], sort=("Tutar", False))
    settle(qtbot, window)
    assert window.model.frame.index.tolist() == [2, 0, 3]
    window.table.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    window.delete_rows()
    settle(qtbot, window)
    assert 2 not in window.document.frame.index
    assert window.document.frame.loc[0, "Kod"] == "0001"
    window.undo()
    settle(qtbot, window)
    assert window.document.frame.loc[2, "Kod"] == "0003"
    assert window.model.frame.index.tolist() == [2, 0, 3]


@pytest.mark.parametrize("extension", [".xlsx", ".csv", ".tsv"])
def test_async_export_contains_complete_filtered_sort_and_selected_columns(
    qtbot, window, tmp_path, extension
):
    frame = pd.concat([sales_frame()] * 50, ignore_index=True)
    window.set_document(frame, "Satışlar")
    window.apply_view(rules=[FilterRule("Şehir", "equals", "istanbul")], sort=("Tutar", False))
    settle(qtbot, window)
    path = tmp_path / ("sonuç" + extension)
    window.export_to(path, ExportOptions(columns=["Tutar", "Kod"], safe_csv=False))
    settle(qtbot, window)
    result = read_table(path).frame
    assert result.columns.tolist() == ["Tutar", "Kod"]
    assert len(result) == 150
    assert result["Kod"].tolist() == window.model.frame["Kod"].tolist()
    assert result["Tutar"].tolist() == window.model.frame["Tutar"].tolist()
    assert not window.test_errors


def test_zero_results_export_keeps_headers(qtbot, window, tmp_path):
    window.set_document(sales_frame(), "Satışlar")
    window.apply_view(rules=[FilterRule("Şehir", "equals", "Yok")])
    settle(qtbot, window)
    assert window.model.rowCount() == 0
    assert window.export_button.isEnabled()
    path = tmp_path / "boş.xlsx"
    window.export_to(path, ExportOptions(columns=["Kod", "Ad"]))
    settle(qtbot, window)
    frame = read_table(path).frame
    assert frame.shape == (0, 2)
    assert frame.columns.tolist() == ["Kod", "Ad"]


def test_export_flushes_search_debounce_before_writing(qtbot, window, tmp_path):
    window.set_document(sales_frame(), "Satışlar")
    window.search.setText("Bora")
    assert window.search_timer.isActive()
    path = tmp_path / "hemen.csv"
    window.export_to(path, ExportOptions(columns=["Kod", "Ad"]))
    settle(qtbot, window)
    qtbot.waitUntil(path.is_file)
    result = read_table(path).frame
    assert result["Kod"].tolist() == ["0004"]
    assert window.search_text == "Bora"
    assert not window.test_errors


def test_failed_import_resumes_pending_search(qtbot, window, tmp_path):
    window.set_document(sales_frame(), "Satışlar")
    window.search.setText("Ali")
    assert window.search_timer.isActive()
    window.load_path(tmp_path / "olmayan.xlsx")
    settle(qtbot, window)
    qtbot.waitUntil(lambda: not window.busy and window.search_text == "Ali")
    assert window.model.frame["Kod"].tolist() == ["0001"]
    assert len(window.test_errors) == 1


def test_failed_import_keeps_document_filters_sort_and_source(qtbot, window, tmp_path):
    window.set_document(sales_frame(), "Satışlar", tmp_path / "kaynak.xlsx")
    rule = FilterRule("Şehir", "equals", "istanbul")
    window.apply_view(rules=[rule], sort=("Tutar", False))
    settle(qtbot, window)
    before = window.model.frame.copy(deep=True)
    document = window.document
    window.load_path(tmp_path / "bulunamayan.xlsx")
    settle(qtbot, window)
    assert window.document is document
    assert window.rules == [rule]
    assert window.sort_column == "Tutar"
    assert window.source_path == (tmp_path / "kaynak.xlsx").resolve()
    pd.testing.assert_frame_equal(window.model.frame, before)
    assert len(window.test_errors) == 1


def test_new_import_clears_all_stale_view_state(qtbot, window, tmp_path):
    window.set_document(sales_frame(), "Satışlar")
    window.search.setText("Ali")
    window.apply_view(rules=[FilterRule("Şehir", "equals", "istanbul")], match="any", sort=("Tutar", False))
    settle(qtbot, window)
    path = tmp_path / "yenisi.csv"
    path.write_text("Başka;Değer\nİlk;12\nİkinci;20\n", encoding="utf-8")
    window.load_path(path)
    settle(qtbot, window)
    assert window.rules == []
    assert window.match == "all"
    assert window.search.text() == window.search_text == ""
    assert window.sort_column is None
    assert window.rule_list.count() == 0
    assert window.model.frame.columns.tolist() == ["Başka", "Değer"]
    assert len(window.model.frame) == 2


def test_invalid_filter_is_not_committed_and_previous_view_remains(qtbot, window):
    window.set_document(sales_frame(), "Satışlar")
    rule = FilterRule("Şehir", "equals", "istanbul")
    window.apply_view(rules=[rule])
    settle(qtbot, window)
    before = window.model.frame.copy(deep=True)
    window.apply_view(rules=[rule, FilterRule("Tutar", "between", "100", "5", kind="number")])
    settle(qtbot, window)
    assert window.rules == [rule]
    pd.testing.assert_frame_equal(window.model.frame, before)
    assert not window.filter_error.isHidden()
    assert window.filter_error.text()


def test_typed_edit_preserves_native_boolean_date_and_large_integer(qtbot, window):
    from datetime import datetime

    frame = pd.DataFrame({"Onay": [True], "Tarih": [datetime(2026, 11, 6)], "Kimlik": [123456789012345678]})
    window.set_document(frame, "Türler")
    assert window.edit_cell(0, "Onay", "Hayır")
    settle(qtbot, window)
    assert pd.api.types.is_bool(window.document.frame.at[0, "Onay"])
    assert not window.document.frame.at[0, "Onay"]
    assert window.edit_cell(0, "Tarih", "07.11.2026")
    settle(qtbot, window)
    assert window.document.frame.at[0, "Tarih"] == pd.Timestamp("2026-11-07")
    assert window.edit_cell(0, "Kimlik", "123456789012345679")
    settle(qtbot, window)
    assert window.document.frame.at[0, "Kimlik"] == 123456789012345679
    assert not window.edit_cell(0, "Tarih", "31.02.2026")
    assert window.document.frame.at[0, "Tarih"] == pd.Timestamp("2026-11-07")
    assert window.test_errors


def test_add_row_parses_native_types_and_keeps_identifier_then_undo(qtbot, window, monkeypatch):
    original = pd.DataFrame(
        {"Kod": ["0001"], "Tutar": [12.5], "Tarih": [pd.Timestamp("2026-11-06")], "Onay": [True]}
    )
    window.set_document(original, "Türler")

    class AcceptedRow:
        def __init__(self, *_):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return {"Kod": "0002", "Tutar": "1.234,50", "Tarih": "07.11.2026", "Onay": "Hayır"}

    monkeypatch.setattr(ui, "RowDialog", AcceptedRow)
    window.add_row()
    settle(qtbot, window)
    added = window.document.frame.iloc[-1]
    assert added["Kod"] == "0002"
    assert added["Tutar"] == 1234.5
    assert added["Tarih"] == pd.Timestamp("2026-11-07")
    assert pd.api.types.is_bool(added["Onay"])
    assert not added["Onay"]
    window.undo()
    settle(qtbot, window)
    pd.testing.assert_frame_equal(window.document.frame, original)


def test_turkish_number_mode_applies_to_filter_and_column_sort(qtbot, window):
    window.set_document(
        pd.DataFrame({"Kod": ["A", "B", "C"], "Tutar": ["1.234", "20", "3,50"]}), "Türkçe sayılar"
    )
    window.column.setCurrentText("Tutar")
    window.number_format.setCurrentIndex(window.number_format.findData("tr"))
    window.operator.setCurrentIndex(window.operator.findData("gt"))
    window.value.setText("100")
    window.add_filter()
    settle(qtbot, window)
    assert window.rules[0].number_format == "tr"
    assert window.model.frame["Kod"].tolist() == ["A"]
    window.reset_view()
    settle(qtbot, window)
    window.sort_by(1)
    settle(qtbot, window)
    assert window.model.frame["Kod"].tolist() == ["C", "B", "A"]
    window.number_format.setCurrentIndex(window.number_format.findData("auto"))
    settle(qtbot, window)
    assert window.model.frame["Kod"].tolist() == ["A", "C", "B"]


def test_close_during_background_task_is_deferred_until_safe(qtbot, window):
    started, finish = Event(), Event()
    result = []

    def work():
        started.set()
        finish.wait(timeout=5)
        return "tamam"

    window.show()
    window._run_task("Bekleniyor", work, result.append)
    qtbot.waitUntil(started.is_set)
    assert window.busy
    assert window.close() is False
    assert window.isVisible()
    finish.set()
    settle(qtbot, window)
    assert result == ["tamam"]
    assert window.close() is True


def test_worker_exception_without_message_is_still_failure(qtbot, window):
    successes = []

    def fail():
        raise ValueError()

    window._run_task("Hata denemesi", fail, successes.append)
    settle(qtbot, window)
    assert successes == []
    assert window.test_errors


def test_export_rejects_source_and_hardlink(qtbot, window, tmp_path):
    source = tmp_path / "kaynak.csv"
    source.write_text("A\nkorunacak\n", encoding="utf-8")
    alias = tmp_path / "aynı-dosya.csv"
    alias.hardlink_to(source)
    before = source.read_bytes()
    window.set_document(sales_frame(), "Kaynak", source)
    for output in (source, alias):
        window.export_to(output)
        settle(qtbot, window)
        assert source.read_bytes() == before
        assert not window.busy
    assert len(window.test_errors) == 2


def test_export_dialog_selects_order_and_rejects_no_columns(qtbot):
    dialog = ExportDialog(["A", "B", "C"], 200)
    qtbot.addWidget(dialog)
    item = dialog.columns.takeItem(2)
    dialog.columns.insertItem(0, item)
    dialog.columns.item(2).setCheckState(Qt.CheckState.Unchecked)
    assert dialog.options().columns == ["C", "A"]
    dialog.check_all(Qt.CheckState.Unchecked)
    dialog.validate()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert not dialog.error.isHidden()


def test_import_preview_options_and_busy_controls(qtbot, tmp_path):
    dialog = ImportDialog(
        tmp_path / "rapor.xlsx", FileInfo(sheets=["Özet", "Veriler"]), LoadedTable(sales_frame())
    )
    qtbot.addWidget(dialog)
    dialog.sheet.setCurrentIndex(1)
    dialog.header.setValue(3)
    options = dialog.options()
    assert options.sheet == "Veriler"
    assert options.header_row == 3
    dialog.no_header.setChecked(True)
    assert dialog.options().header_row is None
    assert dialog.preview_model.rowCount() == 5
    dialog.set_busy(True)
    assert not dialog.sheet.isEnabled()
    assert not dialog.no_header.isEnabled()
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Open).isEnabled()
    dialog.set_busy(False)
    assert dialog.sheet.isEnabled()
