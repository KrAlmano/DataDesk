"""Real file workflows from the workspace browser through editing and saving."""

from pathlib import Path

import pandas as pd
import pytest
from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit, QMessageBox

from datadesk import ui, workspace_ui
from datadesk.core import FilterRule
from datadesk.io import ExportOptions, read_table
from datadesk.workspace import Workspace


@pytest.fixture
def desk(qtbot, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    window = ui.MainWindow(settings=settings, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "dirty", False))
    window.test_errors = []
    monkeypatch.setattr(window, "show_error", window.test_errors.append)
    window.resize(1100, 760)
    window.show()
    yield window
    window.search_timer.stop()
    QApplication.processEvents()
    qtbot.waitUntil(lambda: not window.busy and not window.tasks, timeout=10000)
    window.dirty = False
    window.close()


def settle(qtbot, window):
    for _ in range(3):
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not window.busy and not window.tasks, timeout=10000)


def add_rows(qtbot, desk):
    desk.document.add({"Kod": "0001", "Tutar": "12,50"})
    desk.document.add({"Kod": "0002", "Tutar": "350,00"})
    desk._after_edit()
    settle(qtbot, desk)


def open_new_table(qtbot, desk, suffix="xlsx", parent=None):
    path = desk.create_workspace_file(parent or desk.workspace.root, "Satışlar", ["Kod", "Tutar"], suffix)
    assert isinstance(path, Path), desk.test_errors
    settle(qtbot, desk)
    return path


@pytest.mark.parametrize("suffix", ["xlsx", "csv", "tsv"])
def test_create_empty_table_edit_save_all_rows_under_filter_and_reopen(qtbot, desk, suffix):
    path = open_new_table(qtbot, desk, suffix)
    assert read_table(path).frame.shape == (0, 2)
    assert desk.document.frame.empty
    assert desk.stack.currentIndex() == 2
    assert desk.no_title.text() == "Tablo henüz boş"
    assert desk.workspace.is_managed(path)
    add_rows(qtbot, desk)
    desk.apply_view(rules=[FilterRule("Kod", "equals", "0002")], sort=("Tutar", False))
    settle(qtbot, desk)
    assert desk.model.frame["Kod"].tolist() == ["0002"]
    assert desk.dirty
    desk.save_document()
    settle(qtbot, desk)
    result = read_table(path).frame
    assert result["Kod"].tolist() == ["0001", "0002"]
    assert result["Tutar"].tolist() == ["12,50", "350,00"]
    assert desk.model.frame["Kod"].tolist() == ["0002"]
    assert not desk.dirty
    assert "*" not in desk.windowTitle()
    assert Workspace(desk.workspace.root).is_managed(path)
    # Opening a DataDesk-created file takes the owned-table route, including
    # after restoring the workspace catalogue from disk.
    desk.workspace = Workspace(desk.workspace.root)
    desk.open_path(path)
    settle(qtbot, desk)
    assert desk.document.frame["Kod"].tolist() == ["0001", "0002"]
    assert desk._can_save_source()
    assert not desk.test_errors


def test_existing_external_source_and_hardlink_are_preserved_on_save(qtbot, desk, tmp_path):
    source = tmp_path / "Dışarıdaki liste.csv"
    source.write_text("Kod;Tutar\n0001;12,50\n", encoding="utf-8")
    original = source.read_bytes()
    desk.load_path(source)
    settle(qtbot, desk)
    assert not desk._can_save_source()
    desk.edit_cell(0, "Tutar", "20,00")
    settle(qtbot, desk)
    assert not desk.save_document_to(source)
    alias = tmp_path / "Aynı kaynak.csv"
    alias.hardlink_to(source)
    assert not desk.save_document_to(alias)
    assert source.read_bytes() == alias.read_bytes() == original
    assert desk.dirty
    assert len(desk.test_errors) == 2
    assert desk.document.frame.at[0, "Tutar"] == "20,00"


