"""Build the same DataDesk UI natively for macOS or Windows."""

import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys
import tomllib

from generate_icons import generate_icons

ROOT = Path(__file__).resolve().parents[1]


def native_target():
    return {"darwin": "macos", "win32": "windows"}.get(sys.platform)


def build(platform_name=None, output_dir=None):
    target = platform_name or native_target()
    if not target or target != native_target():
        raise ValueError("Build macOS packages on macOS and Windows packages on Windows.")
    machine = platform.machine().lower()
    if target == "windows" and machine not in ("amd64", "x86_64"):
        raise ValueError("The Windows installer requires an x64 Python build.")
    if target == "macos" and machine not in ("arm64", "x86_64"):
        raise ValueError("Supported Mac architectures: arm64 and x86_64.")
    output = Path(output_dir or ROOT / "dist").resolve()
    # Build/cache folders belong to this checkout, independent of shell cwd.
    generate_icons()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    parts = tuple(int(value) for value in version.split("."))
    parts = (parts + (0, 0, 0, 0))[:4]
    (ROOT / "build" / "windows-version.txt").write_text(
        f"VSVersionInfo(ffi=FixedFileInfo(filevers={parts!r},prodvers={parts!r},mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('CompanyName','KrAlmano'),StringStruct('FileDescription','DataDesk'),StringStruct('FileVersion','{version}'),StringStruct('InternalName','DataDesk'),StringStruct('OriginalFilename','DataDesk.exe'),StringStruct('ProductName','DataDesk'),StringStruct('ProductVersion','{version}')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])",
        encoding="utf-8",
    )
    environment = {**os.environ, "DATADESK_BUILD_ROOT": str(ROOT)}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(output),
            "--workpath",
            str(ROOT / "build" / "pyinstaller"),
            str(ROOT / "packaging" / "DataDesk.spec"),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    application = output / "DataDesk.app" if target == "macos" else output / "DataDesk" / "DataDesk.exe"
    if not application.exists():
        raise RuntimeError(f"The expected application was not built: {application}")
    print(application)
    return application


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("macos", "windows"))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    arguments = parser.parse_args()
    try:
        build(arguments.platform, arguments.output_dir)
    except ValueError as error:
        parser.error(str(error))
