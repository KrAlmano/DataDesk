"""Native integration around the shared DataDesk workspace."""

from collections import deque
from collections.abc import Callable
import ctypes
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QObject, QStandardPaths, QTimer


APP_ID = "io.github.KrAlmano.DataDesk"


def shortcut_label(keys: str, platform: str | None = None) -> str:
    """Describe Qt's portable Control shortcuts using the actual platform key."""
    platform = sys.platform if platform is None else platform
    return keys.replace("Ctrl", "Cmd") if platform == "darwin" else keys


def default_export_directory() -> Path:
    """Use OS-known folders, including redirected Windows/OneDrive desktops."""
    for location in (
        QStandardPaths.StandardLocation.DesktopLocation,
        QStandardPaths.StandardLocation.DocumentsLocation,
        QStandardPaths.StandardLocation.HomeLocation,
    ):
        value = QStandardPaths.writableLocation(location)
        if value and Path(value).is_dir():
            return Path(value)
    return Path.home()


def configure_platform_application(platform: str | None = None) -> bool:
    """Give the Windows taskbar a stable identity before any window is created."""
    platform = sys.platform if platform is None else platform
    if platform != "win32":
        return False
    try:
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        set_id = shell.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes = [ctypes.c_wchar_p]
        set_id.restype = ctypes.c_long
        return set_id(APP_ID) == 0
    except (AttributeError, OSError):
        # A taskbar customization must not prevent the data editor from opening.
        return False


class FileOpenRouter(QObject):
    """Queue local Finder/Dock requests until the shared window is ready.

    A macOS bundle receives QFileOpenEvent instead of ordinary command-line
    arguments. The same queue accepts a Windows command-line file. It avoids
    losing a second request while the first import dialog or worker is active.
    """

    def __init__(self, application):
        super().__init__(application)
        self.application = application
        self.pending = deque()
        self.handler: Callable[[str], object] | None = None
        self.ready: Callable[[], bool] = lambda: True
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._drain)
        application.installEventFilter(self)

    def set_handler(self, handler: Callable[[str], object], ready: Callable[[], bool] | None = None):
        self.handler = handler
        self.ready = ready or (lambda: True)
        if self.pending:
            self.timer.start()

    def request_file(self, path: str):
        if not path:
            return
        normalized = str(Path(path).expanduser().resolve())
        if normalized not in self.pending:
            self.pending.append(normalized)
        self.timer.start()

    def eventFilter(self, watched, event):
        if watched is self.application and event.type() == QEvent.Type.FileOpen:
            path = event.file()
            if not path and event.url().isLocalFile():
                path = event.url().toLocalFile()
            if path:
                self.request_file(path)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _drain(self):
        if not self.pending:
            self.timer.stop()
            return
        if self.handler is not None and self.ready():
            self.handler(self.pending.popleft())

    def close(self):
        self.timer.stop()
        self.pending.clear()
        self.application.removeEventFilter(self)
