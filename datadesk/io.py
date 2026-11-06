"""Loss-conscious table import and atomic export, independent from the UI.

CSV fields stay strings; interpretation belongs to the filtering engine. Excel
values stay native, except numeric identifiers with an explicit zero mask.
"""

from __future__ import annotations

import codecs
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import io
from itertools import islice, zip_longest
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

import pandas as pd

INPUT_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv", ".tsv"}
OUTPUT_SUFFIXES = {".xlsx", ".csv", ".tsv", ".docx"}


@dataclass(frozen=True)
class ImportOptions:
    sheet: str | int = 0
    header_row: int | None = 1
    delimiter: str | None = None
    encoding: str | None = None


@dataclass
class FileInfo:
    sheets: list[str] = field(default_factory=list)
    encoding: str | None = None
    delimiter: str | None = None
    path: Path | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class LoadedTable:
    frame: pd.DataFrame
    sheet: str | None = None
    warnings: list[str] = field(default_factory=list)
    encoding: str | None = None
    delimiter: str | None = None


@dataclass(frozen=True)
class ExportOptions:
    columns: list[str] | None = None
    delimiter: str = ";"
    encoding: str = "utf-8-sig"
    sheet_name: str = "Sonuçlar"
    safe_csv: bool = True


def _source(path: str | Path) -> Path:
    path = Path(path).expanduser()
    if not path.is_file():
        raise ValueError(f"Dosya bulunamadı: {path.name}")
    if path.suffix.lower() not in INPUT_SUFFIXES:
        raise ValueError("Desteklenen giriş biçimleri: XLSX, XLSM, XLS, CSV ve TSV.")
    return path


def _decode(data: bytes, encoding: str | None = None) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if encoding:
        try:
            return data.decode(encoding).removeprefix("\ufeff"), encoding, warnings
        except (UnicodeError, LookupError) as exc:
            raise ValueError(f"Dosya {encoding} kodlamasıyla okunamadı. Kodlamayı değiştirin.") from exc
    if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        chosen = "utf-32"
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        chosen = "utf-16"
    elif data.startswith(codecs.BOM_UTF8):
        chosen = "utf-8-sig"
    else:
        try:
            return data.decode("utf-8"), "utf-8", warnings
        except UnicodeError:
            chosen = "cp1254"
            warnings.append(
                "UTF-8 olmayan CSV, Windows Türkçe (CP1254) ile okundu. "
                "Harfler yanlış görünüyorsa içe aktarma kodlamasını CP1252 veya başka bir kodlama olarak değiştirin."
            )
    try:
        return data.decode(chosen), chosen, warnings
    except UnicodeError as exc:
        raise ValueError("Dosyanın metin kodlaması belirlenemedi. Kodlamayı elle seçin.") from exc


def _delimiter(text: str, suffix: str, header_row: int | None = 1) -> str:
    if suffix == ".tsv":
        return "\t"
    sample = text[:65536]
    sniffed = None
    try:
        sniffed = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        pass
    candidates: list[tuple[float, int, bool, str]] = []
    evidence: list[tuple[int, int, str]] = []
    for candidate in (";", "\t", "|", ","):
        try:
            rows = list(islice(csv.reader(io.StringIO(sample), delimiter=candidate), 50))
        except csv.Error:
            continue
        start = (header_row - 1) if header_row is not None else 0
        relevant = rows[start:]
        lengths = [len(row) for row in relevant if row]
        if not lengths:
            continue
        # Header evidence is deliberately retained even when later records have
        # inconsistent lengths: choosing a one-column fallback would hide the
        # malformed CSV and silently swallow its actual columns.
        header_width = len(rows[start]) if header_row is not None and start < len(rows) else lengths[0]
        if header_width > 1:
            consistency = sum(length == header_width for length in lengths) / len(lengths)
            candidates.append((consistency, header_width, candidate == sniffed, candidate))
        split_rows = sum(length > 1 for length in lengths)
        if split_rows:
            evidence.append((split_rows, max(lengths), candidate))
    if candidates:
        return max(candidates)[3]
    if sniffed:
        return sniffed
    # Unquoted separators in body-only records are ambiguous. Prefer an
    # explicit field-count error over concealing possibly malformed columns;
    # users can override the separator for intentionally single-column data.
    if evidence:
        return max(evidence)[2]
    # Quoted comma/semicolon text still parses as a single field.
    return ";"


def _valid_delimiter(delimiter: str) -> None:
    if len(delimiter) != 1 or delimiter in {"\r", "\n", '"'}:
        raise ValueError("CSV ayıracı tek bir karakter olmalıdır (ör. ; , veya sekme).")


