from datetime import datetime
from pathlib import Path
import csv
import io
import zipfile

import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

from datadesk.io import ExportOptions, ImportOptions, inspect_file, read_table, write_table


def make_book(path: Path, rows, *, sheet="Veriler"):
    book = Workbook()
    page = book.active
    page.title = sheet
    for row in rows:
        page.append(row)
    book.save(path)
    book.close()


@pytest.mark.parametrize("delimiter", [";", ",", "\t", "|"])
def test_csv_delimiter_quotes_and_multiline_roundtrip(tmp_path, delimiter):
    path = tmp_path / "ürünler.csv"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter)
    writer.writerows(
        [
            ["Kimlik", "Açıklama", "Tutar"],
            ["00123", 'İzmir; çay, "özel"\nyeni satır', "1.234,56"],
            ["NA", "null", ""],
        ]
    )
    path.write_text(stream.getvalue(), encoding="utf-8-sig", newline="")
    info = inspect_file(path)
    assert info.delimiter == delimiter
    table = read_table(path)
    assert list(table.frame.columns) == ["Kimlik", "Açıklama", "Tutar"]
    assert table.frame.iloc[0].tolist() == ["00123", 'İzmir; çay, "özel"\nyeni satır', "1.234,56"]
    assert table.frame.iloc[1].tolist() == ["NA", "null", ""]
    output = tmp_path / "sonuç.csv"
    write_table(table.frame, output, ExportOptions(delimiter=delimiter))
    pd.testing.assert_frame_equal(read_table(output).frame, table.frame)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32", "cp1254"])
def test_csv_encodings(tmp_path, encoding):
    path = tmp_path / "metin.csv"
    path.write_text("Ad;Şehir\nÇağrı;İstanbul\nŞule;Iğdır\n", encoding=encoding)
    table = read_table(path)
    assert table.frame.iloc[0].tolist() == ["Çağrı", "İstanbul"]
    assert table.frame.iloc[1].tolist() == ["Şule", "Iğdır"]
    if encoding == "cp1254":
        assert table.warnings


def test_csv_encoding_override_and_errors(tmp_path):
    path = tmp_path / "western.csv"
    path.write_text("name;city\nFrançois;Málaga", encoding="cp1252")
    assert read_table(path, ImportOptions(encoding="cp1252")).frame.iloc[0].tolist() == ["François", "Málaga"]
    with pytest.raises(ValueError, match="kodlamasıyla"):
        read_table(path, ImportOptions(encoding="utf-8"))
    with pytest.raises(ValueError):
        read_table(path, ImportOptions(encoding="not-an-encoding"))


def test_header_row_duplicate_numeric_blank_columns_no_data_loss(tmp_path):
    path = tmp_path / "başlık.xlsx"
    make_book(
        path,
        [
            ["Rapor"],
            ["Ad", None, "Ad", 2026, "Ad (2)"],
            ["Ali", 7, "Veli", 9, None],
            ["Ayşe", 8, "Can", 10, None],
        ],
    )
    table = read_table(path, ImportOptions(header_row=2))
    assert list(table.frame.columns) == ["Ad", "Sütun 2", "Ad (2)", "2026", "Ad (2) (2)"]
    assert table.frame.iloc[0].tolist() == ["Ali", 7, "Veli", 9, None]
    assert table.frame.shape == (2, 5)
    # No automatic header promotion: the first actual data row survives.
    first = read_table(path)
    assert first.frame.iloc[0, 0] == "Ad"


def test_headerless_and_empty_column(tmp_path):
    path = tmp_path / "headerless.csv"
    path.write_text("001;;NA\n002;;null", encoding="utf-8")
    frame = read_table(path, ImportOptions(header_row=None)).frame
    assert frame.columns.tolist() == ["Sütun 1", "Sütun 2", "Sütun 3"]
    assert frame.iloc[0].tolist() == ["001", "", "NA"]
    assert len(frame) == 2


