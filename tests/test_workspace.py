"""Local workspace operations preserve original files and never replace names."""

import json
from pathlib import Path

import pandas as pd
import pytest

from datadesk import workspace as module
from datadesk.io import read_table, write_table
from datadesk.workspace import MANIFEST_NAME, Workspace, validate_name


@pytest.fixture
def workspace(tmp_path):
    return Workspace(tmp_path / "Çalışma Alanım")


def test_real_folders_and_unicode_spreadsheets_survive_reopening(workspace):
    folder = workspace.create_folder(".", "Müşteri İşleri")
    workbook = workspace.create_table(folder, "Şubat Ödemeleri", ["Müşteri kodu", "İşlem tarihi", "Tutar"])
    reopened = Workspace(workspace.root, create=False)
    entries = reopened.entries()
    assert [entry.name for entry in entries] == ["Müşteri İşleri"]
    assert entries[0].is_dir
    assert entries[0].relative_path == Path("Müşteri İşleri")
    files = reopened.entries(entries[0].relative_path)
    assert len(files) == 1
    assert files[0].name == "Şubat Ödemeleri.xlsx"
    assert files[0].path == workbook
    assert files[0].size > 0
    assert not files[0].is_dir
    result = read_table(workbook).frame
    assert result.empty
    assert result.columns.tolist() == ["Müşteri kodu", "İşlem tarihi", "Tutar"]
    assert reopened.is_managed(workbook)


@pytest.mark.parametrize("file_format", ["xlsx", "csv", "tsv"])
def test_new_files_are_readable_empty_tables_with_exact_headers(workspace, file_format):
    path = workspace.create_table(".", "Veriler", ["Kod", "Ad soyad", "Şehir"], file_format=file_format)
    assert path.suffix == f".{file_format}"
    assert read_table(path).frame.shape == (0, 3)
    assert read_table(path).frame.columns.tolist() == ["Kod", "Ad soyad", "Şehir"]


def test_explicit_supported_extension_is_preserved(workspace):
    path = workspace.create_table(".", "Yeni.CSV", ["Ad"], file_format="xlsx")
    assert path.name == "Yeni.CSV"
    assert read_table(path).frame.columns.tolist() == ["Ad"]


@pytest.mark.parametrize("columns", [[], [""], ["  "], ["A", "A"], ["A", " A "], [None]])
def test_invalid_columns_leave_no_file(workspace, columns):
    with pytest.raises(ValueError):
        workspace.create_table(".", "Veriler", columns)
    assert list(workspace.root.iterdir()) == []


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        ".",
        "..",
        "../dışarı",
        "a/b",
        "a\\b",
        "CON",
        "aux.csv",
        "LPT3",
        "a:",
        "b?",
        "c.",
        " a",
        "a ",
        "a\x00",
    ],
)
def test_portable_names_are_validated(name):
    with pytest.raises(ValueError):
        validate_name(name)


def test_valid_unicode_names(workspace):
    assert validate_name("İstanbul, öğlen (1)") == "İstanbul, öğlen (1)"
    with pytest.raises(ValueError, match="uzun"):
        workspace.create_folder(".", "ş" * 121)


def test_existing_file_and_folder_names_are_never_replaced(workspace):
    existing = workspace.create_table(".", "Rapor", ["İlk"])
    before = existing.read_bytes()
    with pytest.raises(ValueError, match="zaten var"):
        workspace.create_table(".", "rapor.xlsx", ["İkinci"])
    assert existing.read_bytes() == before
    folder = workspace.create_folder(".", "Siparişler")
    with pytest.raises(ValueError, match="zaten var"):
        workspace.create_folder(".", "Siparişler")
    assert folder.is_dir()


def test_case_insensitive_and_unicode_normalized_collisions(workspace):
    workspace.create_folder(".", "Reports")
    with pytest.raises(ValueError, match="zaten var"):
        workspace.create_folder(".", "reports")
    workspace.create_folder(".", "Café")
    with pytest.raises(ValueError, match="zaten var"):
        workspace.create_folder(".", "Cafe\u0301")


@pytest.mark.parametrize("path", ["..", "../gizli", "a/../../gizli"])
def test_navigation_cannot_escape_workspace(workspace, path):
    with pytest.raises(ValueError, match="dışındaki"):
        workspace.resolve(path, must_exist=False)
    with pytest.raises(ValueError):
        workspace.create_folder(path, "Yeni")


def test_absolute_paths_outside_workspace_are_rejected(workspace, tmp_path):
    with pytest.raises(ValueError, match="dışındaki"):
        workspace.resolve(tmp_path)
    with pytest.raises(ValueError):
        workspace.relative(tmp_path / "outside.csv")
    assert workspace.relative(workspace.root) == Path(".")


