# -*- mode: python ; coding: utf-8 -*-
"""One shared application, with native launchers and platform metadata."""

import os
from pathlib import Path
import platform
import sys
import tomllib
from PyInstaller.utils.hooks import copy_metadata

root = Path(os.environ["DATADESK_BUILD_ROOT"])
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
is_mac = sys.platform == "darwin"
sign_identity = os.environ.get("MACOS_SIGN_IDENTITY") or None
icon = root / "build" / "icons" / ("datadesk.icns" if is_mac else "datadesk.ico")
metadata = []
for distribution in ("PySide6-Essentials", "shiboken6", "pandas", "numpy", "openpyxl", "xlrd", "python-docx", "lxml", "python-dateutil", "tzdata"):
    metadata += copy_metadata(distribution)

analysis = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "datadesk" / "assets"), "datadesk/assets"), (str(root / "LICENSE"), "."), (str(root / "packaging" / "THIRD_PARTY_NOTICES.txt"), "."), *metadata],
    hiddenimports=["PySide6.QtSvg", "openpyxl", "xlrd", "docx"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "xlwt", "IPython", "matplotlib", "scipy", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
    optimize=0,
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="DataDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=platform.machine() if is_mac else None,
    codesign_identity=sign_identity,
    entitlements_file=None,
    icon=str(icon),
    version=None if is_mac else str(root / "build" / "windows-version.txt"),
)
collection = COLLECT(executable, analysis.binaries, analysis.datas, strip=False, upx=False, name="DataDesk")
if is_mac:
    application = BUNDLE(
        collection,
        name="DataDesk.app",
        icon=str(icon),
        bundle_identifier="io.github.KrAlmano.DataDesk",
        version=version,
        info_plist={
            "CFBundleDisplayName": "DataDesk",
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMinimumSystemVersion": "14.0",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Excel and delimited data",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "CFBundleTypeExtensions": ["xlsx", "xlsm", "xls", "csv", "tsv"],
            }],
        },
    )
