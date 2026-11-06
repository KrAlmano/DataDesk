"""Saving a working table and exporting a result have different safety contracts."""

from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from datadesk import ui, workspace_ui
from datadesk.io import ExportOptions, ImportOptions, read_table, write_table
from datadesk.workspace import MANIFEST_NAME, Workspace


@pytest.fixture
def editor(qtbot, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "safety.ini"), QSettings.Format.IniFormat)
    window = ui.MainWindow(settings=settings, workspace_root=tmp_path / "Çalışma alanı")
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "dirty", False))
    window.test_errors = []
    monkeypatch.setattr(window, "show_error", window.test_errors.append)
    yield window
    window.search_timer.stop()
    QApplication.processEvents()
    qtbot.waitUntil(lambda: not window.busy and not window.tasks, timeout=10000)
    window.dirty = False
    window.close()


def settle(qtbot, editor):
    for _ in range(3):
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not editor.busy and not editor.tasks, timeout=10000)


def working_table(qtbot, editor):
    path = editor.create_workspace_file(editor.workspace.root, "Rapor", ["Kod", "Ad"], "csv")
    settle(qtbot, editor)
    editor.document.add({"Kod": "0001", "Ad": "İlk kayıt"})
    editor._after_edit()
    settle(qtbot, editor)
    return path


@pytest.mark.parametrize("suffix", [".xlsx", ".csv", ".tsv", ".docx"])
def test_exporting_all_rows_and_columns_keeps_source_edits_unsaved(qtbot, editor, tmp_path, suffix):
    source = working_table(qtbot, editor)
    original = source.read_bytes()
    document = editor.document
    output = tmp_path / f"Sonuç{suffix}"
    editor.export_to(output, ExportOptions(columns=["Kod", "Ad"]))
    settle(qtbot, editor)
    assert output.is_file()
    assert source.read_bytes() == original
    assert read_table(source).frame.empty
    assert editor.document is document
    assert editor.document.frame["Kod"].tolist() == ["0001"]
    assert editor.dirty
    assert "*" in editor.windowTitle()
    assert editor.source_path == source
    assert not editor.test_errors


@pytest.mark.parametrize("destination_kind", ["source", "existing_save_as", "new_save_as"])
def test_external_file_change_while_staging_save_preserves_external_data_and_dirty_editor(
    qtbot, editor, tmp_path, monkeypatch, destination_kind
):
    source = working_table(qtbot, editor)
    if destination_kind == "source":
        destination = source
    else:
        destination = tmp_path / "Başka dosya.csv"
        if destination_kind == "existing_save_as":
            write_table(pd.DataFrame({"Harici": ["önceki değer"]}), destination)
    document = editor.document
    original_writer = workspace_ui.write_table
    external_data = "Harici\nExcel ile dışarıdan kaydedildi\n".encode("utf-8")

    def change_target_after_staging(frame, staged, options):
        assert Path(staged) != destination
        result = original_writer(frame, staged, options)
        destination.write_bytes(external_data)
        return result

    monkeypatch.setattr(workspace_ui, "write_table", change_target_after_staging)
    assert editor.save_document_to(destination)
    settle(qtbot, editor)
    assert destination.read_bytes() == external_data
    assert editor.source_path == source
    assert editor.document is document
    assert editor.document.frame["Kod"].tolist() == ["0001"]
    assert editor.dirty
    assert len(editor.test_errors) == 1
    assert "başka bir uygulamada değişti" in editor.test_errors[0]
    assert not list(destination.parent.glob(".datadesk-save-*"))
    assert not editor.busy


@pytest.mark.parametrize("suffix,title", [(".xlsx", "Excel"), (".csv", "CSV"), (".tsv", "TSV")])
def test_suffixless_save_as_asks_about_final_existing_path_and_cancel_preserves_it(
    qtbot, editor, tmp_path, monkeypatch, suffix, title
):
    source = working_table(qtbot, editor)
    destination = tmp_path / f"Önemli dosya{suffix}"
    write_table(pd.DataFrame({"Asıl": ["Kalsın"]}), destination)
    original = destination.read_bytes()
    monkeypatch.setattr(
        workspace_ui.QFileDialog,
        "getSaveFileName",
        lambda *_: (str(destination.with_suffix("")), f"{title} (*{suffix})"),
    )
    confirmations = []

    def reject_overwrite(*arguments):
        confirmations.append(arguments)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(workspace_ui.QMessageBox, "question", reject_overwrite)
    editor.save_document_as()
    settle(qtbot, editor)
    assert len(confirmations) == 1
    assert destination.name in confirmations[0][2]
    assert confirmations[0][-1] == QMessageBox.StandardButton.No
    assert destination.read_bytes() == original
    assert editor.source_path == source
    assert editor.dirty
    assert not editor.test_errors