def test_saving_to_new_external_destination_can_be_saved_again(qtbot, desk, tmp_path):
    open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    external = tmp_path / "Dışarı kaydedilen.xlsx"
    assert desk.save_document_to(external)
    settle(qtbot, desk)
    assert external.is_file()
    assert desk.source_path == external
    assert not desk.dirty
    assert desk._can_save_source()
    desk.edit_cell(0, "Kod", "0003")
    settle(qtbot, desk)
    desk.save_document()
    settle(qtbot, desk)
    assert read_table(external).frame["Kod"].tolist() == ["0003", "0002"]
    assert not desk.test_errors


def test_rename_and_move_active_file_update_document_and_keep_all_rows(qtbot, desk, monkeypatch):
    source = open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    monkeypatch.setattr(
        workspace_ui.QInputDialog, "getText", lambda *_args, **_kwargs: ("Yeni satışlar.xlsx", True)
    )
    desk.rename_workspace_item(source)
    renamed = source.with_name("Yeni satışlar.xlsx")
    assert desk.source_path == renamed
    assert not source.exists()
    assert renamed.is_file()
    assert desk.dirty
    assert desk._can_save_source()
    destination = desk.workspace.create_folder(".", "Arşiv")
    monkeypatch.setattr(workspace_ui.QFileDialog, "getExistingDirectory", lambda *_args: str(destination))
    desk.move_workspace_item(renamed)
    target = destination / renamed.name
    assert desk.source_path == target
    assert not renamed.exists()
    assert desk._can_save_source()
    desk.apply_view(rules=[FilterRule("Kod", "equals", "0001")])
    settle(qtbot, desk)
    desk.save_document()
    settle(qtbot, desk)
    assert read_table(target).frame["Kod"].tolist() == ["0001", "0002"]
    assert str(target) in desk.settings.value("recent_files", [], type=list)
    assert not desk.test_errors


def test_renaming_parent_folder_keeps_active_descendant_saveable(qtbot, desk, monkeypatch):
    folder = desk.workspace.create_folder(".", "Eski dönem")
    path = open_new_table(qtbot, desk, parent=folder)
    add_rows(qtbot, desk)
    monkeypatch.setattr(workspace_ui.QInputDialog, "getText", lambda *_args, **_kwargs: ("Yeni dönem", True))
    desk.rename_workspace_item(folder)
    target = desk.workspace.root / "Yeni dönem" / path.name
    assert desk.source_path == target
    assert desk._can_save_source()
    assert not path.exists()
    desk.save_document()
    settle(qtbot, desk)
    assert read_table(target).frame["Kod"].tolist() == ["0001", "0002"]
    assert not desk.test_errors


def test_added_column_undo_redo_updates_filter_and_sort_choices(qtbot, desk, monkeypatch):
    open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    monkeypatch.setattr(workspace_ui.QInputDialog, "getText", lambda *_args: ("Açıklama", True))
    desk.add_column()
    settle(qtbot, desk)
    assert list(desk.document.frame.columns) == ["Kod", "Tutar", "Açıklama"]
    assert desk.column.findText("Açıklama") >= 0
    assert "Açıklama" in desk.kinds
    desk.apply_view(rules=[FilterRule("Açıklama", "is_empty")], sort=("Açıklama", True))
    settle(qtbot, desk)
    assert desk.model.rowCount() == 2
    desk.undo()
    settle(qtbot, desk)
    assert list(desk.document.frame.columns) == ["Kod", "Tutar"]
    assert desk.column.findText("Açıklama") == -1
    assert "Açıklama" not in desk.kinds
    assert desk.rules == []
    assert desk.sort_column is None
    assert desk.filter_error.isHidden()
    desk.redo()
    settle(qtbot, desk)
    assert list(desk.model.frame.columns) == ["Kod", "Tutar", "Açıklama"]
    assert desk.column.findText("Açıklama") >= 0
    assert desk.model.frame["Kod"].tolist() == ["0001", "0002"]
    assert not desk.test_errors


