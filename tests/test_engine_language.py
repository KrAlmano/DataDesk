"""Interface language changes messages, never user data or filter semantics."""

from contextlib import contextmanager
from pathlib import Path
from string import Formatter

import pandas as pd
from PySide6.QtCore import Qt
import pytest

from datadesk.core import FilterRule, apply_filters, display_value, sort_frame
from datadesk.i18n import language, set_language
from datadesk.io import ExportOptions, ImportOptions, inspect_file, read_table, write_table
from datadesk.models import TableModel
from datadesk.translations_engine import EN
from datadesk.workspace import MANIFEST_NAME, Workspace, validate_name


@contextmanager
def using_language(code):
    previous = language()
    set_language(code)
    try:
        yield
    finally:
        set_language(previous)


@pytest.fixture
def english():
    with using_language("en"):
        yield


def test_engine_catalog_keeps_every_interpolation_field():
    def fields(message):
        return {(name, spec, conversion) for _, name, spec, conversion in Formatter().parse(message) if name}

    for source, translated in EN.items():
        assert fields(source) == fields(translated), source


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        (FilterRule("Tutar", "contains", ""), "A filter value is required."),
        (FilterRule("Tutar", "equals", "?", kind="number"), "Enter a value in the selected number format"),
        (FilterRule("Tutar", "equals", "?", kind="date"), "Enter a valid date"),
        (FilterRule("Tutar", "equals", "?", kind="boolean"), "Enter Yes / No or True / False."),
        (FilterRule("Tutar", "between", "3", "1", kind="number"), "The start of the range cannot"),
        (FilterRule("Tutar", "between", "1", "", kind="number"), "Enter the start and end"),
        (FilterRule("Tutar", "equals", "", kind="number"), "use the 'Is empty' filter"),
        (FilterRule("Tutar", "gt", "x", kind="text"), "Choose Number or Date"),
        (FilterRule("Tutar", "in", ";;;"), "Enter at least one matching value."),
        (FilterRule("Tutar", "equals", "1", kind="invalid"), "Invalid column type."),
        (FilterRule("Tutar", "equals", "1", number_format="invalid"), "Invalid number format"),
        (FilterRule("Tutar", "{işlem}"), "Unknown filter operator: {işlem}"),
        (FilterRule("{Başlık}", "equals", "1"), "Column not found: {Başlık}"),
    ],
)
def test_filter_errors_are_english_and_preserve_dynamic_values(english, rule, message):
    with pytest.raises(ValueError) as error:
        apply_filters(pd.DataFrame({"Tutar": [1, 2]}), [rule])
    assert message in str(error.value)


def test_number_example_and_sort_errors_are_english(english):
    with pytest.raises(ValueError, match="1234,56 or 1234.56"):
        apply_filters(pd.DataFrame({"Sayı": [1]}), [FilterRule("Sayı", "equals", "x", kind="number")])
    with pytest.raises(ValueError, match="Column not found: Metin"):
        sort_frame(pd.DataFrame({"Tutar": [1]}), "Metin")
    with pytest.raises(ValueError, match="Filter matching must"):
        apply_filters(pd.DataFrame({"Tutar": [1]}), [], match="bad")


@pytest.mark.parametrize("code", ["tr", "en"])
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("yes", [0, 4]),
        ("no", [1, 5]),
        ("true", [0, 6]),
        ("false", [1, 7]),
        ("evet", [0, 2]),
        ("HAYIR", [1, 3]),
    ],
)
def test_native_boolean_search_accepts_both_languages_without_translating_strings(code, query, expected):
    frame = pd.DataFrame({"Metin": [True, False, "Evet", "Hayır", "yes", "no", "true", "false", None]})
    before = frame.copy(deep=True)
    with using_language(code):
        assert apply_filters(frame, [], search=query).index.tolist() == expected
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("code", ["tr", "en"])
def test_native_boolean_dtype_search_is_consistent(code):
    frame = pd.DataFrame({"Onay": [True, False]})
    with using_language(code):
        assert apply_filters(frame, [], search="yes").index.tolist() == [0]
        assert apply_filters(frame, [], search="Hayır").index.tolist() == [1]


