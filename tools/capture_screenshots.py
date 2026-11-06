"""Render reproducible UI screenshots from synthetic data (no user files)."""

from pathlib import Path
import sys
import tempfile
import time

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datadesk.core import FilterRule  # noqa: E402
from datadesk.ui import MainWindow  # noqa: E402
from datadesk.theme import configure_app  # noqa: E402


def main():
    output = Path(__file__).resolve().parents[1] / "docs"
    app = QApplication.instance() or QApplication([])
    configure_app(app)
    with tempfile.TemporaryDirectory(prefix="datadesk-preview-") as temporary:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, temporary)
        window = MainWindow()
        window.resize(1440, 900)
        window.show()
        app.processEvents()
        window.grab().save(str(output / "screenshot-empty.png"))
        window.open_demo()
        window.apply_view(
            rules=[
                FilterRule("Tutar", "between", "5.000,00", "20.000,00", "number", "tr"),
                FilterRule("Durum", "equals", "Tamamlandı", kind="text"),
            ]
        )
        deadline = time.monotonic() + 10
        while window.busy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        if window.busy:
            raise RuntimeError("Preview operation timed out")
        window.column.setCurrentText("Şehir")
        window.value.setText("İstanbul")
        window.notice.hide()
        app.processEvents()
        window.grab().save(str(output / "screenshot-filters.png"))
        window.filter_tabs.setCurrentIndex(1)
        app.processEvents()
        window.grab().save(str(output / "screenshot.png"))
        window.resize(800, 600)
        window.set_zoom(100)
        app.processEvents()
        window.grab().save(str(output / "screenshot-compact.png"))
        window.toggle_filters()
        window.filter_tabs.setCurrentIndex(0)
        window.column.setCurrentText("Tutar")
        window.operator.setCurrentIndex(window.operator.findData("between"))
        window.value.setText("1000")
        window.value2.setText("20000")
        app.processEvents()
        window.filter_scroll.verticalScrollBar().setValue(0)
        window.grab().save(str(output / "screenshot-compact-filters.png"))
        window.toggle_filters()
        window.set_zoom(150)
        app.processEvents()
        window.grab().save(str(output / "screenshot-zoom.png"))
        print(f"Rendered {len(window.model.frame)} matching rows; screenshots saved in {output}")
        window.close()


if __name__ == "__main__":
    main()