def test_sheet_selection_dates_zero_mask_and_uncached_formula(tmp_path):
    path = tmp_path / "sayfalar.xlsx"
    book = Workbook()
    book.active.title = "Özet"
    book.active.append(["Yanlış"])
    sheet = book.create_sheet("İşlemler")
    sheet.append(["Kod", "Tarih", "Tutar", "Formül", "Boş"])
    sheet.append([123, datetime(2026, 11, 6), 1234.56, "=C2*2", None])
    sheet["A2"].number_format = "000000"
    book.save(path)
    book.close()
    assert inspect_file(path).sheets == ["Özet", "İşlemler"]
    loaded = read_table(path, ImportOptions(sheet="İşlemler"))
    assert loaded.frame.iloc[0].tolist() == ["000123", datetime(2026, 11, 6), 1234.56, "=C2*2", None]
    assert "1 formül" in loaded.warnings[0]
    assert read_table(path, ImportOptions(sheet=1)).frame.equals(loaded.frame)
    with pytest.raises(ValueError, match="sayfası"):
        read_table(path, ImportOptions(sheet="Kayıp"))


def test_cached_formula_reads_result(tmp_path):
    path = tmp_path / "cached.xlsx"
    make_book(path, [["Tutar"], ["=1+2"]])
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    sheet_path = "xl/worksheets/sheet1.xml"
    files[sheet_path] = files[sheet_path].replace(b"<f>1+2</f><v></v>", b"<f>1+2</f><v>3</v>")
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    loaded = read_table(path)
    assert loaded.frame.iloc[0, 0] == 3
    assert not loaded.warnings


def test_xls_legacy_dates_and_identifiers(tmp_path):
    import xlwt

    path = tmp_path / "eski.xls"
    book = xlwt.Workbook()
    sheet = book.add_sheet("Türkçe")
    for j, text in enumerate(["Kimlik", "Tarih", "Tutar"]):
        sheet.write(0, j, text)
    sheet.write(1, 0, 42, xlwt.easyxf(num_format_str="00000"))
    sheet.write(1, 1, datetime(2026, 11, 6), xlwt.easyxf(num_format_str="DD.MM.YYYY"))
    sheet.write(1, 2, 12.5)
    book.save(str(path))
    assert inspect_file(path).sheets == ["Türkçe"]
    table = read_table(path)
    assert table.frame.iloc[0].tolist() == ["00042", datetime(2026, 11, 6), 12.5]


@pytest.mark.parametrize("text", ["A;B\n1;2;3", "A;B\n1", 'A;B\n"oops;2'])
def test_malformed_csv_rejected_without_skipping_rows(tmp_path, text):
    path = tmp_path / "hatalı.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="CSV"):
        read_table(path, ImportOptions(delimiter=";"))


@pytest.mark.parametrize("header", [0, -1, True, 1.5])
def test_invalid_header_rejected(tmp_path, header):
    path = tmp_path / "data.csv"
    path.write_text("A;B\n1;2", encoding="utf-8")
    with pytest.raises(ValueError, match="Başlık"):
        read_table(path, ImportOptions(header_row=header))


def test_xlsx_roundtrip_keeps_native_values_and_literal_formula_text(tmp_path):
    frame = pd.DataFrame(
        {
            "Kod": ["00123", "NA"],
            "Tutar": [1234.56, -2.5],
            "Tarih": [datetime(2026, 11, 6), None],
            "Metin": ['=HYPERLINK("bad")', "@SUM(A1)"],
            "Büyük": [1234567890123456789, 1],
        },
        dtype=object,
    )
    path = tmp_path / "çıktı.xlsx"
    write_table(frame, path)
    book = load_workbook(path)
    sheet = book.active
    assert sheet.title == "Sonuçlar"
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:E3"
    assert sheet["A2"].value == "00123"
    assert sheet["B2"].value == 1234.56
    assert sheet["C2"].value == datetime(2026, 11, 6)
    assert sheet["D2"].value == '=HYPERLINK("bad")'
    assert sheet["D2"].data_type == "s"
    assert sheet["E2"].value == "1234567890123456789"
    book.close()
    table = read_table(path)
    assert table.frame.iloc[0, 0] == "00123"
    assert table.frame.iloc[0, 3] == '=HYPERLINK("bad")'