def test_suffixless_save_as_can_replace_final_path_after_explicit_confirmation(
    qtbot, editor, tmp_path, monkeypatch
):
    working_table(qtbot, editor)
    destination = tmp_path / "Kaydedilen.xlsx"
    write_table(pd.DataFrame({"Asıl": ["önceki dosya"]}), destination)
    monkeypatch.setattr(
        workspace_ui.QFileDialog,
        "getSaveFileName",
        lambda *_: (str(destination.with_suffix("")), "Excel (*.xlsx)"),
    )
    monkeypatch.setattr(workspace_ui.QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    editor.save_document_as()
    settle(qtbot, editor)
    assert editor.source_path == destination
    assert read_table(destination).frame["Kod"].tolist() == ["0001"]
    assert not editor.dirty
    assert editor._can_save_source()
    assert not editor.test_errors


def test_copied_multisheet_workbook_remains_untouched_when_selected_sheet_is_saved_elsewhere(
    qtbot, editor, tmp_path
):
    external = tmp_path / "Excel çalışma kitabı.xlsx"
    book = Workbook()
    book.active.title = "Özet"
    book.active.append(["Toplam"])
    book.active.append(["=SUM(İşlemler!B2:B3)"])
    rows = book.create_sheet("İşlemler")
    rows.append(["Kod", "Tutar"])
    rows.append(["0001", 12])
    rows.append(["0002", 20])
    book.save(external)
    book.close()
    original = external.read_bytes()
    copied = editor.workspace.import_files([external])[0]
    editor.load_path(copied, ImportOptions(sheet="İşlemler"))
    settle(qtbot, editor)
    assert editor.document.frame["Kod"].tolist() == ["0001", "0002"]
    assert not editor._can_save_source()
    editor.edit_cell(0, "Tutar", "99")
    settle(qtbot, editor)
    assert not editor.save_document_to(copied)
    assert copied.read_bytes() == external.read_bytes() == original
    destination = editor.workspace.root / "İşlemler çalışma kopyası.xlsx"
    assert editor.save_document_to(destination)
    settle(qtbot, editor)
    assert copied.read_bytes() == external.read_bytes() == original
    assert read_table(destination).frame["Tutar"].tolist() == [99, 20]
    assert editor.workspace.is_managed(destination)
    assert len(editor.test_errors) == 1


def test_switching_workspace_keeps_dirty_document_and_existing_files(qtbot, editor, tmp_path):
    source = working_table(qtbot, editor)
    original = source.read_bytes()
    document = editor.document
    destination = tmp_path / "Başka çalışma alanı"
    destination.mkdir()
    unrelated = destination / source.name
    unrelated.write_text("Harici\nDokunma\n", encoding="utf-8")
    unrelated_data = unrelated.read_bytes()
    assert editor.set_workspace_root(destination)
    assert editor.document is document
    assert editor.source_path == source
    assert editor.dirty
    assert editor.browser.current_directory == destination
    assert not editor.workspace.is_managed(unrelated)
    assert source.read_bytes() == original
    assert unrelated.read_bytes() == unrelated_data


def test_successful_save_survives_manifest_permission_failure(qtbot, editor, monkeypatch):
    source = working_table(qtbot, editor)
    document = editor.document
    original_replace = workspace_ui.os.replace
    replacements = []
    initial_identity = workspace_ui._identity(source)
    assert editor.document.frame["Kod"].tolist() == ["0001"]
    assert not editor.busy and not editor.tasks
    assert editor._can_save_source(), {
        "source": str(source),
        "identity": initial_identity,
        "managed": editor.workspace._managed,
        "warning": editor.workspace.metadata_warning,
    }

    def fail_metadata(source_path, destination_path):
        replacements.append((str(source_path), str(destination_path)))
        if Path(destination_path).name == MANIFEST_NAME:
            raise PermissionError("metadata is read-only")
        return original_replace(source_path, destination_path)

    monkeypatch.setattr(workspace_ui.os, "replace", fail_metadata)
    editor.save_document()
    assert editor.busy and editor.tasks, {
        "errors": editor.test_errors,
        "dirty": editor.dirty,
        "identity": workspace_ui._identity(source),
        "initial_identity": initial_identity,
    }
    settle(qtbot, editor)
    assert not editor.test_errors, {
        "errors": editor.test_errors,
        "replacements": replacements,
        "status": editor.statusBar().currentMessage(),
        "identity": workspace_ui._identity(source),
        "initial_identity": initial_identity,
    }
    assert not editor.dirty, {"replacements": replacements, "status": editor.statusBar().currentMessage()}
    assert editor.document is document
    assert editor.source_path == source
    assert read_table(source).frame["Kod"].tolist() == ["0001"]
    assert not editor.dirty
    assert editor.workspace.metadata_warning
    assert editor._can_save_source()
    assert not Workspace(editor.workspace.root).is_managed(source)
    assert not editor.test_errors
