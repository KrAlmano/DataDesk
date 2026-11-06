"""Capture the real DataDesk workflow with synthetic data and temporary settings.

Run ``QT_QPA_PLATFORM=cocoa uv run python tools/capture_screenshots.py`` on macOS
or omit that platform override on Windows. All images come from QWidget.grab();
the script does not compose, retouch or fake application controls.
"""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datadesk.dialogs import ExportDialog, ImportDialog, demo_frame  # noqa: E402
from datadesk.io import ExportOptions, ImportOptions, inspect_file, read_table, write_table  # noqa: E402
from datadesk.settings_ui import SettingsDialog  # noqa: E402
from datadesk.theme import configure_app  # noqa: E402
from datadesk.ui import MainWindow  # noqa: E402
from datadesk.workspace_ui import NewTableDialog  # noqa: E402


def settle(application, window=None):
    """Let real layout, focus and background completion events finish."""
    deadline = time.monotonic() + 15
    while window is not None and window.busy:
        application.processEvents()
        if time.monotonic() > deadline:
            raise RuntimeError("A screenshot operation did not finish in 15 seconds")
        time.sleep(0.01)
    for _ in range(3):
        application.processEvents()
        time.sleep(0.02)


def capture(widget, *paths):
    """Save an unmodified widget capture, including any real scrollbars."""
    pixmap = widget.grab()
    if pixmap.isNull():
        raise RuntimeError("Qt returned an empty screenshot")
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not pixmap.save(str(path)):
            raise RuntimeError(f"Screenshot could not be saved: {path}")


def show_dialog(application, dialog, width, height):
    """Show a real modal dialog without blocking the capture event loop."""
    dialog.setModal(True)
    dialog.show()
    settle(application)
    available = dialog.screen().availableGeometry()
    dialog.resize(min(width, available.width() - 64), min(height, available.height() - 80))
    settle(application)


def sample_workbook(directory):
    """Create the same 120-row, eight-column workbook shown in the guide."""
    from openpyxl import load_workbook

    path = directory / "Ornek_Satislar.xlsx"
    frame = demo_frame()
    write_table(frame, path, ExportOptions(sheet_name="Satışlar"))
    book = load_workbook(path)
    summary = book.create_sheet("Özet", 0)
    summary.append(["Gösterge", "Değer"])
    summary.append(["Sipariş sayısı", len(frame)])
    summary.append(["Dönem", "Ekim 2026"])
    summary.append(["Kaynak", "DataDesk için oluşturulmuş yapay örnek veri"])
    book.save(path)
    book.close()
    return path


