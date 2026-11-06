"""Language choices translate controls while preserving user files and values."""

from datetime import datetime
import os

import pandas as pd
import pytest
from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QMainWindow, QWidget

from datadesk import workspace_ui
from datadesk.dialogs import ExportDialog, ImportDialog, RowDialog
from datadesk.i18n import language, set_language
from datadesk.io import FileInfo, LoadedTable, read_table, write_table
from datadesk.theme import scaled_style
from datadesk.workspace_ui import NewTableDialog, WorkspaceActions
from datadesk.workspace_widgets import WorkspaceBrowser, _size_label


@pytest.fixture(autouse=True)
def english():
    previous = language()
    set_language("en")
    yield
    set_language(previous)


def test_new_table_defaults_follow_language_and_entered_headings_are_preserved(qtbot):
    dialog = NewTableDialog()
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "New file"
    assert dialog.values() == ("New table", "xlsx", ["Name", "Date", "Amount"])
    assert dialog.name.accessibleName() == "File name"
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Save).text() == "Create"
    dialog.name.setText("Yeni tablo")
    dialog.columns.setPlainText("Ad\nAd")
    dialog.accept()
    assert dialog.error.text() == "Enter a file name and unique, non-empty column names."
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.columns.setPlainText("Ad\nSütunlar")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.values() == ("Yeni tablo", "xlsx", ["Ad", "Sütunlar"])
    set_language("tr")
    turkish = NewTableDialog()
    qtbot.addWidget(turkish)
    assert turkish.values() == ("Yeni tablo", "xlsx", ["Ad", "Tarih", "Tutar"])


def test_import_localizes_controls_and_counts_but_preserves_sheets_columns_and_values(qtbot):
    frame = pd.DataFrame({"Ad": ["Yeni tablo"] * 1234, "Sütunlar": ["0001"] * 1234})
    dialog = ImportDialog("Dosyalar.xlsx", FileInfo(sheets=["Dosyalar", "Yeni dosya"]), LoadedTable(frame))
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "DataDesk · Import file"
    assert dialog.sheet.currentText() == "Dosyalar"
    assert dialog.options().sheet == "Dosyalar"
    assert dialog.preview_model.frame.columns.tolist() == ["Ad", "Sütunlar"]
    assert dialog.preview_model.frame.iloc[0].tolist() == ["Yeni tablo", "0001"]
    assert dialog.message.text() == "Rows: 1,234 · Columns: 2"
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Open).text() == "Open file"
    dialog.sheet.setCurrentIndex(1)
    assert dialog.options().sheet == "Yeni dosya"
    assert dialog.message.text() == "Settings changed. You can refresh the preview before opening."


def test_csv_choices_are_translated_at_construction_and_keep_engine_values(qtbot):
    dialog = ImportDialog("liste.csv", FileInfo())
    qtbot.addWidget(dialog)
    assert dialog.encoding.currentText() == "Detect automatically"
    assert dialog.delimiter.currentText() == "Detect automatically"
    dialog.encoding.setCurrentIndex(dialog.encoding.findData("cp1254"))
    dialog.delimiter.setCurrentIndex(dialog.delimiter.findData(";"))
    assert dialog.encoding.currentText() == "Turkish Windows (1254)"
    assert dialog.delimiter.currentText() == "Semicolon ;"
    assert dialog.options().encoding == "cp1254"
    assert dialog.options().delimiter == ";"
    dialog.no_header.setChecked(True)
    assert dialog.no_header.text() == "No header"
    assert dialog.options().header_row is None
    set_language("tr")
    turkish = ImportDialog("liste.csv", FileInfo())
    qtbot.addWidget(turkish)
    assert turkish.encoding.currentText() == "Otomatik algıla"
    assert turkish.delimiter.itemText(1) == "Noktalı virgül ;"


def test_export_translates_format_options_and_validation_without_renaming_columns(qtbot, tmp_path):
    dialog = ExportDialog(["Ad", "Sütunlar"], 1234)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "DataDesk · Export results"
    assert "Rows to export: 1,234" in [label.text() for label in dialog.findChildren(QLabel)]
    assert dialog.format.currentText() == "Excel workbook (.xlsx)"
    assert dialog.selected_columns() == ["Ad", "Sütunlar"]
    assert dialog.options().sheet_name == "Results"
    dialog.check_all(Qt.CheckState.Unchecked)
    dialog.validate()
    assert dialog.error.text() == "Select at least one column."
    dialog.check_all(Qt.CheckState.Checked)
    dialog.format.setCurrentIndex(dialog.format.findData(".csv"))
    assert dialog.delimiter.currentText() == "Semicolon ;"
    assert dialog.safe_csv.text() == "CSV formula protection"
    frame = pd.DataFrame({"Ad": ["Yeni tablo"], "Sütunlar": ["0001"]}, dtype=object)
    output = tmp_path / "Çıktı.xlsx"
    write_table(frame, output, dialog.options())
    loaded = read_table(output)
    assert loaded.sheet == "Results"
    pd.testing.assert_frame_equal(loaded.frame, frame)


def test_row_dialog_uses_column_names_as_entered_not_as_translation_keys(qtbot):
    dialog = RowDialog(["Ad", "Yeni dosya"])
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "DataDesk · Add row"
    assert dialog.entries["Ad"].accessibleName() == "Ad"
    assert dialog.entries["Yeni dosya"].accessibleName() == "Yeni dosya"
    dialog.entries["Ad"].setText("Dosyalar")
    assert dialog.values() == {"Ad": "Dosyalar", "Yeni dosya": None}


