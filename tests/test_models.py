"""Regression checks for source identities and reversible edits."""

from datetime import datetime

import pandas as pd
from PySide6.QtCore import QModelIndex, Qt

from datadesk.models import Document, TableModel


def test_document_edit_delete_add_undo_redo_preserves_source_identity():
    source = pd.DataFrame({"Kod": ["001", "002", "003"], "Tutar": [10, 20, 30]}, index=[10, 20, 30])
    doc = Document(source.copy(deep=True))
    doc.edit(20, "Tutar", 25)
    doc.delete([10])
    doc.add({"Kod": "004", "Tutar": 40})
    assert doc.frame.index.tolist() == [20, 30, 31]
    assert doc.frame.loc[20, "Tutar"] == 25
    assert doc.frame.loc[30, "Kod"] == "003"
    assert doc.frame.loc[31, "Kod"] == "004"
    added = doc.frame.copy(deep=True)
    doc.undo()
    assert doc.frame.index.tolist() == [20, 30]
    doc.undo()
    assert doc.frame.index.tolist() == [10, 20, 30]
    doc.undo()
    pd.testing.assert_frame_equal(doc.frame, source)
    doc.redo()
    doc.redo()
    doc.redo()
    pd.testing.assert_frame_equal(doc.frame, added)


def test_new_edit_after_undo_clears_redo_and_keeps_unedited_types():
    stamp = datetime(2026, 11, 6, 12, 30)
    doc = Document(pd.DataFrame({"Tarih": [stamp], "Kod": ["0001"], "Tutar": [20]}))
    doc.edit(0, "Tutar", 21)
    doc.undo()
    assert doc.future
    doc.edit(0, "Tutar", 22)
    assert not doc.future
    assert doc.frame.loc[0, "Tarih"] == stamp
    assert doc.frame.loc[0, "Kod"] == "0001"
    doc.redo()
    assert doc.frame.loc[0, "Tutar"] == 22


def test_history_is_bounded_to_ten_complete_edits():
    doc = Document(pd.DataFrame({"A": [0]}))
    for value in range(1, 15):
        doc.edit(0, "A", value)
    assert len(doc.history) == 10
    for _ in range(20):
        doc.undo()
    assert doc.frame.loc[0, "A"] == 4


def test_table_model_edits_original_row_after_filter_and_sort(qapp):
    doc = Document(pd.DataFrame({"Ad": ["Ali", "Ece", "Can"], "Tutar": [30, 10, 20]}, index=[4, 8, 12]))
    calls = []

    def edit(row, column, value):
        calls.append((row, column, value))
        doc.edit(row, column, value)
        return True

    model = TableModel(edit)
    model.replace(doc.frame.loc[[12, 4]])
    assert model.rowCount() == 2
    assert model.columnCount() == 2
    assert model.rowCount(model.index(0, 0)) == 0
    assert model.columnCount(model.index(0, 0)) == 0
    assert model.setData(model.index(0, 0), "Can güncel")
    assert calls == [(12, "Ad", "Can güncel")]
    assert doc.frame.loc[12, "Ad"] == "Can güncel"
    assert doc.frame.loc[4, "Ad"] == "Ali"
    assert not model.setData(QModelIndex(), "Geçersiz")
    model.editable = False
    assert not model.setData(model.index(1, 0), "Değişmez")
    assert not (model.flags(model.index(1, 0)) & Qt.ItemFlag.ItemIsEditable)


def test_table_model_formats_values_without_mutating_source(qapp):
    frame = pd.DataFrame({"Kod": ["00001", "NA", "null", None], "Tutar": [0, 1.5, None, 4]})
    before = frame.copy(deep=True)
    model = TableModel(lambda *_: False)
    model.replace(frame)
    assert [model.data(model.index(i, 0)) for i in range(4)] == ["00001", "NA", "null", ""]
    assert model.data(model.index(2, 1)) == ""
    assert model.headerData(0, Qt.Orientation.Horizontal) == "Kod"
    pd.testing.assert_frame_equal(frame, before)