@pytest.mark.parametrize("code", ["tr", "en"])
@pytest.mark.parametrize(
    ("operator", "query", "expected"),
    [
        ("contains", "yes", [0, 4, 8]),
        ("contains", "false", [1, 7]),
        ("not_contains", "yes", [1, 2, 3, 5, 6, 7, 9]),
        ("starts_with", "ye", [0, 4, 8]),
        ("ends_with", "es", [0, 4]),
        ("ends_with", "NO", [1, 5]),
        ("all_words", "yes", [0, 4, 8]),
        ("any_words", "yes false", [0, 1, 4, 7, 8]),
        ("all_words", "yes ter", [8]),
    ],
)
def test_boolean_text_operators_accept_both_languages_without_translating_strings(
    code, operator, query, expected
):
    frame = pd.DataFrame(
        {"Metin": [True, False, "Evet", "Hayır", "yes", "no", "true", "false", "yesterday", None]}
    )
    before = frame.copy(deep=True)
    with using_language(code):
        rule = FilterRule("Metin", operator, query, kind="text")
        assert apply_filters(frame, [rule]).index.tolist() == expected
    pd.testing.assert_frame_equal(frame, before)


def test_filter_and_sort_results_are_identical_across_languages():
    frame = pd.DataFrame(
        {
            "Tutar": ["1.250,50", "0001", "2.600,00"],
            "Onay": [True, False, True],
            "Metin": ["Evet", "No", "Yes"],
        },
        index=[5, 10, 15],
    )
    rules = [FilterRule("Tutar", "gte", "1200", kind="number", number_format="tr")]
    results = []
    for code in ["tr", "en"]:
        with using_language(code):
            results.append(
                sort_frame(apply_filters(frame, rules), "Tutar", kind="number", number_format="tr")
            )
            assert display_value(True) == "Evet"
            assert display_value(False) == "Hayır"
    pd.testing.assert_frame_equal(results[0], results[1])
    assert results[0].index.tolist() == [5, 15]


@pytest.mark.parametrize("suffix", [".xlsx", ".csv", ".tsv"])
def test_english_export_does_not_translate_values_headers_or_filename(english, tmp_path, suffix):
    frame = pd.DataFrame(
        {"Metin": ["Evet", "Hayır", "Sonuçlar"], "Tarih": ["00001", "{name}", "Sayı"]}, dtype=object
    )
    path = tmp_path / ("Sonuçlar {name}" + suffix)
    write_table(frame, path)
    result = read_table(path)
    assert path.name == "Sonuçlar {name}" + suffix
    pd.testing.assert_frame_equal(result.frame, frame)
    if suffix == ".xlsx":
        assert result.sheet == "Sonuçlar"  # Public export default remains backward-compatible.


def test_english_generated_headers_preserve_real_turkish_headings(english, tmp_path):
    path = tmp_path / "Başlık.csv"
    path.write_text(";Metin;Sonuçlar;Sütun 1\n001;Hayır;{name};x\n", encoding="utf-8")
    table = read_table(path)
    assert list(table.frame.columns) == ["Column 1", "Metin", "Sonuçlar", "Sütun 1"]
    assert table.frame.iloc[0].tolist() == ["001", "Hayır", "{name}", "x"]
    headerless = read_table(path, ImportOptions(header_row=None))
    assert list(headerless.frame.columns) == ["Column 1", "Column 2", "Column 3", "Column 4"]
    assert headerless.frame.iloc[0].tolist() == ["", "Metin", "Sonuçlar", "Sütun 1"]


def test_english_decode_and_formula_warnings_preserve_data(english, tmp_path):
    from openpyxl import Workbook

    csv_path = tmp_path / "Türkçe.csv"
    csv_path.write_bytes("Şehir;Tutar\nİstanbul;001\n".encode("cp1254"))
    table = read_table(csv_path)
    assert table.warnings and "Windows Turkish (CP1254)" in table.warnings[0]
    assert table.frame.iloc[0].tolist() == ["İstanbul", "001"]
    path = tmp_path / "Formül.xlsx"
    book = Workbook()
    book.active.title = "Sonuçlar"
    book.active.append(["Sayı", "Metin"])
    book.active.append(["=1+1", "Hayır"])
    book.save(path)
    book.close()
    table = read_table(path)
    assert table.sheet == "Sonuçlar"
    assert inspect_file(path).sheets == ["Sonuçlar"]
    assert table.frame.iloc[0].tolist() == ["=1+1", "Hayır"]
    assert "Formula cells without a saved result: 1" in table.warnings[0]
    assert "does not recalculate formulas" in table.warnings[0]