def test_browser_translates_actions_placeholders_metadata_and_retains_real_paths(qtbot, tmp_path):
    root = tmp_path / "Çalışma klasörü"
    root.mkdir()
    (root / "Klasör").mkdir()
    path = root / "Yeni tablo.xlsm"
    path.write_bytes(b"x" * 1536)
    modified = datetime(2026, 11, 6, 14, 30).timestamp()
    os.utime(path, (modified, modified))
    browser = WorkspaceBrowser(root)
    qtbot.addWidget(browser)
    assert browser.breadcrumb.placeholderText() == "Working folder"
    assert browser.breadcrumb.text() == "Çalışma klasörü"
    assert browser.new_file_button.text() == "New file"
    assert browser.new_folder_action.text() == "New folder…"
    assert browser.file_list.headerItem().text(2) == "Modified"
    items = {
        browser.file_list.topLevelItem(index).text(0): browser.file_list.topLevelItem(index)
        for index in range(browser.file_list.topLevelItemCount())
    }
    assert set(items) == {"Klasör", "Yeni tablo.xlsm"}
    assert items["Klasör"].text(1) == "Folder"
    assert items[path.name].text(1) == "Excel (macro-enabled)"
    assert items[path.name].text(2) == "2026-11-06 14:30"
    assert items[path.name].text(3) == "1.5 KB"
    assert browser.footer.text() == "Folders: 1 · Files: 1"
    with qtbot.waitSignal(browser.new_folder_requested) as created:
        browser.new_folder_action.trigger()
    assert created.args == [root]
    assert not browser.navigate(tmp_path)
    assert browser.error_label.text() == (
        "This folder is not accessible. Choose a folder inside your working folder."
    )
    browser.navigate(root / "Klasör")
    assert browser.empty_label.text() == "This folder is empty.\nCreate a new file or import your files."
    assert browser.footer.text() == "Folders: 0 · Files: 0"
    assert path.read_bytes() == b"x" * 1536
    set_language("tr")
    assert _size_label(1536) == "1,5 KB"


class WorkspaceHost(WorkspaceActions, QMainWindow):
    """Use the real filesystem actions without coupling to the main UI builder."""

    def __init__(self, path):
        super().__init__()
        self.settings = QSettings(str(path / "prefs.ini"), QSettings.Format.IniFormat)
        self.busy = False
        self._init_workspace(path / "Dosyalar")
        self.browser = WorkspaceBrowser(self.workspace.root, self)
        self.setCentralWidget(self.browser)
        self._connect_browser()

    def _directory_changed(self, _path):
        pass

    def open_path(self, _path):
        pass

    def show_files(self):
        self.browser.refresh()

    def show_error(self, message):
        pytest.fail(message)

    def _run_task(self, _message, function, done):
        done(function())


def test_workspace_folder_and_import_actions_localize_prompts_and_dynamic_results(
    qtbot, tmp_path, monkeypatch
):
    host = WorkspaceHost(tmp_path)
    qtbot.addWidget(host)
    prompts = []

    def folder_prompt(_parent, title, label):
        prompts.append((title, label))
        return "Yeni klasör", True

    monkeypatch.setattr(workspace_ui.QInputDialog, "getText", folder_prompt)
    host.browser.new_folder_action.trigger()
    assert prompts == [("New folder", "Folder name")]
    folder = host.workspace.root / "Yeni klasör"
    assert folder.is_dir()
    assert host.statusBar().currentMessage() == "Folder created: Yeni klasör"
    source = tmp_path / "Ad.csv"
    original = "Ad;Sütunlar\nYeni tablo;0001\n".encode()
    source.write_bytes(original)
    host._copy_workspace_files([source], folder)
    assert host.statusBar().currentMessage() == "Files copied into the working folder: 1."
    assert source.read_bytes() == (folder / source.name).read_bytes() == original


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("kind", ["import", "export", "new", "row"])
def test_english_dialog_actions_remain_reachable_at_large_zoom(qtbot, theme, kind):
    parent = QWidget()
    parent.resize(800, 600)
    parent.setStyleSheet(scaled_style(200, theme))
    qtbot.addWidget(parent)
    parent.show()
    if kind == "import":
        dialog = ImportDialog("Satışlar.csv", FileInfo(), parent=parent)
        control = dialog.delimiter
    elif kind == "export":
        dialog = ExportDialog(["Ad", "Sütunlar"], 10000, parent=parent)
        dialog.format.setCurrentIndex(dialog.format.findData(".csv"))
        control = dialog.delimiter
    elif kind == "new":
        dialog = NewTableDialog(parent)
        control = dialog.name
    else:
        dialog = RowDialog(["Ad", "Sütunlar"], parent=parent)
        control = dialog.entries["Ad"]
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert dialog.width() <= parent.width()
    assert dialog.height() <= parent.height()
    for button in dialog.buttons.buttons():
        assert button.isVisible()
        assert button.width() >= button.minimumSizeHint().width()
        bounds = QRect(button.mapTo(dialog, QPoint()), button.size())
        assert dialog.rect().contains(bounds)
    dialog.content_scroll.ensureWidgetVisible(control)
    QApplication.processEvents()
    viewport = dialog.content_scroll.viewport()
    assert viewport.rect().contains(QRect(control.mapTo(viewport, QPoint()), control.size()))
