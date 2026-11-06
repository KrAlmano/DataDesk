"""Verify native launch details without changing the shared desktop interface."""

import ctypes
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from datadesk import __version__, app, platforms


@pytest.mark.parametrize(
    "system,keys,expected",
    [
        ("darwin", "Ctrl+O", "Cmd+O"),
        ("darwin", "Ctrl+Shift+F", "Cmd+Shift+F"),
        ("win32", "Ctrl+Shift+F", "Ctrl+Shift+F"),
        ("linux", "Ctrl+0", "Ctrl+0"),
        ("darwin", "F2", "F2"),
    ],
)
def test_shortcut_labels_use_the_platform_key(system, keys, expected):
    assert platforms.shortcut_label(keys, system) == expected


def test_default_export_uses_redirected_known_desktop(monkeypatch, tmp_path):
    desktop = tmp_path / "OneDrive – Şirket" / "Masaüstü"
    desktop.mkdir(parents=True)
    values = {platforms.QStandardPaths.StandardLocation.DesktopLocation: str(desktop)}
    monkeypatch.setattr(
        platforms.QStandardPaths, "writableLocation", lambda location: values.get(location, "")
    )
    assert platforms.default_export_directory() == desktop


def test_missing_desktop_falls_back_to_existing_documents_without_creating_folders(monkeypatch, tmp_path):
    missing = tmp_path / "olmayan-masaüstü"
    documents = tmp_path / "Belgeler"
    documents.mkdir()
    values = {
        platforms.QStandardPaths.StandardLocation.DesktopLocation: str(missing),
        platforms.QStandardPaths.StandardLocation.DocumentsLocation: str(documents),
    }
    monkeypatch.setattr(
        platforms.QStandardPaths, "writableLocation", lambda location: values.get(location, "")
    )
    assert platforms.default_export_directory() == documents
    assert not missing.exists()


def test_missing_known_folders_fall_back_to_home(monkeypatch):
    monkeypatch.setattr(platforms.QStandardPaths, "writableLocation", lambda _: "")
    assert platforms.default_export_directory() == Path.home()


def test_other_platforms_never_call_windows_apis(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("A Windows API was requested on another platform")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    assert platforms.configure_platform_application("darwin") is False
    assert platforms.configure_platform_application("linux") is False


@pytest.mark.parametrize("result,expected", [(0, True), (-1, False)])
def test_windows_taskbar_identity_is_applied_before_window_creation(monkeypatch, result, expected):
    received = []

    class SetAppID:
        def __call__(self, value):
            received.append(value)
            return result

    setter = SetAppID()
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name, **kwargs: SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=setter),
        raising=False,
    )
    assert platforms.configure_platform_application("win32") is expected
    assert received == [platforms.APP_ID]
    assert setter.argtypes == [ctypes.c_wchar_p]
    assert setter.restype is ctypes.c_long


def test_windows_taskbar_api_failure_does_not_block_launch(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise OSError("Shell API unavailable")

    monkeypatch.setattr(ctypes, "WinDLL", unavailable, raising=False)
    assert platforms.configure_platform_application("win32") is False


def test_finder_file_event_waits_for_startup_handler(qtbot, qapp, tmp_path):
    path = tmp_path / "Türkçe rapor.csv"
    path.write_text("Kod;Ad\n001;İpek\n", encoding="utf-8")
    router = platforms.FileOpenRouter(qapp)
    received = []
    try:
        assert QApplication.sendEvent(qapp, QFileOpenEvent(str(path)))
        qtbot.wait(70)
        assert received == []
        router.set_handler(received.append)
        qtbot.waitUntil(lambda: received == [str(path.resolve())])
    finally:
        router.close()


def test_file_open_queue_keeps_order_and_pending_duplicates_while_import_is_busy(qtbot, qapp, tmp_path):
    first = tmp_path / "ilk.xlsx"
    second = tmp_path / "ikinci.csv"
    router = platforms.FileOpenRouter(qapp)
    received = []
    state = {"ready": False}
    try:
        router.set_handler(received.append, lambda: state["ready"])
        router.request_file(str(first))
        router.request_file(str(first))
        router.request_file(str(second))
        qtbot.wait(80)
        assert received == []
        state["ready"] = True
        qtbot.waitUntil(lambda: len(received) == 2)
        assert received == [str(first.resolve()), str(second.resolve())]
        # A later explicit reopen of the same file is allowed.
        router.request_file(str(first))
        qtbot.waitUntil(lambda: len(received) == 3)
        assert received[-1] == str(first.resolve())
    finally:
        router.close()


def test_remote_file_open_urls_are_not_dispatched(qapp):
    router = platforms.FileOpenRouter(qapp)
    try:
        event = QFileOpenEvent(QUrl("https://example.com/data.csv"))
        assert router.eventFilter(qapp, event) is False
        assert not router.pending
    finally:
        router.close()


def test_stopping_router_discards_unprocessed_requests(qtbot, qapp, tmp_path):
    router = platforms.FileOpenRouter(qapp)
    received = []
    router.set_handler(received.append)
    router.request_file(str(tmp_path / "test.csv"))
    router.close()
    qtbot.wait(80)
    assert received == []
    assert not router.timer.isActive()


def test_version_cli_does_not_create_an_application(monkeypatch, capsys):
    monkeypatch.setattr(app, "configure_platform_application", lambda: pytest.fail("GUI setup was requested"))
    assert app.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"DataDesk {__version__}"


def test_startup_ignores_finder_process_serial_number():
    arguments = app._arguments(["-psn_0_12345", "Türkçe veri.xlsx"])
    assert arguments.file == "Türkçe veri.xlsx"


def test_smoke_cli_writes_machine_readable_result_without_entering_normal_event_loop(
    monkeypatch, qapp, tmp_path
):
    calls = []

    def smoke(application):
        calls.append(application)
        return {"checks": ["Qt resources", "file round trip"], "version": __version__}

    monkeypatch.setitem(sys.modules, "datadesk.smoke", SimpleNamespace(run_smoke_test=smoke))
    path = tmp_path / "reports" / "smoke.json"
    assert app.main(["--smoke-test", str(path)]) == 0
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "success"
    assert report["checks"] == ["Qt resources", "file round trip"]
    assert calls == [qapp]


def test_smoke_cli_failure_returns_nonzero_and_preserves_error_details(monkeypatch, qapp, tmp_path):
    def smoke(_application):
        raise ValueError("Türkçe test hatası")

    monkeypatch.setitem(sys.modules, "datadesk.smoke", SimpleNamespace(run_smoke_test=smoke))
    path = tmp_path / "failed.json"
    assert app.main(["--smoke-test", str(path)]) == 1
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["error"] == "Türkçe test hatası"