def test_files_page_preserves_dirty_document_and_returning_view(qtbot, desk, monkeypatch):
    path = open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    desk.apply_view(rules=[FilterRule("Kod", "equals", "0001")])
    settle(qtbot, desk)
    document = desk.document
    before = desk.model.frame.copy(deep=True)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: pytest.fail("Browsing must keep the active document")
    )
    desk.show_files()
    assert desk.pages.currentIndex() == 0
    assert desk.browser.isVisible()
    assert desk.document is document
    assert desk.source_path == path
    assert desk.dirty
    desk.show_document()
    assert desk.pages.currentIndex() == 1
    pd.testing.assert_frame_equal(desk.model.frame, before)
    assert desk.document is document
    assert desk.dirty


def test_create_folder_from_browser_keeps_dirty_document_and_uses_real_directory(qtbot, desk, monkeypatch):
    open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    document = desk.document
    monkeypatch.setattr(
        workspace_ui.QInputDialog, "getText", lambda *_args: ("Kasım çalışma dosyaları", True)
    )
    desk.show_files()
    desk.browser.new_folder_action.trigger()
    created = desk.workspace.root / "Kasım çalışma dosyaları"
    assert created.is_dir()
    assert desk.browser.current_directory == created
    assert desk.document is document
    assert desk.dirty
    path = desk.create_workspace_file(created, "Tahsilat", ["Müşteri", "Tutar"], "csv")
    settle(qtbot, desk)
    assert path.parent == created
    assert path.is_file()
    assert read_table(path).frame.columns.tolist() == ["Müşteri", "Tutar"]


def test_import_copies_external_file_without_taking_ownership_or_altering_source(qtbot, desk, tmp_path):
    source = tmp_path / "Gelen liste.csv"
    source.write_text("Kod;Tutar\n0001;12,50\n", encoding="utf-8")
    original = source.read_bytes()
    folder = desk.workspace.create_folder(".", "Gelenler")
    desk._copy_workspace_files([source], folder)
    settle(qtbot, desk)
    copied = folder / source.name
    assert copied.read_bytes() == source.read_bytes() == original
    assert desk.browser.current_directory == folder
    assert not desk.workspace.is_managed(copied)
    assert desk.document is None
    assert not desk.test_errors


def test_save_during_pending_search_keeps_all_source_rows_and_finishes_search(qtbot, desk):
    path = open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    desk.search.setText("0002")
    assert desk.search_timer.isActive()
    desk.save_document()
    settle(qtbot, desk)
    assert read_table(path).frame["Kod"].tolist() == ["0001", "0002"]
    assert desk.model.frame["Kod"].tolist() == ["0002"]
    assert desk.search_text == "0002"
    assert not desk.dirty
    assert not desk.test_errors


def test_save_action_commits_the_cell_currently_being_edited(qtbot, desk):
    path = open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    index = desk.model.index(0, 0)
    desk.table.setCurrentIndex(index)
    desk.table.edit(index)
    editors = desk.table.findChildren(QLineEdit)
    assert len(editors) == 1
    editor = editors[0]
    editor.selectAll()
    qtbot.keyClicks(editor, "0012")
    save = next(
        action
        for top in desk.menuBar().actions()
        if top.menu() is not None
        for action in top.menu().actions()
        if action.text() == "Kaydet"
    )
    save.trigger()
    settle(qtbot, desk)
    assert read_table(path).frame["Kod"].tolist() == ["0012", "0002"]
    assert desk.document.frame["Kod"].tolist() == ["0012", "0002"]
    assert not desk.dirty


