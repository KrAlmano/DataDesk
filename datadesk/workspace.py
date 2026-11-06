"""Real local folders and spreadsheet files, confined to one chosen workspace.

The workspace is an ordinary directory. No catalogue or virtual filesystem is
required, so files remain usable from Excel and Finder/Explorer after DataDesk
has closed. Creating and importing files never replaces an existing entry.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
import ctypes
import errno
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata

import pandas as pd

from .io import ExportOptions, INPUT_SUFFIXES, write_table
from .translations_engine import tr

TABLE_SUFFIXES = {".xlsx", ".csv", ".tsv"}
MANIFEST_NAME = ".datadesk.json"


class WorkspaceCollision(ValueError):
    """A portable case-insensitive name already exists."""


_RESERVED_NAMES = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)


@dataclass(frozen=True)
class WorkspaceEntry:
    name: str
    path: Path
    relative_path: Path
    is_dir: bool
    size: int
    modified: datetime


def validate_name(name: str) -> str:
    """Use the same portable file-name rules on macOS and Windows."""
    if not isinstance(name, str) or not name or not name.strip():
        raise ValueError(tr("Bir ad yazın."))
    if name.startswith("."):
        raise ValueError(tr("Ad nokta ile başlayamaz."))
    if name != name.strip() or name.endswith("."):
        raise ValueError(tr("Adın başında veya sonunda boşluk, sonunda nokta bulunamaz."))
    if name in {".", ".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError(tr('Ad; / \\ : * ? " < > | veya denetim karakteri içeremez.'))
    if _RESERVED_NAMES.match(name):
        raise ValueError(tr("Bu ad Windows tarafından ayrılmış. Başka bir ad seçin."))
    if len(name.encode("utf-8")) > 240:
        raise ValueError(tr("Ad çok uzun. Daha kısa bir ad yazın."))
    return name


def _name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _rename_exclusive(source: Path, target: Path) -> None:
    """Rename without replacement, including the last filesystem-level race."""
    if os.name == "nt":
        # Unlike POSIX rename, Windows rename already fails if target exists.
        os.rename(source, target)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        arguments = (os.fsencode(source), os.fsencode(target), 0x00000004)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        arguments = (-100, os.fsencode(source), -100, os.fsencode(target), 1)  # RENAME_NOREPLACE
    else:
        raise OSError(errno.ENOTSUP, tr("Güvenli taşıma bu sistemde desteklenmiyor."))
    rename.restype = ctypes.c_int
    if rename(*arguments) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(target))


class Workspace:
    def __init__(self, root: str | Path, *, create: bool = True):
        path = Path(root).expanduser()
        try:
            if create:
                path.mkdir(parents=True, exist_ok=True)
            if not path.is_dir():
                raise ValueError(tr("Çalışma alanı klasörü bulunamadı."))
            self.root = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(tr("Çalışma alanı açılamadı: {error}", error=exc)) from exc
        self.metadata_warning = ""
        self._managed = self._load_managed()

    def _load_managed(self) -> dict[str, dict[str, int]]:
        manifest = self.root / MANIFEST_NAME
        if manifest.is_symlink():
            self.metadata_warning = tr(
                "Çalışma alanı kaydı bir bağlantı; dosyalar güvenli kaydetme için tanınamadı."
            )
            return {}
        if not manifest.exists():
            return {}
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            if payload.get("version") != 1 or not isinstance(payload.get("tables"), list):
                raise ValueError("invalid manifest")
            identities = payload.get("identities", {})
            result = {}
            for name in payload["tables"]:
                if not isinstance(name, str):
                    continue
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
                    continue
                identity = identities.get(name)
                if (
                    isinstance(identity, dict)
                    and set(identity) == {"device", "inode", "size", "mtime_ns"}
                    and all(isinstance(value, int) for value in identity.values())
                ):
                    result[name] = identity
            return result
        except (OSError, ValueError, TypeError, AttributeError):
            self.metadata_warning = tr(
                "Çalışma alanı kaydı okunamadı; mevcut dosyalar Farklı Kaydet ile korunacak."
            )
            return {}

    @staticmethod
    def _identity(path: Path) -> dict[str, int]:
        info = path.stat()
        return {
            "device": info.st_dev,
            "inode": info.st_ino,
            "size": info.st_size,
            "mtime_ns": info.st_mtime_ns,
        }

    def _persist_managed(self, managed: dict[str, dict[str, int]]) -> bool:
        temporary = None
        try:
            handle, temporary_name = tempfile.mkstemp(prefix=".datadesk-meta-", suffix=".json", dir=self.root)
            temporary = Path(temporary_name)
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                json.dump(
                    {"version": 1, "tables": sorted(managed), "identities": managed},
                    output,
                    ensure_ascii=False,
                    indent=2,
                )
                output.write("\n")
            os.replace(temporary, self.root / MANIFEST_NAME)
            self._managed = managed
            self.metadata_warning = ""
            return True
        except OSError:
            # The table operation has already succeeded. Do not report that
            # creation/move failed or risk overwriting it on a repeated click.
            self.metadata_warning = tr(
                "Dosya işlemi tamamlandı ancak çalışma alanı kaydı güncellenemedi. "
                "Bu dosyada Farklı Kaydet kullanın."
            )
            return False
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def register_table(self, path: str | Path) -> bool:
        target = self.resolve(path)
        if not target.is_file() or target.suffix.lower() not in TABLE_SUFFIXES:
            raise ValueError(tr("Kaydedilebilir bir XLSX, CSV veya TSV dosyası seçin."))
        try:
            identity = self._identity(target)
        except OSError as exc:
            self.metadata_warning = tr("Dosya kaydı güncellenemedi: {error}", error=exc)
            return False
        managed = dict(self._managed)
        managed[target.relative_to(self.root).as_posix()] = identity
        return self._persist_managed(managed)

    def is_managed(self, path: str | Path) -> bool:
        try:
            target = self.resolve(path)
            key = target.relative_to(self.root).as_posix()
            return target.is_file() and self._managed.get(key) == self._identity(target)
        except (ValueError, OSError):
            return False

    def _relocated(self, source: Path, target: Path) -> None:
        source_key = source.relative_to(self.root)
        target_key = target.relative_to(self.root)
        managed = {}
        changed = False
        for key, identity in self._managed.items():
            relative = Path(key)
            if relative.is_relative_to(source_key):
                relative = target_key / relative.relative_to(source_key)
                changed = True
            managed[relative.as_posix()] = identity
        if changed:
            self._persist_managed(managed)

    def resolve(self, relative: str | Path = ".", *, must_exist: bool = True) -> Path:
        """Accept relative paths or absolute paths already inside this workspace."""
        path = Path(relative)
        if ".." in path.parts:
            raise ValueError(tr("Çalışma alanının dışındaki bir yol kullanılamaz."))
        candidate = path if path.is_absolute() else self.root / path
        try:
            resolved = candidate.resolve(strict=must_exist)
        except (OSError, RuntimeError) as exc:
            raise ValueError(tr("Dosya veya klasör bulunamadı ya da erişilemiyor.")) from exc
        if not resolved.is_relative_to(self.root):
            raise ValueError(tr("Çalışma alanının dışındaki bir yol kullanılamaz."))
        # Avoid treating a linked entry as the real file when renaming/moving.
        # A user may explicitly choose a linked root; inside it links are omitted.
        try:
            lexical_relative = candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(tr("Çalışma alanının dışındaki bir yol kullanılamaz.")) from exc
        current = self.root
        for part in lexical_relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(tr("Çalışma alanında sembolik bağlantılar kullanılamaz."))
        if must_exist and not resolved.exists():
            raise ValueError(tr("Dosya veya klasör bulunamadı."))
        return resolved

    def relative(self, path: str | Path) -> Path:
        return self.resolve(path, must_exist=False).relative_to(self.root)

    def _directory(self, relative: str | Path) -> Path:
        directory = self.resolve(relative)
        if not directory.is_dir():
            raise ValueError(tr("Bir klasör seçin."))
        return directory

    def entries(self, relative: str | Path = ".") -> list[WorkspaceEntry]:
        directory = self._directory(relative)
        entries = []
        try:
            for child in directory.iterdir():
                if child.name.startswith(".") or child.is_symlink():
                    continue
                try:
                    path = self.resolve(child)
                    is_dir = path.is_dir()
                    if not is_dir and (not path.is_file() or path.suffix.lower() not in INPUT_SUFFIXES):
                        continue
                    info = path.stat()
                except (ValueError, OSError):
                    # Files may disappear between listing and stat; refresh will
                    # pick up their new location without breaking the whole view.
                    continue
                entries.append(
                    WorkspaceEntry(
                        child.name,
                        path,
                        path.relative_to(self.root),
                        is_dir,
                        0 if is_dir else info.st_size,
                        datetime.fromtimestamp(info.st_mtime),
                    )
                )
        except OSError as exc:
            raise ValueError(tr("Klasör okunamadı: {error}", error=exc)) from exc
        return sorted(entries, key=lambda item: (not item.is_dir, _name_key(item.name)))

    @staticmethod
    def _available(directory: Path, name: str, *, exclude: Path | None = None) -> Path:
        validate_name(name)
        key = _name_key(name)
        for existing in directory.iterdir():
            if existing != exclude and _name_key(existing.name) == key:
                raise WorkspaceCollision(tr("“{name}” zaten var. Başka bir ad seçin.", name=name))
        target = directory / name
        if target.exists() or target.is_symlink():
            if exclude != target:
                raise WorkspaceCollision(tr("“{name}” zaten var. Başka bir ad seçin.", name=name))
        return target

    @staticmethod
    def _publish(temporary: Path, target: Path) -> None:
        # Native exclusive rename supports APFS/NTFS and removable FAT/exFAT,
        # while an exists()+replace() pair could overwrite a concurrent file.
        _rename_exclusive(temporary, target)

    def create_folder(self, parent: str | Path, name: str) -> Path:
        try:
            target = self._available(self._directory(parent), name)
            target.mkdir()
            return target
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(tr("Klasör oluşturulamadı: {error}", error=exc)) from exc

    def create_table(
        self,
        parent: str | Path,
        name: str,
        columns: Sequence[str],
        *,
        file_format: str = "xlsx",
    ) -> Path:
        file_format = file_format.lower().lstrip(".")
        if f".{file_format}" not in TABLE_SUFFIXES:
            raise ValueError(tr("Yeni dosya biçimi XLSX, CSV veya TSV olmalıdır."))
        validate_name(name)
        suffix = Path(name).suffix.lower()
        if suffix not in TABLE_SUFFIXES:
            name += f".{file_format}"
        if not columns or any(not isinstance(column, str) or not column.strip() for column in columns):
            raise ValueError(tr("En az bir boş olmayan sütun adı yazın."))
        headings = [column.strip() for column in columns]
        if len(set(headings)) != len(headings):
            raise ValueError(tr("Sütun adları birbirinden farklı olmalıdır."))
        if len(headings) > 16_384 and Path(name).suffix.lower() == ".xlsx":
            raise ValueError(tr("Excel dosyasında en fazla 16.384 sütun olabilir."))
        temporary = None
        try:
            target = self._available(self._directory(parent), name)
            handle, temporary_name = tempfile.mkstemp(
                prefix=".datadesk-create-", suffix=target.suffix, dir=target.parent
            )
            os.close(handle)
            temporary = Path(temporary_name)
            write_table(
                pd.DataFrame(columns=headings, dtype=object),
                temporary,
                ExportOptions(sheet_name=tr("Sayfa1"), safe_csv=False),
            )
            self._publish(temporary, target)
            self.register_table(target)
            return target
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(tr("Dosya oluşturulamadı: {error}", error=exc)) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def import_files(self, sources: Iterable[str | Path], parent: str | Path = ".") -> list[Path]:
        directory = self._directory(parent)
        originals = [Path(source).expanduser() for source in sources]
        for source in originals:
            if not source.is_file():
                raise ValueError(tr("Dosya bulunamadı: {name}", name=source.name))
            if source.suffix.lower() not in INPUT_SUFFIXES:
                raise ValueError(tr("Yalnızca XLSX, XLSM, XLS, CSV ve TSV dosyaları eklenebilir."))
            validate_name(source.name)
        imported = []
        temporary = None
        try:
            for source in originals:
                number = 1
                while True:
                    name = source.name if number == 1 else f"{source.stem} ({number}){source.suffix}"
                    try:
                        target = self._available(directory, name)
                        break
                    except WorkspaceCollision:
                        number += 1
                handle, temporary_name = tempfile.mkstemp(
                    prefix=".datadesk-import-", suffix=target.suffix, dir=directory
                )
                os.close(handle)
                temporary = Path(temporary_name)
                shutil.copy2(source, temporary)
                # A different process may have chosen the same available name
                # while copying a large workbook. Try the next suffix safely.
                while True:
                    try:
                        self._publish(temporary, target)
                        break
                    except FileExistsError:
                        number += 1
                        name = f"{source.stem} ({number}){source.suffix}"
                        try:
                            target = self._available(directory, name)
                        except WorkspaceCollision:
                            continue
                imported.append(target)
                temporary = None
            return imported
        except (ValueError, OSError) as exc:
            for target in reversed(imported):
                target.unlink(missing_ok=True)
            if isinstance(exc, ValueError):
                raise
            raise ValueError(tr("Dosyalar eklenemedi: {error}", error=exc)) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def rename(self, relative: str | Path, new_name: str) -> Path:
        source = self.resolve(relative)
        if source == self.root:
            raise ValueError(tr("Çalışma alanının ana klasörü yeniden adlandırılamaz."))
        validate_name(new_name)
        if source.is_file() and Path(new_name).suffix.lower() != source.suffix.lower():
            raise ValueError(tr("Dosyanın uzantısını değiştirmeden yeniden adlandırın."))
        if source.name == new_name:
            return source
        try:
            target = self._available(source.parent, new_name)
            self._publish(source, target)
            self._relocated(source, target)
            return target
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(tr("Ad değiştirilemedi: {error}", error=exc)) from exc

    def move(self, relative: str | Path, destination_parent: str | Path) -> Path:
        source = self.resolve(relative)
        destination = self._directory(destination_parent)
        if source == self.root:
            raise ValueError(tr("Çalışma alanının ana klasörü taşınamaz."))
        if source.parent == destination:
            return source
        if source.is_dir() and destination.is_relative_to(source):
            raise ValueError(tr("Bir klasör kendi içine taşınamaz."))
        try:
            target = self._available(destination, source.name)
            self._publish(source, target)
            self._relocated(source, target)
            return target
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(tr("Dosya veya klasör taşınamadı: {error}", error=exc)) from exc
