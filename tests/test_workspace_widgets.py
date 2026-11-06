"""A real file browser: navigation, emitted actions, safe roots and resizing."""

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from datadesk.theme import scaled_style
from datadesk.workspace_widgets import WorkspaceBrowser


@pytest.fixture
def browser(qtbot, tmp_path):
    root = tmp_path / "Çalışmalar"
    root.mkdir()
    (root / "2026").mkdir()
    (root / "Satışlar.csv").write_text("Kod;Tutar\n0001;12,5\n", encoding="utf-8")
    widget = WorkspaceBrowser(root)
    qtbot.addWidget(widget)
    widget.resize(900, 600)
    widget.show()
    return widget


def names(browser):
    return [browser.file_list.topLevelItem(i).text(0) for i in range(browser.file_list.topLevelItemCount())]


def item_for(browser, name):
    for index in range(browser.file_list.topLevelItemCount()):
        item = browser.file_list.topLevelItem(index)
        if item.text(0) == name:
            return item
    raise AssertionError(f"Missing browser item: {name}")


def test_browser_lists_only_folders_and_supported_tables(browser):
    root = browser.root_directory
    for filename in [
        "eski.xls",
        "Rapor.XLSX",
        "makrolu.xlsm",
        "liste.tsv",
        "not.txt",
        ".gizli.csv",
        "~$kilit.xlsx",
    ]:
        (root / filename).write_bytes(b"test")
    browser.refresh()
    assert names(browser) == ["2026", "eski.xls", "liste.tsv", "makrolu.xlsm", "Rapor.XLSX", "Satışlar.csv"]
    assert browser.footer.text() == "1 klasör · 5 dosya"
    assert browser.breadcrumb.text() == "Çalışmalar"
    assert not browser.empty_label.isVisible()


def test_folder_activation_up_and_back_use_real_paths(qtbot, browser):
    root = browser.root_directory
    browser.file_list.setCurrentItem(item_for(browser, "2026"))
    with qtbot.waitSignal(browser.directory_changed) as changed:
        qtbot.keyClick(browser.file_list, Qt.Key.Key_Return)
    assert changed.args == [root / "2026"]
    assert browser.current_directory == root / "2026"
    assert browser.breadcrumb.text() == "Çalışmalar / 2026"
    assert browser.empty_label.isVisible()
    browser.go_up()
    assert browser.current_directory == root
    browser.go_back()
    assert browser.current_directory == root / "2026"
    browser.go_back()
    assert browser.current_directory == root
    assert not browser.back_button.isEnabled()
    assert not browser.up_button.isEnabled()


def test_table_activation_emits_open_without_modifying_file(qtbot, browser):
    path = browser.root_directory / "Satışlar.csv"
    original = path.read_bytes()
    browser.file_list.setCurrentItem(item_for(browser, path.name))
    with qtbot.waitSignal(browser.open_requested) as opened:
        qtbot.keyClick(browser.file_list, Qt.Key.Key_Return)
    assert opened.args == [path]
    assert path.read_bytes() == original
    assert browser.current_directory == browser.root_directory


def test_toolbar_and_overflow_actions_emit_current_folder(qtbot, browser):
    browser.navigate("2026")
    path = browser.current_directory
    for signal, action in [
        (browser.new_file_requested, browser.new_file_button.click),
        (browser.new_folder_requested, browser.new_folder_action.trigger),
        (browser.import_requested, browser.import_action.trigger),
    ]:
        with qtbot.waitSignal(signal) as requested:
            action()
        assert requested.args == [path]
    assert list(path.iterdir()) == []


def test_rename_shortcut_and_move_emit_selected_path(qtbot, browser):
    assert not browser.rename_action.isEnabled()
    browser.file_list.setCurrentItem(item_for(browser, "Satışlar.csv"))
    assert browser.rename_action.isEnabled()
    with qtbot.waitSignal(browser.rename_requested) as renamed:
        qtbot.keyClick(browser.file_list, Qt.Key.Key_F2)
    assert renamed.args == [browser.root_directory / "Satışlar.csv"]
    with qtbot.waitSignal(browser.move_requested) as moved:
        browser.move_action.trigger()
    assert moved.args == renamed.args


def test_navigation_rejects_parent_and_symlink_outside_root(browser, tmp_path):
    root = browser.root_directory
    external = tmp_path / "Dışarıdaki dosyalar"
    external.mkdir()
    (external / "Gizli.csv").write_bytes(b"original")
    try:
        (root / "Dış bağlantı").symlink_to(external, target_is_directory=True)
        (root / "Dış dosya.csv").symlink_to(external / "Gizli.csv")
    except OSError:
        pytest.skip("Creating symbolic links is not permitted on this filesystem.")
    browser.refresh()
    assert "Dış bağlantı" not in names(browser)
    assert "Dış dosya.csv" not in names(browser)
    assert not browser.navigate("..")
    assert not browser.navigate(external)
    assert not browser.navigate(root / "Dış bağlantı")
    assert browser.current_directory == root
    assert browser.error_label.isVisible()
    assert browser.navigate(root / "2026")
    assert browser.error_label.isHidden()