def test_invalid_native_date_editor_aborts_save_and_keeps_text_available(qtbot, desk):
    path = open_new_table(qtbot, desk)
    date = pd.Timestamp("2026-11-06")
    desk.set_document(pd.DataFrame({"Tarih": [date]}), path.name, path)
    desk.save_document()
    settle(qtbot, desk)
    original = path.read_bytes()
    index = desk.model.index(0, 0)
    desk.table.setCurrentIndex(index)
    desk.table.edit(index)
    editor = desk.table.findChild(QLineEdit)
    editor.selectAll()
    qtbot.keyClicks(editor, "31.02.2026")
    assert not desk.save_document_to(path)
    assert path.read_bytes() == original
    assert desk.document.frame.at[0, "Tarih"] == date
    assert editor.isVisible()
    assert editor.text() == "31.02.2026"
    assert len(desk.test_errors) == 1
    qtbot.keyClick(editor, Qt.Key.Key_Escape)


def test_export_commits_current_editor_and_preserves_unsaved_document_status(qtbot, desk, tmp_path):
    source = open_new_table(qtbot, desk)
    add_rows(qtbot, desk)
    original = source.read_bytes()
    index = desk.model.index(0, 0)
    desk.table.setCurrentIndex(index)
    desk.table.edit(index)
    editor = desk.table.findChild(QLineEdit)
    editor.selectAll()
    qtbot.keyClicks(editor, "0012")
    output = tmp_path / "Düzenlenmiş sonuç.csv"
    desk.export_to(output, ExportOptions(safe_csv=False))
    settle(qtbot, desk)
    assert read_table(output).frame["Kod"].tolist() == ["0012", "0002"]
    assert desk.document.frame["Kod"].tolist() == ["0012", "0002"]
    assert desk.dirty
    assert source.read_bytes() == original
    assert not desk.test_errors


def test_new_table_dialog_rejects_duplicate_headings_then_creates_values(qtbot, desk):
    dialog = workspace_ui.NewTableDialog(desk)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.name.setText("Kasım listesi")
    dialog.columns.setPlainText("Kod\nKod")
    dialog.accept()
    assert dialog.isVisible()
    assert dialog.error.isVisible()
    dialog.columns.setPlainText("Kod\nTutar")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.values() == ("Kasım listesi", "xlsx", ["Kod", "Tutar"])


def test_new_table_dialog_keeps_actions_and_inputs_reachable_at_large_zoom(qtbot, desk):
    desk.resize(800, 600)
    desk.set_zoom(150)
    dialog = workspace_ui.NewTableDialog(desk)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert dialog.width() <= desk.width()
    assert dialog.height() <= desk.height()
    for standard, text in [
        (QDialogButtonBox.StandardButton.Save, "Oluştur"),
        (QDialogButtonBox.StandardButton.Cancel, "Vazgeç"),
    ]:
        button = dialog.buttons.button(standard)
        assert button.isVisible()
        assert button.text() == text
        rect = QRect(button.mapTo(dialog, QPoint(0, 0)), button.size())
        assert dialog.rect().contains(rect)
        assert button.width() >= button.sizeHint().width()
    for control in (dialog.name, dialog.format, dialog.columns):
        dialog.content_scroll.ensureWidgetVisible(control)
        QApplication.processEvents()
        rect = QRect(control.mapTo(dialog.content_scroll.viewport(), QPoint(0, 0)), control.size())
        assert dialog.content_scroll.viewport().rect().contains(rect)
        assert control.width() >= 200
    dialog.content_scroll.verticalScrollBar().setValue(0)
    dialog.activateWindow()
    dialog.format.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.waitUntil(dialog.format.hasFocus)
    qtbot.keyClick(dialog.format, Qt.Key.Key_Tab)
    qtbot.waitUntil(dialog.columns.hasFocus)
    qtbot.waitUntil(
        lambda: (
            dialog.content_scroll.viewport()
            .rect()
            .contains(
                QRect(
                    dialog.columns.mapTo(dialog.content_scroll.viewport(), QPoint(0, 0)),
                    dialog.columns.size(),
                )
            )
        )
    )
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
