"""Application entry point; no Tk or browser runtime is required."""

import sys
from pathlib import Path

from PySide6.QtCore import QLocale
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .ui import MainWindow
from .theme import configure_app


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("DataDesk")
    app.setOrganizationName("DataDesk")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "icon.svg")))
    configure_app(app)
    QLocale.setDefault(QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey))
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, lambda: window.open_path(sys.argv[1]))
    return app.exec()
