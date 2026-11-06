"""Live settings must preserve the user's working table and unfinished inputs."""

import pandas as pd
import pytest
from PySide6.QtCore import QPoint, QRect, QSettings
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from datadesk.core import FilterRule
from datadesk.i18n import set_language, tr
from datadesk.io import ExportOptions, read_table
from datadesk.theme import PALETTES
from datadesk.ui import MainWindow


@pytest.fixture
def desk(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window, before_close_func=lambda w: setattr(w, "dirty", False))
    window.show()
    window.test_errors = []
    window.show_error = window.test_errors.append
    yield window
    settle(qtbot, window)
    window.dirty = False
    window.close()
    set_language("tr")


def settle(qtbot, window):
    for _ in range(3):
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not window.busy and not window.tasks, timeout=10000)


@pytest.mark.parametrize("code", ["tr", "en"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_settings_filter_export_and_full_save_roundtrip(qtbot, desk, tmp_path, code, theme):
    assert desk.apply_preferences(language=code, theme=theme, zoom=100)
    path = desk.create_workspace_file(desk.workspace.root, "Türkçe çalışma", ["Kod", "Tutar", "Not"])
    settle(qtbot, desk)
    for code_value, amount, note in [("0001", "1.250,50", "NA"), ("0002", "25,00", "İstanbul")]:
        desk.document.add({"Kod": code_value, "Tutar": amount, "Not": note})
    desk._after_edit()
    settle(qtbot, desk)
    desk.apply_view(rules=[FilterRule("Tutar", "gt", "1000", kind="number", number_format="tr")])
    settle(qtbot, desk)
    assert desk.model.frame["Kod"].tolist() == ["0001"]
    for suffix in ("xlsx", "csv"):
        output = tmp_path / f"Sonuç.{suffix}"
        desk.export_to(output, ExportOptions(safe_csv=False))
        settle(qtbot, desk)
        assert read_table(output).frame["Kod"].tolist() == ["0001"]
    desk.save_document()
    settle(qtbot, desk)
    assert read_table(path).frame["Kod"].tolist() == ["0001", "0002"]
    assert not desk.test_errors
    assert (
        QApplication.instance().palette().color(QPalette.ColorRole.Base).name() == PALETTES[theme]["surface"]
    )
    assert desk.settings_button.text() == ("Ayarlar" if code == "tr" else "Settings")


def test_switch_preserves_dirty_history_filter_sort_draft_and_selection(qtbot, desk):
    desk.set_document(
        pd.DataFrame({"Kod": ["0001", "0002", "0003"], "Tutar": [20, 80, 40]}),
        "Yeni dosya.xlsx",
        warnings=[tr("Bir dosya açın")],
    )
    desk.edit_cell(0, "Tutar", "25")
    settle(qtbot, desk)
    rules = [FilterRule("Tutar", "gte", "25", kind="number")]
    desk.apply_view(rules=rules, sort=("Tutar", False))
    settle(qtbot, desk)
    desk.column.setCurrentText("Tutar")
    desk.operator.setCurrentIndex(desk.operator.findData("between"))
    desk.kind.setCurrentIndex(desk.kind.findData("number"))
    desk.value.setText("10,5")
    desk.value2.setText("90,5")
    desk.table.selectRow(1)
    desk.table.setColumnWidth(0, 222)
    document = desk.document
    frame = desk.model.frame.copy(deep=True)
    history = len(document.history)
    for code, theme in [("en", "dark"), ("tr", "light"), ("en", "system"), ("tr", "dark")]:
        assert desk.apply_preferences(language=code, theme=theme)
        QApplication.processEvents()
        assert desk.document is document
        assert len(document.history) == history
        assert desk.dirty
        assert desk.rules == rules
        assert desk.sort_column == "Tutar" and not desk.sort_ascending
        pd.testing.assert_frame_equal(desk.model.frame, frame)
        assert desk.column.currentText() == "Tutar"
        assert desk.operator.currentData() == "between"
        assert desk.kind.currentData() == "number"
        assert desk.value.text() == "10,5" and desk.value2.text() == "90,5"
        assert [i.row() for i in desk.table.selectionModel().selectedRows()] == [1]
        assert desk.table.columnWidth(0) == 222
        assert desk.page_tabs.tabText(1) == "Yeni dosya.xlsx *"
        assert desk.notice.text() == ("Open a file" if code == "en" else "Bir dosya açın")
        enabled_actions = [
            action
            for action in desk.findChildren(QAction)
            if action.isEnabled() and action.shortcut().toString() == "Ctrl+,"
        ]
        assert len(enabled_actions) == 1
    desk.undo()
    settle(qtbot, desk)
    assert desk.document.frame.at[0, "Tutar"] == 20


def test_live_switch_commits_editor_and_keeps_pending_search(qtbot, desk):
    desk.set_document(pd.DataFrame({"Kod": ["old", "keep"], "Tutar": [1, 2]}), "x.xlsx")
    desk.table.setCurrentIndex(desk.model.index(0, 0))
    desk.table.edit(desk.model.index(0, 0))
    editor = desk.table.findChild(QLineEdit)
    assert editor is not None
    editor.setText("changed")
    assert desk.apply_preferences(language="en", theme="dark")
    settle(qtbot, desk)
    assert desk.document.frame.at[0, "Kod"] == "changed"
    desk.search.setText("keep")
    assert desk.apply_preferences(language="tr", theme="light")
    settle(qtbot, desk)
    assert desk.search.text() == "keep"
    assert desk.model.frame["Kod"].tolist() == ["keep"]
    assert desk.dirty


def test_settings_persist_and_cancel_does_not_apply(qtbot, desk, monkeypatch):
    from datadesk import preferences

    assert desk.apply_preferences(language="en", theme="dark", zoom=125)

    def cancel(dialog):
        dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("tr"))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(preferences.SettingsDialog, "exec", cancel)
    desk.show_settings()
    assert desk.language_code == "en" and desk.theme_mode == "dark"
    another = MainWindow(settings=desk.settings, workspace_root=desk.workspace.root)
    qtbot.addWidget(another)
    assert another.language_code == "en" and another.theme_mode == "dark"
    assert another.zoom_percent == 125
    assert another.settings_button.text() == "Settings"
    another.close()


@pytest.mark.parametrize("code", ["tr", "en"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_settings_remain_reachable_at_small_window_and_large_text(qtbot, desk, code, theme):
    desk.open_demo()
    desk.resize(800, 600)
    assert desk.apply_preferences(language=code, theme=theme, zoom=150)
    QApplication.processEvents()
    for control in (desk.settings_button, desk.export_button, desk.filter_toggle, desk.search):
        assert control.isVisible()
        assert desk.rect().contains(QRect(control.mapTo(desk, QPoint()), control.size()))
    desk.toggle_filters()
    QApplication.processEvents()
    assert desk.filter_button.isVisible()
    assert desk.rect().contains(QRect(desk.filter_button.mapTo(desk, QPoint()), desk.filter_button.size()))


def test_busy_operation_cannot_partly_change_preferences(desk):
    before = (desk.language_code, desk.theme_mode, desk.zoom_percent)
    desk.busy = True
    try:
        assert not desk.apply_preferences(language="en", theme="dark", zoom=150)
        assert (desk.language_code, desk.theme_mode, desk.zoom_percent) == before
        assert desk.settings.value("ui_language") is None
    finally:
        desk.busy = False


def test_switch_preserves_directory_history_selected_file_and_error(qtbot, desk):
    from datadesk.workspace_widgets import PATH_ROLE

    folder = desk.workspace.create_folder(".", "Yeni klasör")
    path = desk.workspace.create_table(folder, "Yeni dosya.csv", ["Kod"])
    desk.browser.navigate(folder)
    for i in range(desk.browser.file_list.topLevelItemCount()):
        item = desk.browser.file_list.topLevelItem(i)
        if item.data(0, PATH_ROLE) == path:
            desk.browser.file_list.setCurrentItem(item)
    desk.set_document(pd.DataFrame({"Tutar": [1, 2]}), "Yeni dosya.csv")
    desk.apply_view(rules=[FilterRule("Tutar", "between", "10", "2", kind="number")])
    settle(qtbot, desk)
    assert desk.filter_error.text()
    desk.show_files()
    assert desk.apply_preferences(language="en", theme="dark")
    assert desk.page_tabs.currentIndex() == 0
    assert desk.browser.current_directory == folder
    assert desk.browser.selected_path() == path
    assert desk.browser.back_button.isEnabled()
    assert desk.filter_error.text() == str(
        tr(desk._filter_error_text.source, **desk._filter_error_text.values)
    )
    assert "sınır" not in desk.filter_error.text()
    desk.browser.go_back()
    assert desk.browser.current_directory == desk.workspace.root


@pytest.mark.parametrize("code, theme", [("en", "dark"), ("tr", "light")])
def test_file_dialog_uses_app_language_and_theme(qtbot, desk, code, theme):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFileDialog, QDialogButtonBox

    desk.apply_preferences(language=code, theme=theme)
    assert QApplication.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    dialog = QFileDialog(desk)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None  # a real themed Qt dialog, rather than an OS dialog
    cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel.text() == ("Cancel" if code == "en" else "İptal")
    assert dialog.palette().color(QPalette.ColorRole.Window).name() == PALETTES[theme]["chrome"]
    assert (
        dialog.findChild(QLineEdit).palette().color(QPalette.ColorRole.Base).name()
        == PALETTES[theme]["surface"]
    )
    dialog.reject()