@pytest.mark.parametrize("suffix", [".xlsx", ".csv", ".tsv", ".docx"])
def test_selected_columns_order_and_zero_result_headers(tmp_path, suffix):
    frame = pd.DataFrame({"Ad": ["Ali"], "Boş": [None], "Tutar": [5]})
    path = tmp_path / f"empty{suffix}"
    write_table(frame.iloc[:0], path, ExportOptions(columns=["Tutar", "Ad"]))
    assert path.stat().st_size > 0
    if suffix == ".docx":
        from docx import Document

        table = Document(path).tables[0]
        assert [cell.text for cell in table.rows[0].cells] == ["Tutar", "Ad"]
        assert len(table.rows) == 1
    else:
        result = read_table(path).frame
        assert result.columns.tolist() == ["Tutar", "Ad"]
        assert result.empty


def test_csv_formula_safety_can_be_disabled(tmp_path):
    frame = pd.DataFrame({"Metin": ["=1+1", " @SUM(A1)", "-2", "normal"], "Sayı": [-2, 3, 4, 5]})
    path = tmp_path / "safe.csv"
    write_table(frame, path)
    safe = read_table(path).frame
    assert safe["Metin"].tolist() == ["'=1+1", "' @SUM(A1)", "'-2", "normal"]
    assert safe["Sayı"].iloc[0] == "-2"
    write_table(frame, path, ExportOptions(safe_csv=False))
    assert read_table(path).frame["Metin"].tolist() == frame["Metin"].tolist()


def test_failed_export_keeps_existing_file_and_removes_temp(tmp_path):
    path = tmp_path / "existing.csv"
    path.write_bytes(b"original")
    frame = pd.DataFrame({"Ad": ["Şule"]})
    with pytest.raises(ValueError):
        write_table(frame, path, ExportOptions(encoding="ascii"))
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(ValueError, match="sütun"):
        write_table(frame, path, ExportOptions(columns=["missing"]))
    assert path.read_bytes() == b"original"


def test_all_rows_export_not_preview_limited(tmp_path):
    frame = pd.DataFrame({"Kimlik": [f"{i:06}" for i in range(2500)], "Değer": list(range(2500))})
    path = tmp_path / "all.xlsx"
    write_table(frame, path)
    loaded = read_table(path).frame
    assert len(loaded) == 2500
    assert loaded.iloc[-1].tolist() == ["002499", 2499]


def test_empty_invalid_and_unsupported_files(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="boş"):
        read_table(empty)
    broken = tmp_path / "broken.xlsx"
    broken.write_text("not a zip", encoding="utf-8")
    with pytest.raises(ValueError):
        read_table(broken)
    with pytest.raises(ValueError):
        inspect_file(broken)
    with pytest.raises(ValueError):
        read_table(tmp_path / "missing.csv")
    unsupported = tmp_path / "other.txt"
    unsupported.write_text("A", encoding="utf-8")
    with pytest.raises(ValueError, match="Desteklenen"):
        read_table(unsupported)
    with pytest.raises(ValueError, match="çıktı"):
        write_table(pd.DataFrame({"A": [1]}), tmp_path / "output.xls")


def test_csv_preamble_header_can_be_selected(tmp_path):
    path = tmp_path / "report.csv"
    path.write_text("Aylık rapor\nAd;Tutar\nAli;10\n", encoding="utf-8")
    frame = read_table(path, ImportOptions(header_row=2, delimiter=";")).frame
    assert frame.columns.tolist() == ["Ad", "Tutar"]
    assert frame.iloc[0].tolist() == ["Ali", "10"]


def test_csv_blank_records_keep_header_row_and_internal_positions(tmp_path):
    path = tmp_path / "blank.csv"
    path.write_text("\nAd;Tutar\nAli;10\n\nVeli;20\n", encoding="utf-8")
    frame = read_table(path, ImportOptions(header_row=2, delimiter=";")).frame
    assert frame.columns.tolist() == ["Ad", "Tutar"]
    assert frame.values.tolist() == [["Ali", "10"], ["", ""], ["Veli", "20"]]


