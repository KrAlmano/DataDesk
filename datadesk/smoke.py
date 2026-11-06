"""Exercise an installed/frozen build using actual files and a Qt event loop."""

from datetime import datetime
from pathlib import Path
import platform
import sys
import tempfile
import time

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon


def run_smoke_test(app):
    from docx import Document as WordDocument
    from openpyxl import Workbook
    import xlrd

    from . import __version__
    from .core import FilterRule
    from .io import ExportOptions, ImportOptions, inspect_file, read_table
    from .ui import MainWindow
    from .workspace import Workspace

    def wait_for(window):
        deadline = time.monotonic() + 30
        idle_rounds = 0
        while time.monotonic() < deadline:
            app.processEvents()
            if not window.busy and not window.tasks and not window.search_timer.isActive():
                idle_rounds += 1
                if idle_rounds >= 3:
                    return
            else:
                idle_rounds = 0
            time.sleep(0.01)
        raise RuntimeError("The installed application did not complete its background task.")

    checks = []
    with tempfile.TemporaryDirectory(prefix="datadesk-installed-test-") as temporary:
        directory = Path(temporary)
        source = directory / "Türkçe satış verileri.xlsx"
        workbook = Workbook()
        workbook.active.title = "Açıklamalar"
        workbook.active.append(["İkinci sayfadaki veriyi kullanın."])
        sheet = workbook.create_sheet("Satışlar")
        sheet.append(["Kod", "Şehir", "Tutar", "Tarih", "Not"])
        sheet.append(["0001", "İstanbul", 1250.5, datetime(2026, 11, 6), "NA"])
        sheet.append(["0002", "Ankara", 500, datetime(2026, 11, 6), None])
        sheet.append(["0003", "İSTANBUL", 2500, datetime(2026, 11, 7), "=SUM(1,2)"])
        # The last cell is literal user data, not an uncached Excel formula.
        sheet.cell(4, 5).data_type = "s"
        workbook.save(source)
        workbook.close()
        original = source.read_bytes()
        info = inspect_file(source)
        if info.sheets != ["Açıklamalar", "Satışlar"]:
            raise AssertionError("Installed Excel sheet detection failed.")
        loaded = read_table(source, ImportOptions(sheet="Satışlar"))
        if loaded.frame["Kod"].tolist() != ["0001", "0002", "0003"]:
            raise AssertionError("Installed Excel reading changed identifiers.")
        checks.append("xlsx_multiple_sheets_and_leading_zero_ids")
        assets = Path(__file__).parent / "assets"
        if not (assets / "fonts" / "Inter.ttf").is_file() or "Inter" not in app.font().family():
            raise AssertionError(
                f"The shared macOS/Windows font is missing (file_exists={(assets / 'fonts' / 'Inter.ttf').is_file()}, family={app.font().family()!r}, assets={assets})."
            )
        checks.append("same_bundled_inter_font_on_both_platforms")
        for name in ("icon.svg", "chevron.svg"):
            if QIcon(str(assets / name)).isNull():
                raise AssertionError(f"Packaged SVG asset could not be loaded: {name}")
        checks.append("native_qt_plugins_and_svg_assets")
        window = MainWindow(
            settings=QSettings(str(directory / "settings.ini"), QSettings.Format.IniFormat),
            workspace_root=directory / "workspace",
        )
        errors = []
        window.show_error = errors.append
        try:
            window.set_document(loaded.frame, source.name, source)
            window.resize(1024, 768)
            window.show()
            app.processEvents()
            window.apply_view(
                rules=[
                    FilterRule("Şehir", "equals", "istanbul"),
                    FilterRule("Tutar", "gte", "1000", kind="number"),
                ],
                sort=("Tutar", False),
            )
            wait_for(window)
            expected = ["0003", "0001"]
            if errors or window.model.frame["Kod"].tolist() != expected:
                raise AssertionError(f"Installed filtering/sorting failed: {errors}")
            if not window.export_button.isEnabled() or window.model.rowCount() != 2:
                raise AssertionError("The installed table/export UI is not usable.")
            checks.append("same_qt_workspace_filter_sort_and_full_results")
            for suffix in (".xlsx", ".csv", ".tsv", ".docx"):
                target = directory / ("Filtrelenmiş sonuç" + suffix)
                window.export_to(target, ExportOptions(columns=["Kod", "Tutar", "Not"], safe_csv=False))
                wait_for(window)
                if errors or not target.is_file():
                    raise AssertionError(f"Installed export failed for {suffix}: {errors}")
                if suffix == ".docx":
                    table = WordDocument(target).tables[0]
                    if [row.cells[0].text for row in table.rows[1:]] != expected:
                        raise AssertionError("The installed Word template/export is incomplete.")
                elif read_table(target).frame["Kod"].tolist() != expected:
                    raise AssertionError(f"Installed export/reopen changed rows: {suffix}")
                checks.append(f"{suffix[1:]}_export_and_reopen")
            if source.read_bytes() != original:
                raise AssertionError("The source workbook changed during the installed smoke test.")
            checks.append("source_file_unchanged")
            if not xlrd.__version__:
                raise AssertionError("Legacy XLS support is missing from this bundle.")
            checks.append("legacy_xls_reader_available")

            folder = window.workspace.create_folder(".", "Türkçe çalışma klasörü")
            window.browser.navigate(folder)
            window.show_files()
            if window.browser.current_directory != folder or not folder.is_dir():
                raise AssertionError("The installed workspace could not navigate its real folder.")
            checks.append("workspace_real_folder_and_browser_navigation")
            working = window.create_workspace_file(folder, "Yeni çalışma", ["Kod", "Tutar"])
            wait_for(window)
            if working is None or read_table(working).frame.shape != (0, 2):
                raise AssertionError(
                    f"The installed workspace could not create an empty Excel file: {errors}"
                )
            for code, amount in [("0001", "12,50"), ("0002", "350,00"), ("0003", "25,00")]:
                window.document.add({"Kod": code, "Tutar": amount})
            window.document.checkpoint()
            window.document.frame["Açıklama"] = ["İlk kayıt", "İkinci kayıt", "Son kayıt"]
            window._after_edit()
            wait_for(window)
            if window.column.findText("Açıklama") == -1 or window.model.rowCount() != 3:
                raise AssertionError("The installed workspace did not refresh added rows/columns.")
            checks.append("workspace_new_xlsx_add_rows_and_column")
            window.apply_view(rules=[FilterRule("Kod", "equals", "0002")])
            wait_for(window)
            if window.model.frame["Kod"].tolist() != ["0002"]:
                raise AssertionError("The new working table could not be filtered.")
            window.save_document()
            wait_for(window)
            if window.dirty or read_table(working).frame["Kod"].tolist() != ["0001", "0002", "0003"]:
                raise AssertionError("Saving a filtered working table omitted source rows.")
            checks.append("workspace_save_preserves_all_rows_under_filter")

            window.workspace = Workspace(window.workspace.root)
            if not window.workspace.is_managed(working):
                raise AssertionError(
                    "The saved workspace table was not recognised after restoring its catalogue."
                )
            renamed = window.workspace.rename(working, "Yeniden adlandırılmış.xlsx")
            window._item_moved(working, renamed)
            archive = window.workspace.create_folder(".", "Arşiv")
            moved = window.workspace.move(renamed, archive)
            window._item_moved(renamed, moved)
            if window.source_path != moved or not window._can_save_source():
                raise AssertionError("The installed editor lost its table after renaming/moving the file.")
            window.document.edit(0, "Açıklama", "Güncellenmiş kayıt")
            window._after_edit()
            wait_for(window)
            window.save_document()
            wait_for(window)
            window.open_path(moved)
            wait_for(window)
            if (
                errors
                or window.source_path != moved
                or window.document.frame["Kod"].tolist() != ["0001", "0002", "0003"]
                or window.document.frame.at[0, "Açıklama"] != "Güncellenmiş kayıt"
                or source.read_bytes() != original
            ):
                raise AssertionError(f"Installed workspace rename/move/save/reopen failed: {errors}")
            checks.append("workspace_rename_move_and_reopen_managed_table")
        finally:
            wait_for(window)
            window.dirty = False
            window.close()
            app.processEvents()
    return {
        "status": "success",
        "application": "DataDesk",
        "version": __version__,
        "system": platform.system(),
        "architecture": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "checks": checks,
    }