def test_english_import_and_export_validation(english, tmp_path):
    with pytest.raises(ValueError, match=r"File not found: Sonuçlar \{name\}.xlsx"):
        read_table(tmp_path / "Sonuçlar {name}.xlsx")
    malformed = tmp_path / "Veriler.csv"
    malformed.write_text("A;B\n1;2;3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV record 2 contains 3 fields; expected 2"):
        read_table(malformed, ImportOptions(delimiter=";"))
    with pytest.raises(ValueError, match="The CSV delimiter must be one character"):
        read_table(malformed, ImportOptions(delimiter=";;"))
    frame = pd.DataFrame({"Metin": ["Evet"]})
    with pytest.raises(ValueError, match="An Excel sheet name must contain"):
        write_table(frame, tmp_path / "Sonuçlar.xlsx", ExportOptions(sheet_name="a/b"))
    with pytest.raises(ValueError, match="Select at least one column"):
        write_table(frame, tmp_path / "Sonuçlar.csv", ExportOptions(columns=[]))


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "Enter a name."),
        ("CON", "This name is reserved by Windows"),
        (".gizli", "cannot start with a dot"),
        ("a/b", "cannot contain"),
    ],
)
def test_english_workspace_name_validation(english, name, message):
    with pytest.raises(ValueError) as error:
        validate_name(name)
    assert message in str(error.value)


def test_english_workspace_new_sheet_and_warnings_preserve_names(english, tmp_path):
    workspace = Workspace(tmp_path / "Dosyalar")
    folder = workspace.create_folder(".", "Metin {name}")
    path = workspace.create_table(folder, "Sonuçlar", ["Metin", "Sayı"])
    assert path.name == "Sonuçlar.xlsx"
    assert path.parent.name == "Metin {name}"
    table = read_table(path)
    assert table.sheet == "Sheet1"
    assert list(table.frame.columns) == ["Metin", "Sayı"]
    with pytest.raises(ValueError, match=r"“Metin \{name\}” already exists"):
        workspace.create_folder(".", "Metin {name}")
    with pytest.raises(ValueError, match="outside the workspace"):
        workspace.resolve(Path("..") / "Dosyalar")
    (workspace.root / MANIFEST_NAME).write_text("invalid json", encoding="utf-8")
    reopened = Workspace(workspace.root, create=False)
    assert "existing files will be protected by using Save As" in reopened.metadata_warning


def test_english_docx_labels_preserve_table_values(english, tmp_path):
    from docx import Document

    path = tmp_path / "Sonuçlar.docx"
    write_table(pd.DataFrame({"Metin": ["Hayır"]}), path)
    document = Document(path)
    assert document.paragraphs[0].text == "DataDesk · Results"
    assert document.paragraphs[1].text == "Rows: 1 · Columns: 1"
    assert document.tables[0].cell(0, 0).text == "Metin"
    assert document.tables[0].cell(1, 0).text == "Hayır"


def test_model_localizes_native_booleans_and_type_tooltips_without_dirtying_data(qapp, english):
    calls = []
    model = TableModel(lambda *args: calls.append(args) or True)
    frame = pd.DataFrame({"Metin {kind}": [True, False], "Sayı": ["Evet", "Hayır"]})
    before = frame.copy(deep=True)
    model.replace(frame)
    assert model.data(model.index(0, 0)) == "Yes"
    assert model.data(model.index(1, 0), Qt.ItemDataRole.EditRole) == "No"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole) == "Yes"
    assert model.data(model.index(0, 1)) == "Evet"
    assert model.data(model.index(1, 1)) == "Hayır"
    assert model.headerData(0, Qt.Orientation.Horizontal) == "Metin {kind}"
    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) == (
        "Metin {kind} · Boolean\nClick to sort."
    )
    assert not model.setData(model.index(0, 0), "Yes")
    assert not model.setData(model.index(1, 0), "No")
    assert not calls
    with using_language("tr"):
        assert model.data(model.index(0, 0)) == "Evet"
        assert model.data(model.index(1, 0)) == "Hayır"
        assert not model.setData(model.index(0, 0), "Evet")
    pd.testing.assert_frame_equal(frame, before)
