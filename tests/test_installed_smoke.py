"""The same acceptance check runs against source and each native application."""

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
    } <= set(report["checks"])