def render(output):
    gallery = output / "screenshots"
    application = QApplication.instance() or QApplication([])
    application.setApplicationName("DataDesk")
    configure_app(application)
    with ExitStack() as resources:
        temporary = resources.enter_context(tempfile.TemporaryDirectory(prefix="datadesk-screenshots-"))
        directory = Path(temporary)
        # The organization/application QSettings constructor uses NativeFormat
        # even after setDefaultFormat() on macOS. An explicit file constructor
        # is essential to keep screenshots independent from user preferences.
        resources.enter_context(
            patch(
                "datadesk.ui.QSettings",
                lambda *_: QSettings(str(directory / "settings.ini"), QSettings.Format.IniFormat),
            )
        )
        window = MainWindow(workspace_root=directory / "DataDesk")
        assert window.apply_preferences(language="tr", theme="light", zoom=100)
        sales_folder = window.workspace.create_folder(".", "Satışlar")
        window.workspace.create_folder(".", "Giderler")
        window.workspace.create_folder(".", "Arşiv")
        customers = window.workspace.create_table(".", "Müşteriler.csv", ["Kod", "Ad", "Şehir"])
        assert customers.is_file()
        window.browser.refresh()
        window.set_zoom(100)
        window.resize(1440, 900)
        window.show()
        settle(application)
        # QFileSystemModel populates asynchronously; wait for the real folder
        # tree instead of capturing a transient empty sidebar on first launch.
        tree_deadline = time.monotonic() + 5
        while window.folder_model.rowCount(window.folder_tree.rootIndex()) < 3:
            application.processEvents()
            if time.monotonic() > tree_deadline:
                raise RuntimeError("The sample folders did not appear in the sidebar")
            time.sleep(0.02)
        settle(application)
        capture(window, gallery / "01-start.png", output / "screenshot-empty.png")

        source = sample_workbook(directory)
        copied = window.workspace.import_files([source], sales_folder)[0]
        window.workspace.create_table(sales_folder, "Kasım siparişleri.xlsx", ["Sipariş", "Müşteri", "Tutar"])
        window.browser.navigate(sales_folder)
        settle(application)
        capture(window, gallery / "09-workspace.png")
        creator = NewTableDialog(window)
        creator.name.setText("Kasım giderleri")
        creator.columns.setPlainText("Tarih\nAçıklama\nKategori\nTutar")
        show_dialog(application, creator, 560, 510)
        capture(creator, gallery / "08-new-file.png")
        creator.close()
        settle(application)
        source = copied
        info = inspect_file(source)
        loaded = read_table(source, ImportOptions(sheet="Satışlar"))
        assert info.sheets == ["Özet", "Satışlar"]
        assert loaded.frame.shape == (120, 8)
        importer = ImportDialog(source, info, loaded, parent=window)
        importer.sheet.setCurrentText("Satışlar")
        importer.set_preview(loaded)
        show_dialog(application, importer, 960, 720)
        importer.preview.resizeColumnsToContents()
        settle(application)
        capture(importer, gallery / "02-import.png")
        importer.close()
        settle(application)

        window.set_document(loaded.frame, "Ornek_Satislar.xlsx  /  Satışlar", source)
        window.notice.hide()
        if not window.filter_container.isVisible():
            window.toggle_filters()
        window.column.setCurrentText("Tutar")
        window.kind.setCurrentIndex(window.kind.findData("auto"))
        window.number_format.setCurrentIndex(window.number_format.findData("tr"))
        window.operator.setCurrentIndex(window.operator.findData("between"))
        window.value.setText("5.000,00")
        window.value2.setText("20.000,00")
        window.filter_tabs.setCurrentIndex(0)
        window.table.setFocus(Qt.FocusReason.OtherFocusReason)
        settle(application)
        assert not window.rules
        assert len(window.model.frame) == 120
        capture(window, gallery / "03-filter-builder.png", output / "screenshot-filters.png")

        window.add_filter()
        settle(application, window)
        window.column.setCurrentText("Durum")
        window.operator.setCurrentIndex(window.operator.findData("equals"))
        window.value.setText("Tamamlandı")
        window.add_filter()
        settle(application, window)
        assert len(window.rules) == 2
        assert len(window.model.frame) == 37
        window.filter_tabs.setCurrentIndex(1)
        settle(application)
        capture(window, gallery / "04-results.png", output / "screenshot.png")

        exporter = ExportDialog(window.model.frame.columns, len(window.model.frame), parent=window)
        for position in range(exporter.columns.count()):
            item = exporter.columns.item(position)
            if item.text() in ("Departman", "Müşteri Kodu"):
                item.setCheckState(Qt.CheckState.Unchecked)
        assert len(exporter.selected_columns()) == 6
        assert exporter.format.currentData() == ".xlsx"
        show_dialog(application, exporter, 720, 720)
        capture(exporter, gallery / "05-export.png")
        exporter.close()
        settle(application)

        window.resize(800, 600)
        window.set_zoom(100)
        settle(application)
        capture(window, gallery / "06-compact.png", output / "screenshot-compact.png")
        window.toggle_filters()
        window.filter_tabs.setCurrentIndex(0)
        window.column.setCurrentText("Tutar")
        window.number_format.setCurrentIndex(window.number_format.findData("tr"))
        window.operator.setCurrentIndex(window.operator.findData("between"))
        window.value.setText("5.000,00")
        window.value2.setText("20.000,00")
        settle(application)
        window.filter_scroll.verticalScrollBar().setValue(0)
        capture(window, output / "screenshot-compact-filters.png")
        window.toggle_filters()
        window.set_zoom(150)
        settle(application)
        capture(window, gallery / "07-zoom.png", output / "screenshot-zoom.png")

        # Capture the same loaded document after real preference changes. The
        # Turkish source headings/values remain unchanged in the English UI.
        source_frame = window.document.frame.copy(deep=True)
        window.resize(1440, 900)
        assert window.apply_preferences(language="tr", theme="dark", zoom=100)
        settle(application, window)
        if not window.filter_container.isVisible():
            window.toggle_filters()
        window.filter_tabs.setCurrentIndex(1)
        settle(application)
        assert len(window.rules) == 2
        assert len(window.model.frame) == 37
        capture(window, gallery / "10-dark.png")

        assert window.apply_preferences(language="en", theme="light", zoom=100)
        settle(application, window)
        assert window.document.frame.equals(source_frame)
        assert len(window.rules) == 2
        assert len(window.model.frame) == 37
        capture(window, gallery / "11-english.png")

        assert window.apply_preferences(language="en", theme="dark", zoom=100)
        settle(application, window)
        settings = SettingsDialog(window, language="en", theme="dark", zoom=100)
        show_dialog(application, settings, 580, 440)
        capture(settings, gallery / "12-settings.png")
        settings.close()
        settle(application)

        window.page_tabs.setCurrentIndex(0)
        settle(application)
        capture(window, gallery / "13-workspace-dark.png")
        window.dirty = False
        window.close()
        settle(application)
    return {
        "source_rows": 120,
        "source_columns": 8,
        "active_filters": 2,
        "filtered_rows": 37,
        "selected_export_columns": 6,
        "gallery": str(gallery),
        "guide_images": [path.name for path in sorted(gallery.glob("*.png"))],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "docs")
    options = parser.parse_args()
    print(json.dumps(render(options.output_dir.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