def test_explicit_utf8_still_removes_bom(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text("Ad;Kod\nAli;001", encoding="utf-8-sig")
    frame = read_table(path, ImportOptions(encoding="utf-8")).frame
    assert frame.columns.tolist() == ["Ad", "Kod"]


@pytest.mark.parametrize(
    "text,delimiter",
    [
        ("a,b\n1,2,3\n", ","),
        ("a,b\n1\n", ","),
        ("a;b\n1;2;3\n", ";"),
        ("a;b\n1\n", ";"),
        ("a|b\n1|2|3\n", "|"),
    ],
)
def test_malformed_csv_auto_detection_does_not_hide_columns(tmp_path, text, delimiter):
    path = tmp_path / "bad-auto.csv"
    path.write_text(text, encoding="utf-8")
    assert inspect_file(path).delimiter == delimiter
    with pytest.raises(ValueError, match="beklenen 2"):
        read_table(path)


@pytest.mark.parametrize(
    "text,values",
    [
        ('"Description, notes"\n"Ali, satış"\n"Veli, destek"\n', ["Ali, satış", "Veli, destek"]),
        ('Description\n"1,23"\n"2,34"\n', ["1,23", "2,34"]),
        ('"Description; notes"\n"Ali; satış"\n"Veli; destek"\n', ["Ali; satış", "Veli; destek"]),
    ],
)
def test_quoted_single_column_separators_are_literal(tmp_path, text, values):
    path = tmp_path / "single.csv"
    path.write_text(text, encoding="utf-8")
    loaded = read_table(path)
    assert loaded.frame.shape == (2, 1)
    assert loaded.frame.iloc[:, 0].tolist() == values


def test_excel_incorrect_dimension_metadata_does_not_truncate_cells(tmp_path):
    import re

    path = tmp_path / "wrong-dimension.xlsx"
    make_book(path, [["Ad", "Kod", "Tutar"], ["Ali", "001", 10], ["Veli", "002", 20]])
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    sheet_path = "xl/worksheets/sheet1.xml"
    files[sheet_path] = re.sub(rb'<dimension ref="[^"]+"/>', b'<dimension ref="A1:A1"/>', files[sheet_path])
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    frame = read_table(path).frame
    assert frame.columns.tolist() == ["Ad", "Kod", "Tutar"]
    assert frame.values.tolist() == [["Ali", "001", 10], ["Veli", "002", 20]]


def test_xlsm_and_time_native_values(tmp_path):
    from datetime import date, time

    path = tmp_path / "macro-enabled.xlsm"
    make_book(
        path, [["Kod", "Tarih", "Saat", "Mantıksal"], ["0001", date(2026, 11, 6), time(14, 23, 45), True]]
    )
    loaded = read_table(path)
    assert loaded.frame.iloc[0].tolist() == ["0001", datetime(2026, 11, 6), time(14, 23, 45), True]
    output = tmp_path / "times.xlsx"
    write_table(loaded.frame, output)
    assert read_table(output).frame.iloc[0].tolist() == loaded.frame.iloc[0].tolist()


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"A": ["x" * 32768]}),
        pd.DataFrame({"x" * 32768: ["A"]}),
        pd.DataFrame({"A": ["bad\x00value"]}),
    ],
)
def test_xlsx_rejects_unrepresentable_text_before_writing_atomically(tmp_path, frame):
    path = tmp_path / "existing.xlsx"
    path.write_bytes(b"original")
    with pytest.raises(ValueError, match="Excel"):
        write_table(frame, path)
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]


def test_legacy_xls_time_is_not_an_arbitrary_1899_date(tmp_path):
    from datetime import time
    import xlwt

    path = tmp_path / "time.xls"
    book = xlwt.Workbook()
    sheet = book.add_sheet("Saatler")
    sheet.write(0, 0, "Saat")
    sheet.write(1, 0, 0.5, xlwt.easyxf(num_format_str="HH:MM:SS"))
    book.save(str(path))
    assert read_table(path).frame.iloc[0, 0] == time(12)


def test_native_duration_xlsx_roundtrip(tmp_path):
    from datetime import timedelta

    path = tmp_path / "duration.xlsx"
    frame = pd.DataFrame({"Süre": [timedelta(days=2, hours=3, minutes=4)]}, dtype=object)
    write_table(frame, path)
    assert read_table(path).frame.iloc[0, 0] == timedelta(days=2, hours=3, minutes=4)