def inspect_file(path: str | Path) -> FileInfo:
    path = _source(path)
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        try:
            text, encoding, warnings = _decode(path.read_bytes())
        except ValueError:
            return FileInfo(
                path=path,
                warnings=[
                    "Metin kodlaması otomatik belirlenemedi. İçe aktarma penceresinde kodlamayı elle seçin."
                ],
            )
        return FileInfo(encoding=encoding, delimiter=_delimiter(text, suffix), path=path, warnings=warnings)
    try:
        if suffix == ".xls":
            import xlrd

            book = xlrd.open_workbook(path, on_demand=True)
            try:
                sheets = book.sheet_names()
            finally:
                book.release_resources()
        else:
            from openpyxl import load_workbook

            book = load_workbook(path, read_only=True, data_only=True)
            try:
                sheets = book.sheetnames
            finally:
                book.close()
    except Exception as exc:
        raise ValueError(f"Excel dosyası açılamadı: {exc}") from exc
    return FileInfo(sheets=sheets, path=path)


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _headers(values: list[Any]) -> list[str]:
    """Create stable unique labels without discarding unnamed columns."""
    result: list[str] = []
    used: set[str] = set()
    for position, value in enumerate(values, 1):
        name = f"Sütun {position}" if _blank(value) else str(value).strip()
        name = name or f"Sütun {position}"
        unique = name
        counter = 2
        while unique in used:
            unique = f"{name} ({counter})"
            counter += 1
        result.append(unique)
        used.add(unique)
    return result


def _make_frame(rows: list[list[Any]], header_row: int | None, *, trim: bool = False) -> pd.DataFrame:
    if header_row is not None and (isinstance(header_row, bool) or header_row < 1):
        raise ValueError("Başlık satırı 1 veya daha büyük olmalıdır.")
    if not rows:
        raise ValueError("Dosya veya seçilen sayfa boş.")
    relevant = rows if header_row is None else rows[header_row - 1 :]
    if not relevant:
        raise ValueError("Başlık satırı dosyadaki satır sayısını aşıyor.")
    width = max(map(len, relevant))
    if not width:
        raise ValueError("Dosyada okunabilir sütun bulunamadı.")
    if header_row is None:
        columns = [f"Sütun {i + 1}" for i in range(width)]
        data = rows
    else:
        if header_row > len(rows):
            raise ValueError("Başlık satırı dosyadaki satır sayısını aşıyor.")
        head = rows[header_row - 1]
        columns = _headers(head + [None] * (width - len(head)))
        data = rows[header_row:]
    if trim:
        while data and all(_blank(value) for value in data[-1]):
            data.pop()
    padded = [row + [None] * (width - len(row)) for row in data]
    return pd.DataFrame(padded, columns=columns, dtype=object)


def _sheet_name(sheets: list[str], sheet: str | int) -> str:
    if isinstance(sheet, int) and not isinstance(sheet, bool):
        if 0 <= sheet < len(sheets):
            return sheets[sheet]
    elif isinstance(sheet, str) and sheet in sheets:
        return sheet
    raise ValueError("Seçilen Excel sayfası bulunamadı.")


def _zero_mask(value: Any, number_format: str) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and value == int(value) and re.fullmatch(r"0{2,}", number_format):
            return str(int(value)).zfill(len(number_format))
    return value


def _read_xlsx(path: Path, options: ImportOptions) -> LoadedTable:
    from openpyxl import load_workbook

    formula_book = load_workbook(path, read_only=True, data_only=False)
    value_book = None
    try:
        name = _sheet_name(formula_book.sheetnames, options.sheet)
        value_book = load_workbook(path, read_only=True, data_only=True)
        formula_sheet, value_sheet = formula_book[name], value_book[name]
        declared_width = formula_sheet.max_column or 0
        # Third-party writers sometimes declare A1:A1 despite actual cells far
        # beyond it. Scan actual XML records instead of trusting that boundary.
        formula_sheet.reset_dimensions()
        value_sheet.reset_dimensions()
        rows = []
        uncached = 0
        for formulas, values in zip(formula_sheet.iter_rows(), value_sheet.iter_rows()):
            output = []
            for cell, cached in zip_longest(formulas, values):
                value = cached.value if cached is not None else None
                if cell is not None and cell.data_type == "f" and value is None:
                    value = cell.value
                    uncached += 1
                output.append(_zero_mask(value, cell.number_format if cell is not None else "General"))
            rows.append(output + [None] * max(0, declared_width - len(output)))
        warnings = []
        if uncached:
            warnings.append(
                f"{uncached} formül hücresinin kayıtlı sonucu yok; formül metni gösteriliyor. "
                "Sonuçlarla filtrelemek için dosyayı Excel veya LibreOffice'te yeniden hesaplayıp kaydedin. "
                "DataDesk formülleri yeniden hesaplamaz."
            )
        return LoadedTable(_make_frame(rows, options.header_row, trim=True), sheet=name, warnings=warnings)
    finally:
        formula_book.close()
        if value_book is not None:
            value_book.close()