def test_external_symlinks_cannot_be_listed_created_renamed_or_moved(workspace, tmp_path):
    external = tmp_path / "dışarı"
    external.mkdir()
    (external / "önemli.csv").write_text("Kod\n001\n", encoding="utf-8")
    link = workspace.root / "Bağlantı"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks need developer privileges on this Windows machine")
    assert workspace.entries() == []
    with pytest.raises(ValueError):
        workspace.entries(link)
    with pytest.raises(ValueError):
        workspace.create_table(link, "Yeni", ["A"])
    with pytest.raises(ValueError):
        workspace.rename(link, "Başka")
    assert (external / "önemli.csv").read_text(encoding="utf-8") == "Kod\n001\n"


def test_import_copies_bytes_and_adds_collision_suffixes(workspace, tmp_path):
    source = tmp_path / "Kaynak.csv"
    original = b"Kod;Ad\r\n001;NA\r\n"
    source.write_bytes(original)
    paths = workspace.import_files([source, source])
    assert [path.name for path in paths] == ["Kaynak.csv", "Kaynak (2).csv"]
    assert all(path.read_bytes() == original for path in paths)
    assert source.read_bytes() == original
    assert all(not workspace.is_managed(path) for path in paths)
    assert Workspace(workspace.root).entries()[0].size == len(original)


def test_import_to_nested_folder_and_validation_before_copying(workspace, tmp_path):
    folder = workspace.create_folder(".", "Kasım")
    source = tmp_path / "gelir.tsv"
    source.write_text("Ad\nAli\n", encoding="utf-8")
    invalid = tmp_path / "resim.png"
    invalid.write_bytes(b"not a workbook")
    with pytest.raises(ValueError, match="Yalnızca"):
        workspace.import_files([source, invalid], folder)
    assert list(folder.iterdir()) == []
    assert workspace.import_files([source], folder)[0] == folder / "gelir.tsv"


def test_import_rolls_back_new_copies_on_copy_failure(workspace, tmp_path, monkeypatch):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("A\n1\n", encoding="utf-8")
    second.write_text("A\n2\n", encoding="utf-8")
    original_copy = module.shutil.copy2

    def fail_second(source, target):
        if source == second:
            raise OSError("disk full")
        return original_copy(source, target)

    monkeypatch.setattr(module.shutil, "copy2", fail_second)
    with pytest.raises(ValueError, match="eklenemedi"):
        workspace.import_files([first, second])
    assert list(workspace.root.iterdir()) == []
    assert first.exists() and second.exists()


def test_failed_table_writer_preserves_existing_files_and_cleans_temporary(workspace, monkeypatch):
    existing = workspace.create_table(".", "Asıl", ["A"])
    before = existing.read_bytes()

    def fail(*args, **kwargs):
        raise ValueError("write failure")

    monkeypatch.setattr(module, "write_table", fail)
    with pytest.raises(ValueError, match="write failure"):
        workspace.create_table(".", "Yeni", ["B"])
    assert sorted(path.name for path in workspace.root.iterdir()) == [MANIFEST_NAME, "Asıl.xlsx"]
    assert existing.read_bytes() == before


def test_atomic_create_cannot_replace_file_created_during_write(workspace, monkeypatch):
    original_write = module.write_table
    competing = workspace.root / "Rapor.xlsx"

    def race(frame, temporary, options):
        original_write(frame, temporary, options)
        competing.write_bytes(b"external file")

    monkeypatch.setattr(module, "write_table", race)
    with pytest.raises(ValueError, match="oluşturulamadı"):
        workspace.create_table(".", "Rapor", ["Ad"])
    assert competing.read_bytes() == b"external file"
    assert not workspace.is_managed(competing)
    assert list(workspace.root.iterdir()) == [competing]


def test_import_chooses_another_name_if_concurrent_file_appears(workspace, tmp_path, monkeypatch):
    source = tmp_path / "Rapor.csv"
    source.write_bytes(b"Ad\r\nAli\r\n")
    original_copy = module.shutil.copy2

    def race(original, temporary):
        result = original_copy(original, temporary)
        (workspace.root / source.name).write_bytes(b"external file")
        return result

    monkeypatch.setattr(module.shutil, "copy2", race)
    imported = workspace.import_files([source])
    assert imported[0].name == "Rapor (2).csv"
    assert imported[0].read_bytes() == source.read_bytes()
    assert (workspace.root / "Rapor.csv").read_bytes() == b"external file"