def test_replacing_current_folder_with_escaping_symlink_returns_to_safe_parent(browser, tmp_path):
    root = browser.root_directory
    folder = root / "2026"
    external = tmp_path / "Başka klasör"
    external.mkdir()
    (external / "gizli.csv").write_bytes(b"secret")
    browser.navigate(folder)
    folder.rmdir()
    try:
        folder.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symbolic links is not permitted on this filesystem.")
    browser.refresh()
    assert browser.current_directory == root
    assert names(browser) == ["Satışlar.csv"]


def test_refresh_recovers_when_current_folder_has_been_removed(browser):
    root = browser.root_directory
    browser.navigate("2026")
    browser.current_directory.rmdir()
    browser.refresh()
    assert browser.current_directory == root
    assert names(browser) == ["Satışlar.csv"]


def test_refresh_preserves_selection_and_reads_external_changes(browser):
    path = browser.root_directory / "Satışlar.csv"
    browser.file_list.setCurrentItem(item_for(browser, path.name))
    (browser.root_directory / "Yeni.tsv").write_bytes(b"Kod\n01\n")
    browser.refresh()
    assert "Yeni.tsv" in names(browser)
    assert browser.selected_path() == path


def test_set_root_resets_navigation_and_never_creates_missing_directory(browser, tmp_path):
    browser.navigate("2026")
    missing = tmp_path / "Henüz yok"
    assert not browser.set_root(missing)
    assert not missing.exists()
    assert browser.current_directory.name == "2026"
    replacement = tmp_path / "Başka çalışma"
    replacement.mkdir()
    assert browser.set_root(replacement)
    assert browser.current_directory == replacement
    assert browser.root_directory == replacement
    assert not browser.back_button.isEnabled()
    assert browser.empty_label.isVisible()


def test_no_root_disables_mutations_but_keeps_root_choice_available(qtbot):
    browser = WorkspaceBrowser()
    qtbot.addWidget(browser)
    browser.show()
    assert browser.current_directory is None
    for control in (browser.new_file_button, browser.new_folder_action, browser.import_action):
        assert not control.isEnabled()
    root_action = browser.more_menu.actions()[-1]
    assert root_action.isEnabled()
    with qtbot.waitSignal(browser.root_requested):
        root_action.trigger()


def test_drop_accepts_local_spreadsheets_and_emits_import_without_moving(qtbot, browser, tmp_path):
    incoming = tmp_path / "Dış liste.csv"
    incoming.write_text("Kod\n0001\n", encoding="utf-8")
    ignored = tmp_path / "not.txt"
    ignored.write_text("not", encoding="utf-8")
    mime = QMimeData()
    mime.setUrls(
        [QUrl.fromLocalFile(str(incoming)), QUrl.fromLocalFile(str(ignored)), QUrl("https://x.test/a.csv")]
    )
    entered = QDragEnterEvent(
        QPoint(20, 20),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    browser.dragEnterEvent(entered)
    assert entered.isAccepted()
    event = QDropEvent(
        QPointF(20, 20),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with qtbot.waitSignal(browser.import_files_requested) as imported:
        browser.dropEvent(event)
    assert imported.args == [[incoming], browser.current_directory]
    assert incoming.is_file()
    assert not (browser.current_directory / incoming.name).exists()
    assert event.isAccepted()


@pytest.mark.parametrize("width,zoom", [(400, 100), (600, 100), (600, 150), (900, 150)])
def test_resizing_keeps_creation_and_all_overflow_actions_reachable(qtbot, browser, width, zoom):
    browser.setStyleSheet(scaled_style(zoom))
    browser.resize(width, 500)
    QApplication.processEvents()
    qtbot.wait(10)
    assert browser.width() == width
    for control in (browser.new_file_button, browser.more_button, browser.breadcrumb):
        assert control.isVisible()
        rect = control.rect().translated(control.mapTo(browser, QPoint(0, 0)))
        assert browser.rect().contains(rect)
    assert browser.new_file_button.width() >= browser.new_file_button.sizeHint().width()
    assert browser.file_list.viewport().width() >= width - 40
    assert browser.file_list.columnWidth(0) >= 100
    assert browser.new_folder_action.isEnabled()
    assert browser.import_action.isEnabled()


def test_names_are_plain_text_and_long_names_do_not_enlarge_browser(browser):
    path = browser.root_directory / "Kasım & Aralık satışlarının açıklamalı dosya listesi.csv"
    path.write_bytes(b"value")
    browser.refresh()
    item = item_for(browser, path.name)
    assert item.text(0) == path.name
    assert browser.width() == 900