def _read_xls(path: Path, options: ImportOptions) -> LoadedTable:
    import xlrd

    book = xlrd.open_workbook(path, formatting_info=True, on_demand=True)
    try:
        name = _sheet_name(book.sheet_names(), options.sheet)
        sheet = book.sheet_by_name(name)
        rows = []
        for i in range(sheet.nrows):
            row = []
            for j in range(sheet.ncols):
                cell = sheet.cell(i, j)
                value = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    converted = xlrd.xldate_as_datetime(value, book.datemode)
                    value = converted.time() if 0 <= value < 1 else converted
                elif cell.ctype in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK}:
                    value = None
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(value)
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    value = xlrd.error_text_from_code.get(value, f"#ERROR {value}")
                elif cell.ctype == xlrd.XL_CELL_NUMBER:
                    fmt = book.format_map.get(book.xf_list[cell.xf_index].format_key)
                    if fmt:
                        value = _zero_mask(value, fmt.format_str)
                row.append(value)
            rows.append(row)
        return LoadedTable(_make_frame(rows, options.header_row, trim=True), sheet=name)
    finally:
        book.release_resources()


def read_table(path: str | Path, options: ImportOptions | None = None) -> LoadedTable:
    path = _source(path)
    options = options or ImportOptions()
    if options.header_row is not None and (
        not isinstance(options.header_row, int)
        or isinstance(options.header_row, bool)
        or options.header_row < 1
    ):
        raise ValueError("Başlık satırı 1 veya daha büyük olmalıdır.")
    try:
        if path.suffix.lower() == ".xls":
            return _read_xls(path, options)
        if path.suffix.lower() in {".xlsx", ".xlsm"}:
            return _read_xlsx(path, options)
        text, encoding, warnings = _decode(path.read_bytes(), options.encoding)
        delimiter = options.delimiter or _delimiter(text, path.suffix.lower(), options.header_row)
        _valid_delimiter(delimiter)
        rows: list[list[Any]] = []
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        try:
            for row in reader:
                rows.append(row)
        except csv.Error as exc:
            raise ValueError(f"CSV, {reader.line_num}. satırda okunamadı: {exc}") from exc
        start = (options.header_row - 1) if options.header_row is not None else 0
        if rows and start < len(rows):
            width = (
                len(rows[start])
                if options.header_row is not None
                else next((len(row) for row in rows if row), 0)
            )
            for i, row in enumerate(rows[start:], start + 1):
                if not row:
                    rows[i - 1] = [""] * width
                    continue
                if len(row) != width:
                    raise ValueError(
                        f"CSV {i}. kayıtta {len(row)} alan içeriyor; beklenen {width}. "
                        "Ayıraç ve tırnak işaretlerini kontrol edin. Hiçbir satır atlanmadı."
                    )
        return LoadedTable(
            _make_frame(rows, options.header_row), encoding=encoding, delimiter=delimiter, warnings=warnings
        )
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Dosya okunamadı: {exc}") from exc


def _excel_value(value: Any) -> Any:
    if _blank(value):
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes, datetime, date, time, timedelta)):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.isoformat()
    # Excel stores only 15 significant decimal digits. Keep identifiers exact.
    if isinstance(value, int) and not isinstance(value, bool) and len(str(abs(value))) > 15:
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool, date, datetime, time, timedelta)):
        return value
    return str(value)


