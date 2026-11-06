"""Reproduce a 100,000-row CSV → filters → sorted XLSX → reopen workflow.

Run from the project root with ``python tools/benchmark.py``. All files are
temporary. Timings describe the current machine; no timing threshold is used.
Expected rows are calculated with Python integer cents and datetime objects,
independently from DataDesk's parsing/filtering implementation.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datadesk.core import FilterRule, apply_filters, sort_frame  # noqa: E402
from datadesk.io import ExportOptions, read_table, write_table  # noqa: E402


ROWS = 100_000
HEADERS = ["Kimlik", "Tutar", "Tarih", "Şehir", "Not", "Adet", "Durum", "Uzun Kod"]
SELECTED = ["Kimlik", "Tutar", "Tarih", "Şehir", "Not", "Uzun Kod"]
CITY_NAMES = ["İstanbul", "Ankara", "İzmir", "Şanlıurfa", "Isparta"]
DATE_START = datetime(2026, 1, 1)
DATE_END_EXCLUSIVE = datetime(2026, 7, 1)
AMOUNT_MIN_CENTS = 125_000
AMOUNT_MAX_CENTS = 750_000


def _record(index: int) -> tuple[list[str], int, datetime]:
    cents = (index * 137) % 2_000_000
    if index % 11 == 0:
        cents = -cents
    day = datetime(2025, 1, 1) + timedelta(days=index % 730, hours=index % 24)
    magnitude = abs(cents)
    integer = f"{magnitude // 100:,}".replace(",", ".")
    amount = f"{'-' if cents < 0 else ''}{integer},{magnitude % 100:02d} TL"
    if index % 17 == 0:
        note = 'Müşteri "Özel"; açıklama, çığ\nİkinci satır'
    elif index % 19 == 0:
        note = "NA"
    elif index % 23 == 0:
        note = "=SUM(1,2)"
    else:
        note = "Ödeme / ürün № " + str(index)
    return (
        [
            f"00{index:06d}",
            amount,
            day.strftime("%d.%m.%Y %H:%M:%S"),
            CITY_NAMES[index % len(CITY_NAMES)],
            note,
            str(index % 31),
            "Evet" if index % 2 else "Hayır",
            f"900719925474099{index % 10}",
        ],
        cents,
        day,
    )


def main() -> None:
    timings: dict[str, float] = {}
    overall = perf_counter()
    expected: list[tuple[int, int, list[str]]] = []
    selected_positions = [HEADERS.index(column) for column in SELECTED]
    with tempfile.TemporaryDirectory(prefix="datadesk-benchmark-") as directory:
        source = Path(directory) / "Türkçe veri.csv"
        target = Path(directory) / "Filtrelenmiş sonuçlar.xlsx"
        started = perf_counter()
        with source.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
            writer.writerow(HEADERS)
            for index in range(ROWS):
                row, cents, day = _record(index)
                writer.writerow(row)
                if (
                    DATE_START <= day < DATE_END_EXCLUSIVE
                    and AMOUNT_MIN_CENTS <= cents <= AMOUNT_MAX_CENTS
                    and index % len(CITY_NAMES) == 0
                ):
                    expected.append((cents, index, row))
        timings["create_csv_seconds"] = perf_counter() - started
        expected.sort(key=lambda item: item[0])
        expected_rows = [tuple(row[pos] for pos in selected_positions) for _, _, row in expected]

        started = perf_counter()
        loaded = read_table(source)
        timings["import_csv_seconds"] = perf_counter() - started
        assert loaded.frame.shape == (ROWS, len(HEADERS)), "CSV row/column count changed"
        assert loaded.encoding == "utf-8-sig", "UTF-8 BOM was not detected"
        assert loaded.delimiter == ";", "CSV delimiter was not detected"
        assert loaded.frame["Kimlik"].tolist() == [f"00{i:06d}" for i in range(ROWS)], (
            "Leading-zero IDs changed"
        )
        assert loaded.frame.iloc[19]["Not"] == "NA", "Literal NA became missing"
        assert loaded.frame.iloc[17]["Not"] == _record(17)[0][4], "Quoted multiline text changed"

        started = perf_counter()
        filtered = apply_filters(
            loaded.frame,
            [
                FilterRule("Tarih", "between", "01.01.2026", "30.06.2026", kind="date"),
                FilterRule("Tutar", "between", "1.250,00", "7.500,00", kind="number", number_format="tr"),
                FilterRule("Şehir", "equals", "istanbul", kind="text"),
            ],
        )
        timings["filter_seconds"] = perf_counter() - started
        assert len(filtered) == len(expected), "Filtered count disagrees with independent Python calculation"

        started = perf_counter()
        ordered = sort_frame(filtered, "Tutar", kind="number", number_format="tr")
        timings["sort_seconds"] = perf_counter() - started
        assert list(ordered.loc[:, SELECTED].itertuples(index=False, name=None)) == expected_rows, (
            "Sorted rows or raw values changed"
        )

        started = perf_counter()
        write_table(ordered, target, ExportOptions(columns=SELECTED))
        timings["export_xlsx_seconds"] = perf_counter() - started
        started = perf_counter()
        reopened = read_table(target)
        timings["reopen_xlsx_seconds"] = perf_counter() - started
        assert reopened.frame.columns.tolist() == SELECTED, "Exported selection/order changed"
        assert list(reopened.frame.itertuples(index=False, name=None)) == expected_rows, (
            "XLSX round trip changed raw values or IDs"
        )
        assert not reopened.warnings, "Unexpected XLSX import warnings"

        report = {
            "input_rows": ROWS,
            "input_columns": len(HEADERS),
            "expected_filtered_rows": len(expected),
            "actual_filtered_rows": len(filtered),
            "exported_columns": len(SELECTED),
            "reopened_rows": len(reopened.frame),
            "csv_bytes": source.stat().st_size,
            "xlsx_bytes": target.stat().st_size,
            "verified": [
                "independent row count and stable numeric order",
                "leading-zero and 16-digit identifiers",
                "Turkish currency, dates and case-insensitive city filter",
                "Unicode, embedded quotes, delimiters and multiline cells",
                "literal NA and formula-looking text",
                "selected XLSX columns and all reopened raw cell values",
            ],
            "timings_seconds": {name: round(value, 4) for name, value in timings.items()},
            "total_seconds": round(perf_counter() - overall, 4),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
