"""One desktop workspace with platform-specific launch integration."""

import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .ui import MainWindow
from .theme import configure_app
from . import __version__
from .i18n import set_language
from .platforms import APP_ID, FileOpenRouter, configure_platform_application


def _arguments(argv):
    parser = argparse.ArgumentParser(prog="DataDesk", description="Yerel Excel ve CSV çalışma alanı")
    parser.add_argument("file", nargs="?", help="Açılacak Excel, CSV veya TSV dosyası")
    parser.add_argument("--version", action="store_true", help="Sürümü göster")
    parser.add_argument("--smoke-test", metavar="RAPOR.json", help=argparse.SUPPRESS)
    # Finder may pass this process serial number when starting an app bundle.
    return parser.parse_args([value for value in argv if not value.startswith("-psn_")])


def _smoke_report(app, destination):
    try:
        from .smoke import run_smoke_test

        report = run_smoke_test(app)
        report.setdefault("status", "success")
    except Exception as error:
        report = {"status": "failed", "error": str(error) or type(error).__name__, "version": __version__}
    path = Path(destination).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return 1
    return 0 if report["status"] == "success" else 1


def main(argv=None):
    arguments = _arguments(sys.argv[1:] if argv is None else argv)
    if arguments.version:
        if sys.stdout is not None:
            print(f"DataDesk {__version__}")
        return 0
    configure_platform_application()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("DataDesk")
    app.setApplicationDisplayName("DataDesk")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("DataDesk")
    app.setOrganizationDomain("KrAlmano.github.io")
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "icon.svg")))
    settings = QSettings("DataDesk", "DataDesk")
    theme = str(settings.value("ui_theme", "light"))
    language = str(settings.value("ui_language", "tr"))
    configure_app(app, theme if theme in {"light", "dark", "system"} else "light")
    set_language(language if language in {"tr", "en"} else "tr")
    if arguments.smoke_test:
        return _smoke_report(app, arguments.smoke_test)
    router = FileOpenRouter(app)
    window = MainWindow()
    router.set_handler(window.open_path, lambda: not window.busy and window.import_dialog is None)
    window.show()
    if arguments.file:
        router.request_file(arguments.file)
    try:
        return app.exec()
    finally:
        router.close()