def _write_xlsx(frame: pd.DataFrame, target: Path, options: ExportOptions) -> None:
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    if len(frame) > 1_048_575 or len(frame.columns) > 16_384:
        raise ValueError("Excel sınırı aşıldı (1.048.575 veri satırı, 16.384 sütun). CSV kullanın.")
    if (
        not options.sheet_name
        or len(options.sheet_name) > 31
        or re.search(r"[\\/*?:\[\]]", options.sheet_name)
    ):
        raise ValueError("Excel sayfa adı 1–31 karakter olmalı ve \\ / * ? : [ ] içermemelidir.")

    # openpyxl otherwise truncates overlong strings. Validate before opening
    # its streaming XML writer so a rejected export leaves no partial streams.
    def validate_text(value: str) -> None:
        if len(value) > 32767:
            raise ValueError("Bir hücre veya başlık Excel'in 32.767 karakter sınırını aşıyor. CSV kullanın.")
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
            raise ValueError(
                "Bir hücre Excel'in desteklemediği denetim karakteri içeriyor. CSV kullanın veya metni düzeltin."
            )

    for column in frame.columns:
        validate_text(str(column))
    for row in frame.itertuples(index=False, name=None):
        for value in row:
            if isinstance(value, str):
                validate_text(value)
    book = Workbook(write_only=True)
    sheet = book.create_sheet(options.sheet_name)
    sheet.freeze_panes = "A2"
    sheet.sheet_view.showGridLines = False
    sample = frame.head(200)
    for i, col in enumerate(frame.columns, 1):
        width = min(
            48, max(12, len(str(col)) + 3, *(min(len(str(v)), 45) + 2 for v in sample[col] if not _blank(v)))
        )
        sheet.column_dimensions[get_column_letter(i)].width = width
    header = []
    for value in frame.columns:
        cell = WriteOnlyCell(sheet, value=str(value))
        cell.data_type = "s"
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
        cell.fill = PatternFill("solid", fgColor="244B47")
        cell.alignment = Alignment(vertical="center")
        header.append(cell)
    sheet.append(header)
    for row in frame.itertuples(index=False, name=None):
        cells = []
        for raw in row:
            value = _excel_value(raw)
            if isinstance(value, str) and len(value) > 32767:
                raise ValueError("Bir hücre Excel'in 32.767 karakter sınırını aşıyor. CSV kullanın.")
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                cell.data_type = "s"
            elif isinstance(value, timedelta):
                cell.number_format = "[h]:mm:ss"
            elif isinstance(value, (datetime, date)):
                cell.number_format = (
                    "dd.mm.yyyy hh:mm:ss"
                    if isinstance(value, datetime) and value.time() != time()
                    else "dd.mm.yyyy"
                )
            cells.append(cell)
        sheet.append(cells)
    if len(frame.columns):
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(frame.columns))}{len(frame) + 1}"
    book.save(target)
    book.close()


def _csv_value(value: Any, safe: bool) -> Any:
    if _blank(value):
        return ""
    if isinstance(value, (datetime, date, time, pd.Timestamp)):
        return value.isoformat()
    if safe and isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _write_csv(frame: pd.DataFrame, target: Path, options: ExportOptions, suffix: str) -> None:
    delimiter = "\t" if suffix == ".tsv" else options.delimiter
    _valid_delimiter(delimiter)
    with target.open("w", encoding=options.encoding, newline="") as output:
        writer = csv.writer(output, delimiter=delimiter, lineterminator="\r\n")
        writer.writerow([_csv_value(str(v), options.safe_csv) for v in frame.columns])
        for row in frame.itertuples(index=False, name=None):
            writer.writerow([_csv_value(value, options.safe_csv) for value in row])


def _write_docx(frame: pd.DataFrame, target: Path) -> None:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Pt

    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Cm(29.7), Cm(21)
    section.left_margin = section.right_margin = Cm(1.2)
    document.add_heading("DataDesk · Sonuçlar", 0)
    document.add_paragraph(f"{len(frame):,} satır · {len(frame.columns)} sütun")
    table = document.add_table(rows=1, cols=len(frame.columns))
    table.style = "Light Shading Accent 1"
    for cell, column in zip(table.rows[0].cells, frame.columns):
        cell.text = str(column)
    for row in frame.itertuples(index=False, name=None):
        for cell, value in zip(table.add_row().cells, row):
            cell.text = "" if _blank(value) else str(value)
    document.styles["Normal"].font.size = Pt(9)
    document.save(target)


def write_table(frame: pd.DataFrame, path: str | Path, options: ExportOptions | None = None) -> Path:
    """Write the complete selected frame; replace the destination only on success."""
    options = options or ExportOptions()
    path = Path(path).expanduser()
    suffix = path.suffix.lower()
    if suffix not in OUTPUT_SUFFIXES:
        raise ValueError("Desteklenen çıktı biçimleri: XLSX, CSV, TSV ve DOCX.")
    if not frame.columns.is_unique:
        raise ValueError("Çıktı sütun başlıkları benzersiz olmalıdır.")
    if options.columns is not None:
        if len(set(options.columns)) != len(options.columns) or any(
            col not in frame.columns for col in options.columns
        ):
            raise ValueError("Çıktı sütun seçimi geçersiz.")
        frame = frame.loc[:, options.columns]
    if not len(frame.columns):
        raise ValueError("Dışa aktarmak için en az bir sütun seçin.")
    if not path.parent.is_dir():
        raise ValueError("Çıktı klasörü bulunamadı.")
    handle, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=suffix, dir=path.parent)
    os.close(handle)
    target = Path(temporary)
    try:
        if suffix == ".xlsx":
            _write_xlsx(frame, target, options)
        elif suffix == ".docx":
            _write_docx(frame, target)
        else:
            _write_csv(frame, target, options, suffix)
        os.replace(target, path)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Dosya kaydedilemedi: {exc}") from exc
    finally:
        target.unlink(missing_ok=True)
    return path