def test_rename_move_and_persisted_ownership_follow_folder_descendants(workspace):
    first = workspace.create_folder(".", "Birinci")
    nested = workspace.create_folder(first, "Alt klasör")
    workbook = workspace.create_table(nested, "Rapor", ["Kod"])
    assert workspace.is_managed(workbook)
    renamed = workspace.rename(first, "Yeni ad")
    path = renamed / "Alt klasör" / "Rapor.xlsx"
    assert workspace.is_managed(path)
    destination = workspace.create_folder(".", "Arşiv")
    moved = workspace.move(renamed, destination)
    path = moved / "Alt klasör" / "Rapor.xlsx"
    assert workspace.is_managed(path)
    reopened = Workspace(workspace.root)
    assert reopened.is_managed(path)
    assert read_table(path).frame.columns.tolist() == ["Kod"]
    assert reopened.entries(destination)[0].name == "Yeni ad"
    payload = json.loads((workspace.root / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["tables"] == ["Arşiv/Yeni ad/Alt klasör/Rapor.xlsx"]


def test_file_rename_keeps_extension_and_existing_files_safe(workspace):
    first = workspace.create_table(".", "First", ["A"])
    second = workspace.create_table(".", "Second", ["B"])
    before = second.read_bytes()
    with pytest.raises(ValueError, match="zaten var"):
        workspace.rename(first, "Second.xlsx")
    with pytest.raises(ValueError, match="uzantısını"):
        workspace.rename(first, "First.csv")
    renamed = workspace.rename(first, "Son.xlsx")
    assert not first.exists()
    assert workspace.is_managed(renamed)
    assert second.read_bytes() == before


def test_move_cannot_overwrite_another_file_or_recurse_into_own_directory(workspace):
    source = workspace.create_folder(".", "A")
    inside = workspace.create_folder(source, "Inside")
    destination = workspace.create_folder(".", "B")
    original = workspace.create_table(source, "Rapor", ["A"])
    other = workspace.create_table(destination, "Rapor", ["B"])
    before = other.read_bytes()
    with pytest.raises(ValueError, match="zaten var"):
        workspace.move(original, destination)
    with pytest.raises(ValueError, match="kendi içine"):
        workspace.move(source, inside)
    with pytest.raises(ValueError, match="ana klasörü"):
        workspace.move(workspace.root, destination)
    with pytest.raises(ValueError, match="ana klasörü"):
        workspace.rename(workspace.root, "Başka")
    assert other.read_bytes() == before
    assert original.exists()


def test_external_replacement_or_edit_revokes_managed_ownership(workspace):
    path = workspace.create_table(".", "Rapor", ["A"])
    assert workspace.is_managed(path)
    write_table(pd.DataFrame({"B": ["001"]}), path)
    assert not workspace.is_managed(path)
    assert not Workspace(workspace.root).is_managed(path)
    assert workspace.register_table(path)
    assert Workspace(workspace.root).is_managed(path)


def test_existing_unmanaged_files_are_never_claimed_automatically(workspace):
    path = workspace.root / "Varolan.csv"
    path.write_text("Ad\nAli\n", encoding="utf-8")
    assert not workspace.is_managed(path)
    assert not Workspace(workspace.root).is_managed(path)


def test_malformed_manifest_is_safe_and_not_shown(workspace):
    path = workspace.create_table(".", "Rapor", ["A"])
    (workspace.root / MANIFEST_NAME).write_text("{broken", encoding="utf-8")
    reopened = Workspace(workspace.root)
    assert not reopened.is_managed(path)
    assert reopened.metadata_warning
    assert [entry.name for entry in reopened.entries()] == ["Rapor.xlsx"]


def test_manifest_failure_does_not_report_successful_creation_or_move_as_failed(workspace, monkeypatch):
    original = module.os.replace

    def fail_metadata(source, target):
        if Path(target).name == MANIFEST_NAME:
            raise PermissionError("manifest is read-only")
        return original(source, target)

    monkeypatch.setattr(module.os, "replace", fail_metadata)
    path = workspace.create_table(".", "Rapor", ["A"])
    assert path.is_file()
    assert not workspace.is_managed(path)
    assert workspace.metadata_warning
    assert read_table(path).frame.columns.tolist() == ["A"]
    assert not any(path.name.startswith(".datadesk-meta-") for path in workspace.root.iterdir())


def test_manifest_failure_after_move_leaves_moved_file_unmanaged(workspace, monkeypatch):
    path = workspace.create_table(".", "Rapor", ["A"])
    destination = workspace.create_folder(".", "Arşiv")
    original = module.os.replace

    def fail_metadata(source, target):
        if Path(target).name == MANIFEST_NAME:
            raise PermissionError("manifest is read-only")
        return original(source, target)

    monkeypatch.setattr(module.os, "replace", fail_metadata)
    moved = workspace.move(path, destination)
    assert moved.is_file()
    assert not path.exists()
    assert not workspace.is_managed(moved)
    assert not Workspace(workspace.root).is_managed(moved)
    assert workspace.metadata_warning
