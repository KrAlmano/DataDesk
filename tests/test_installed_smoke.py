"""The same acceptance check runs against source and each native application."""

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from datadesk import app as application
from datadesk.i18n import language, set_language
from datadesk.smoke import run_smoke_test
from datadesk.theme import configure_app


def test_installed_acceptance_workflow_uses_real_files_and_qt(qapp):
    configure_app(qapp)
    report = run_smoke_test(qapp)
    assert report["status"] == "success"
    assert {
        "xlsx_export_and_reopen",
        "csv_export_and_reopen",
        "tsv_export_and_reopen",
        "docx_export_and_reopen",
        "source_file_unchanged",
        "workspace_real_folder_and_browser_navigation",
        "workspace_new_xlsx_add_rows_and_column",
        "workspace_save_preserves_all_rows_under_filter",
        "workspace_rename_move_and_reopen_managed_table",
        "qt_turkish_and_english_translation_catalogs",
        "english_dark_mode_preserves_unsaved_table_and_filters",
        "saved_language_and_theme_restored_on_reopen",
        "turkish_light_mode_restored_without_data_loss",
    } <= set(report["checks"])


def test_startup_applies_saved_preferences_before_creating_the_window(monkeypatch, qapp, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui_language", "en")
    settings.setValue("ui_theme", "dark")
    monkeypatch.setattr(application, "QSettings", lambda *_: settings)
    previous_language = language()
    previous_theme = qapp.property("datadeskThemePreference") or "light"
    calls = []

    def inspect_startup(app, destination):
        calls.append(destination)
        assert app is qapp
        assert language() == "en"
        assert app.property("datadeskTheme") == "dark"
        assert app._datadesk_translation_loaded
        assert QApplication.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
        return 0

    monkeypatch.setattr(application, "_smoke_report", inspect_startup)
    try:
        assert application.main(["--smoke-test", str(tmp_path / "report.json")]) == 0
        assert len(calls) == 1
    finally:
        set_language(previous_language)
        configure_app(qapp, previous_theme)
