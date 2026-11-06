"""A worker starting inside the settings modal must not discard draft choices."""

from threading import Event

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from datadesk.i18n import language, set_language
from datadesk.settings_ui import SettingsDialog
from datadesk.ui import MainWindow


def test_settings_wait_for_worker_started_during_modal_then_apply(qtbot, tmp_path):
    previous = language()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "dirty", False))
    window.show()
    entered = Event()
    release = Event()
    failures = []
    observed = {}

    def work():
        entered.set()
        if not release.wait(5):
            raise TimeoutError("The test did not release its worker")

    def interact():
        dialog = None
        try:
            dialog = window.findChild(SettingsDialog)
            assert dialog is not None and dialog.isVisible()
            observed["dialog"] = dialog
            dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
            dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))
            dialog.zoom_combo.setCurrentIndex(dialog.zoom_combo.findData(125))
            apply_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Apply)
            assert window._run_task("Working", work, lambda _result: None)
            # Guard acceptance even before the timer has disabled the button.
            dialog.accept()
            assert dialog.isVisible()
            assert window.language_code == "tr"
            qtbot.waitUntil(entered.is_set)
            qtbot.waitUntil(lambda: not apply_button.isEnabled())
            qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
            assert dialog.isVisible()
            assert dialog.preferences() == {"language": "en", "theme": "dark", "zoom": 125}
            release.set()
            qtbot.waitUntil(lambda: not window.busy and not window.tasks)
            qtbot.waitUntil(apply_button.isEnabled)
            qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
        except BaseException as error:
            failures.append(error)
            if dialog is not None:
                dialog.reject()
        finally:
            release.set()

    try:
        QTimer.singleShot(0, interact)
        window.show_settings()
        if failures:
            raise failures[0]
        assert window.language_code == "en"
        assert window.theme_mode == "dark"
        assert window.zoom_percent == 125
        assert settings.value("ui_language") == "en"
        assert not observed["dialog"]._apply_guard_timer.isActive()
    finally:
        release.set()
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not window.busy and not window.tasks)
        window.dirty = False
        window.close()
        set_language(previous)


def test_cancel_remains_available_while_apply_is_blocked(qtbot):
    dialog = SettingsDialog(can_apply=lambda: False)
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Apply).isEnabled()
    assert dialog._apply_guard_timer.isActive()
    qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel), Qt.MouseButton.LeftButton)
    assert not dialog.isVisible()
    assert not dialog._apply_guard_timer.isActive()
