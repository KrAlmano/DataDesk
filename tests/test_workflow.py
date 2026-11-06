"""Realistic import → combine filters → sort → export → reopen workflows."""

from datetime import datetime
import hashlib

import pandas as pd
import pytest
from openpyxl import Workbook

from datadesk.core import (
    ColumnKind,
    FilterRule,
    apply_filters,
    infer_kind,
    parse_date,
    parse_number,
    sort_frame,
)
from datadesk.io import ExportOptions, ImportOptions, inspect_file, read_table, write_table


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sales_book(path):
    book = Workbook()
    summary = book.active
    summary.title = "Özet"
    summary.append(["Bu sayfa veri tablosu değildir"])
    sales = book.create_sheet("Satışlar")
    sales.append(["Kasım 2026 · Sipariş raporu"])
    sales.append(
        ["Sipariş No", "Müşteri", "Şehir", "Sipariş Tarihi", "Tutar", "Durum", "Not", "NA Kod", None]
    )
    rows = [
        [
            "000012",
            "ÇAĞRI",
            "İSTANBUL",
            "01.11.2026",
            "1.234,56",
            "Onaylandı",
            'Özel; "hızlı"\nteslimat',
            "NA",
            None,
        ],
        ["000003", "Şule", "Ankara", datetime(2026, 11, 6, 18, 30), 2500.5, "Onaylandı", None, "null", None],
        ["000009", "IŞIK", "Istanbul", "30/11/2026", "2,345.67", "Bekliyor", "", "001", None],
        ["000001", "Can", "İzmir", "01.12.2026", "100,00", "Onaylandı", "İade", "0", None],
        ["000021", "İpek", "İstanbul", "06.11.2026", "9,50", "Bekliyor", "", "NULL", None],
    ]
    for row in rows:
        sales.append(row)
    stocks = book.create_sheet("Stok")
    stocks.append(["Ürün", "Adet"])
    stocks.append(["Kahve", 7])
    book.save(path)
    book.close()
    return rows


@pytest.mark.parametrize("suffix", [".xlsx", ".csv", ".tsv"])
def test_multisheet_turkish_sales_filtered_sorted_exported_reopened(tmp_path, suffix):
    source = tmp_path / "kasım satışları.xlsx"
    original_rows = sales_book(source)
    before_digest = digest(source)
    assert inspect_file(source).sheets == ["Özet", "Satışlar", "Stok"]
    source_frame = read_table(source, ImportOptions(sheet="Satışlar", header_row=2)).frame
    assert source_frame.shape == (5, 9)
    assert source_frame.columns[-1] == "Sütun 9"
    assert source_frame.iloc[0].tolist() == original_rows[0]
    assert infer_kind(source_frame["Sipariş No"]) == ColumnKind.TEXT
    assert infer_kind(source_frame["Tutar"]) == ColumnKind.NUMBER
    assert infer_kind(source_frame["Sipariş Tarihi"]) == ColumnKind.DATE
    pristine = source_frame.copy(deep=True)
    filtered = apply_filters(
        source_frame,
        [
            FilterRule("Sipariş Tarihi", "between", "01.11.2026", "30.11.2026"),
            FilterRule("Tutar", "gte", "1.000,00"),
            FilterRule("Şehir", "any_words", "istanbul ankara"),
            FilterRule("Durum", "any_words", "onaylandı bekliyor"),
        ],
    )
    assert filtered.index.tolist() == [0, 1, 2]
    sorted_frame = sort_frame(filtered, "Tutar", ascending=False)
    assert sorted_frame["Sipariş No"].tolist() == ["000003", "000009", "000012"]
    assert sorted_frame["Tutar"].tolist() == [2500.5, "2,345.67", "1.234,56"]
    pd.testing.assert_frame_equal(source_frame, pristine)
    selected_columns = ["Sipariş No", "Tutar", "Şehir", "Sipariş Tarihi", "NA Kod", "Not"]
    output = tmp_path / f"kasım sonuçları{suffix}"
    write_table(sorted_frame, output, ExportOptions(columns=selected_columns))
    result = read_table(output).frame
    assert result.columns.tolist() == selected_columns
    assert len(result) == 3
    assert result["Sipariş No"].tolist() == ["000003", "000009", "000012"]
    assert result["NA Kod"].tolist() == ["null", "001", "NA"]
    assert [parse_number(value) for value in result["Tutar"]] == [2500.5, 2345.67, 1234.56]
    assert [parse_date(value) for value in result["Sipariş Tarihi"]] == [
        pd.Timestamp("2026-11-06 18:30"),
        pd.Timestamp("2026-11-30"),
        pd.Timestamp("2026-11-01"),
    ]
    assert result.iloc[-1]["Not"] == 'Özel; "hızlı"\nteslimat'
    assert digest(source) == before_digest
    assert read_table(source, ImportOptions(sheet="Stok")).frame.iloc[0].tolist() == ["Kahve", 7]


@pytest.mark.parametrize("suffix", [".xlsx", ".csv"])
def test_zero_matches_export_headers_without_falling_back_to_source(tmp_path, suffix):
    source = tmp_path / "source.xlsx"
    sales_book(source)
    source_frame = read_table(source, ImportOptions(sheet="Satışlar", header_row=2)).frame
    result = apply_filters(source_frame, [FilterRule("Müşteri", "equals", "Olmayan kişi")])
    assert result.empty
    path = tmp_path / f"zero{suffix}"
    write_table(result, path, ExportOptions(columns=["Sipariş No", "Müşteri"]))
    reopened = read_table(path).frame
    assert reopened.empty
    assert reopened.columns.tolist() == ["Sipariş No", "Müşteri"]


def test_cp1254_csv_or_rules_literal_search_and_numeric_sort(tmp_path):
    source = tmp_path / "eski türkçe.csv"
    source.write_text(
        'Kimlik;Ad;Şehir;Tutar\r\n001;Çağrı;İSTANBUL;"1.234,50"\r\n002;Şule;Ankara;"2.000,00"\r\n003;IŞIK;İzmir;"999,99"\r\n004;İpek;İstanbul;"3.000,50"\r\n',
        encoding="cp1254",
    )
    before = digest(source)
    loaded = read_table(source)
    assert loaded.warnings
    result = apply_filters(
        loaded.frame,
        [FilterRule("Şehir", "equals", "istanbul"), FilterRule("Ad", "equals", "şule")],
        match="any",
    )
    assert result["Kimlik"].tolist() == ["001", "002", "004"]
    result = sort_frame(result, "Tutar", ascending=False)
    assert result["Kimlik"].tolist() == ["004", "002", "001"]
    query = apply_filters(result, [], search="ÇAĞRI")
    assert query["Kimlik"].tolist() == ["001"]
    out = tmp_path / "sonuç.xlsx"
    write_table(result, out)
    reopened = read_table(out).frame
    assert reopened["Kimlik"].tolist() == ["004", "002", "001"]
    assert reopened["Tutar"].tolist() == ["3.000,50", "2.000,00", "1.234,50"]
    assert digest(source) == before
