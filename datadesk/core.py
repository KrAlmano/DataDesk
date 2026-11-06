"""Lossless, UI-independent filtering and sorting for DataDesk.

Conversion is only used to build comparison keys. Source cells and row indexes
are never rewritten, including identifiers, unsupported values and empty cells.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from numbers import Real
from typing import Iterable

import pandas as pd

from .translations_engine import tr


class ColumnKind(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class FilterRule:
    column: str
    operator: str
    value: str = ""
    value2: str = ""
    kind: str = "auto"
    number_format: str = "auto"


def _missing(value: object) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _empty(value: object) -> bool:
    return _missing(value) or (isinstance(value, str) and not value.strip())


def normalize_text(value: object) -> str:
    """Case-insensitive text with dotted/dotless Turkish I treated alike."""
    return display_value(value).translate(str.maketrans({"İ": "i", "I": "i", "ı": "i"})).casefold()


def _text_matches(value: object, query: str, operator: str = "contains") -> bool:
    """Match native boolean labels in either language; string cells stay literal."""
    if pd.api.types.is_bool(value):
        labels = ("evet", "yes", "true") if value else ("hayir", "no", "false")
    else:
        labels = (normalize_text(value),)
    if operator == "starts_with":
        return any(label.startswith(query) for label in labels)
    if operator == "ends_with":
        return any(label.endswith(query) for label in labels)
    return any(query in label for label in labels)


def display_value(value: object) -> str:
    if _missing(value):
        return ""
    if isinstance(value, (datetime, date, pd.Timestamp)):
        stamp = pd.Timestamp(value)
        if (
            stamp.hour == stamp.minute == stamp.second == stamp.microsecond == stamp.nanosecond == 0
            and not stamp.tzinfo
        ):
            return stamp.strftime("%d.%m.%Y")
        result = stamp.strftime("%d.%m.%Y %H:%M:%S")
        if stamp.microsecond or stamp.nanosecond:
            result += "." + f"{stamp.microsecond:06d}{stamp.nanosecond:03d}".rstrip("0")
        if stamp.tzinfo:
            offset = stamp.strftime("%z")
            result += offset[:3] + ":" + offset[3:]
        return result
    if isinstance(value, bool):
        return "Evet" if value else "Hayır"
    return str(value)


_CURRENCY = re.compile(r"(?i)^(?:TRY|USD|EUR|GBP|TL|₺|\$|€|£)\s*|\s*(?:TRY|USD|EUR|GBP|TL|₺|\$|€|£)$")


def _validate_number_format(number_format: str) -> None:
    if number_format not in {"auto", "tr", "us"}:
        raise ValueError(tr("Geçersiz sayı biçimi; Otomatik, Türkçe veya İngilizce seçin."))


def _localized_number_text(text: str, number_format: str) -> str | None:
    """Validate an explicit locale before removing its grouping separator."""
    decimal, grouping = (",", ".") if number_format == "tr" else (".", ",")
    sign = text[:1] if text.startswith(("+", "-")) else ""
    unsigned = text[len(sign) :]
    parts = unsigned.split(decimal)
    if len(parts) > 2:
        return None
    integer = parts[0]
    fraction = parts[1] if len(parts) == 2 else None
    if fraction is not None and fraction and not fraction.isdigit():
        return None
    if grouping in integer:
        if not re.fullmatch(rf"\d{{1,3}}(?:\{grouping}\d{{3}})+", integer):
            return None
        integer = integer.replace(grouping, "")
    elif not integer.isdigit():
        if integer or not fraction:
            return None
        integer = "0"
    return sign + integer + ("." + fraction if fraction is not None else "")


def _number_decimal(value: object, number_format: str = "auto") -> Decimal | None:
    """Read decimal dots/commas and unambiguous TR/US grouped numbers.

    Auto treats a single separator as decimal. Explicit ``tr``/``us`` formats
    disambiguate grouped thousands. Native numeric values are locale-neutral.
    """
    _validate_number_format(number_format)
    if _missing(value) or isinstance(value, bool):
        return None
    if isinstance(value, (Real, Decimal)):
        try:
            result = Decimal(str(value))
            return result if result.is_finite() else None
        except InvalidOperation:
            return None
    text = str(value).strip()
    if not text:
        return None
    text = _CURRENCY.sub("", text).strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
        text = _CURRENCY.sub("", text).strip()
        if text.startswith(("+", "-")):
            return None
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    # Space grouping is accepted only when groups contain three digits.
    if re.search(r"[\s\u00a0\u202f]", text):
        if not re.fullmatch(r"[+-]?\d{1,3}(?:[\s\u00a0\u202f]\d{3})+(?:[.,]\d+)?", text):
            return None
        text = re.sub(r"[\s\u00a0\u202f]", "", text)
    exponent = 0
    parts = re.split(r"[eE]", text)
    if len(parts) == 2:
        text, exp = parts
        if not re.fullmatch(r"[+-]?\d+", exp):
            return None
        try:
            exponent = int(exp)
        except ValueError:
            return None
    elif len(parts) > 2:
        return None
    if number_format != "auto":
        text = _localized_number_text(text, number_format)
        if text is None:
            return None
    elif "." in text and "," in text:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
        grouping = "," if decimal == "." else "."
        integer, fraction = text.rsplit(decimal, 1)
        if not fraction.isdigit() or not re.fullmatch(rf"[+-]?\d{{1,3}}(?:\{grouping}\d{{3}})+", integer):
            return None
        text = integer.replace(grouping, "") + "." + fraction
    elif text.count(".") > 1 or text.count(",") > 1:
        separator = "." if "." in text else ","
        if not re.fullmatch(rf"[+-]?\d{{1,3}}(?:\{separator}\d{{3}})+", text):
            return None
        text = text.replace(separator, "")
    else:
        text = text.replace(",", ".")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        return None
    try:
        result = Decimal(text + "e" + str(exponent - (2 if percent else 0)))
    except (ValueError, InvalidOperation, OverflowError):
        return None
    if negative:
        result = result.copy_negate()
    return result if result.is_finite() else None


def parse_number(value: object, number_format: str = "auto") -> float | None:
    """Parse a numeric cell for display/editing; comparisons use exact decimals.

    Auto treats a single dot/comma as decimal. Select ``tr`` for ``1.234`` as
    1234, or ``us`` for ``1,234`` as 1234. Grouping is validated in both modes.
    Currency, scientific notation and percentages are supported.
    """
    parsed = _number_decimal(value, number_format)
    if parsed is None:
        return None
    try:
        result = float(parsed)
        return result if math.isfinite(result) else None
    except (ValueError, OverflowError):
        return None


_DATE = re.compile(
    r"^(?P<a>\d{1,4})(?P<sep>[-/.])(?P<b>\d{1,2})(?P=sep)(?P<c>\d{2,4})"
    r"(?P<time>[ T]\d{1,2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


def parse_date(value: object) -> pd.Timestamp | None:
    """Read native dates and explicit ISO or day-first dates, never numbers."""
    if _missing(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        try:
            result = pd.Timestamp(value)
            return result.tz_localize(None) if result.tzinfo else result
        except (TypeError, ValueError, OverflowError):
            return None
    if not isinstance(value, str):
        return None
    match = _DATE.fullmatch(value.strip())
    if not match:
        return None
    a, b, c = match.group("a", "b", "c")
    if len(a) == 4:
        year, month, day = int(a), int(b), int(c)
    else:
        day, month, year = int(a), int(b), int(c)
        if len(c) == 2:
            year += 2000 if year <= 68 else 1900
    suffix = match.group("time") or ""
    try:
        result = pd.Timestamp(f"{year:04d}-{month:02d}-{day:02d}{suffix}")
        return result.tz_localize(None) if result.tzinfo else result
    except (TypeError, ValueError, OverflowError):
        return None


_TRUE = {"true", "evet", "yes", "doğru", "dogru"}
_FALSE = {"false", "hayir", "no", "yanlış", "yanlis"}


def _boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if _missing(value):
        return None
    text = normalize_text(value).strip()
    if text in _TRUE or text == "1":
        return True
    if text in _FALSE or text == "0":
        return False
    return None


def infer_kind(series: pd.Series) -> ColumnKind:
    values = series[~series.map(_empty)]
    if values.empty:
        return ColumnKind.TEXT
    if pd.api.types.is_bool_dtype(values.dtype):
        return ColumnKind.BOOLEAN
    if pd.api.types.is_numeric_dtype(values.dtype):
        return ColumnKind.NUMBER
    if pd.api.types.is_datetime64_any_dtype(values.dtype):
        return ColumnKind.DATE
    values = values.drop_duplicates()
    # Any identifier with significant zeroes keeps the entire column textual.
    if values.map(lambda v: isinstance(v, str) and bool(re.fullmatch(r"[+-]?0\d+", v.strip()))).any():
        return ColumnKind.TEXT
    if values.map(lambda v: isinstance(v, str) and bool(re.fullmatch(r"[+-]?\d{16,}", v.strip()))).any():
        return ColumnKind.TEXT
    bool_words = values.map(lambda v: normalize_text(v).strip() in _TRUE | _FALSE)
    if bool_words.all():
        return ColumnKind.BOOLEAN
    if values.map(lambda v: parse_number(v) is not None).all():
        return ColumnKind.NUMBER
    if values.map(lambda v: parse_date(v) is not None).all():
        return ColumnKind.DATE
    return ColumnKind.TEXT


def _kind(series: pd.Series, kind: str | ColumnKind) -> ColumnKind:
    if kind == "auto":
        return infer_kind(series)
    try:
        return ColumnKind(kind)
    except ValueError as error:
        raise ValueError(tr("Geçersiz sütun türü.")) from error


def _keys(series: pd.Series, kind: ColumnKind, number_format: str = "auto") -> pd.Series:
    if kind == ColumnKind.NUMBER:
        return pd.Series(
            [_number_decimal(value, number_format) for value in series], index=series.index, dtype=object
        )
    if kind == ColumnKind.DATE:
        return pd.to_datetime(series.map(parse_date), errors="coerce")
    if kind == ColumnKind.BOOLEAN:
        return series.map(_boolean)
    return series.map(normalize_text)


def _operand(value: object, kind: ColumnKind, number_format: str = "auto") -> object:
    if kind == ColumnKind.NUMBER:
        parsed = _number_decimal(value, number_format)
        if parsed is None:
            examples = {"auto": tr("1234,56 veya 1234.56"), "tr": "1.234,56", "us": "1,234.56"}
            raise ValueError(
                tr(
                    "Seçili sayı biçimine uygun bir değer girin (örnek: {example}).",
                    example=examples[number_format],
                )
            )
        return parsed
    if kind == ColumnKind.DATE:
        parsed = parse_date(value)
        if parsed is None:
            raise ValueError(tr("Geçerli bir tarih girin (örnek: 31.12.2026 veya 2026-12-31)."))
        return parsed
    if kind == ColumnKind.BOOLEAN:
        parsed = _boolean(value)
        if parsed is None:
            raise ValueError(tr("Evet / Hayır veya True / False girin."))
        return parsed
    return normalize_text(value)


def _date_only(value: object) -> bool:
    return isinstance(value, str) and not re.search(r"[ T]\d{1,2}:\d{2}", value.strip())


def _rule_mask(series: pd.Series, rule: FilterRule, kind: ColumnKind | None = None) -> pd.Series:
    _validate_number_format(rule.number_format)
    op = rule.operator
    empty = series.map(_empty)
    if op == "is_empty":
        return empty
    if op == "not_empty":
        return ~empty
    if op in {"contains", "not_contains", "starts_with", "ends_with", "all_words", "any_words", "in"}:
        value = normalize_text(rule.value)
        if not value.strip():
            raise ValueError(tr("Filtre değeri boş bırakılamaz."))
        if op in {"contains", "not_contains", "starts_with", "ends_with"}:
            mask = series.map(lambda cell: _text_matches(cell, value, op)) & ~empty
            return ~mask if op == "not_contains" else mask
        if op == "in":
            current_kind = kind or _kind(series, rule.kind)
            # A semicolon/newline list preserves decimal commas in every
            # locale. Explicit number formats also allow one grouped value.
            preferred = ";" in value or "\n" in value
            localized_number = current_kind == ColumnKind.NUMBER and rule.number_format != "auto"
            separator = r"[\n;]" if preferred or localized_number else ","
            terms = [term.strip() for term in re.split(separator, value) if term.strip()]
            if not terms:
                raise ValueError(tr("En az bir eşleşme değeri girin."))
            # Exact selections use the selected column kind, including numbers.
            keys = _keys(series, current_kind, rule.number_format)
            return keys.isin([_operand(term, current_kind, rule.number_format) for term in terms]) & ~empty
        terms = [term for term in re.split(r"[\s,]+", value.strip()) if term]
        masks = [series.map(lambda cell: _text_matches(cell, term)) & ~empty for term in terms]
        result = masks[0]
        for mask in masks[1:]:
            result = result & mask if op == "all_words" else result | mask
        return result
    if op not in {"equals", "not_equals", "between", "gt", "gte", "lt", "lte"}:
        raise ValueError(tr("Bilinmeyen filtre işlemi: {operator}", operator=op))
    current_kind = kind or _kind(series, rule.kind)
    if op in {"between", "gt", "gte", "lt", "lte"} and current_kind not in {
        ColumnKind.NUMBER,
        ColumnKind.DATE,
    }:
        raise ValueError(tr("Aralık ve büyüklük filtreleri için Sayı veya Tarih türünü seçin."))
    if _empty(rule.value):
        raise ValueError(tr("Filtre değeri boş bırakılamaz; boş hücreler için 'Boş' filtresini kullanın."))
    keys = _keys(series, current_kind, rule.number_format)
    first = _operand(rule.value, current_kind, rule.number_format)
    if op in {"equals", "not_equals"}:
        if current_kind == ColumnKind.DATE and _date_only(rule.value):
            mask = (keys >= first.normalize()) & (keys < first.normalize() + pd.Timedelta(days=1))
        else:
            mask = keys.eq(first) & ~empty
        return ~mask if op == "not_equals" else mask
    if op == "between":
        if _empty(rule.value2):
            raise ValueError(tr("Aralığın başlangıcını ve bitişini girin."))
        last = _operand(rule.value2, current_kind, rule.number_format)
        if first > last:
            raise ValueError(tr("Aralık başlangıcı bitişten büyük olamaz."))
        if current_kind == ColumnKind.DATE and _date_only(rule.value2):
            return (keys >= first) & (keys < last.normalize() + pd.Timedelta(days=1))
        return keys.between(first, last, inclusive="both")
    if current_kind == ColumnKind.DATE and _date_only(rule.value):
        if op == "lte":
            return keys < first.normalize() + pd.Timedelta(days=1)
        if op == "gt":
            return keys >= first.normalize() + pd.Timedelta(days=1)
    return {"gt": keys.gt, "gte": keys.ge, "lt": keys.lt, "lte": keys.le}[op](first) & ~empty


def apply_filters(
    df: pd.DataFrame,
    rules: Iterable[FilterRule],
    match: str = "all",
    search: str = "",
) -> pd.DataFrame:
    """Combine explicit rules with AND/OR, then apply literal global search."""
    if match not in {"all", "any"}:
        raise ValueError(tr("Filtre birleştirme türü 'all' veya 'any' olmalıdır."))
    combined = None
    inferred: dict[tuple[str, str], ColumnKind] = {}
    for rule in rules:
        if rule.column not in df.columns:
            raise ValueError(tr("Sütun bulunamadı: {column}", column=rule.column))
        series = df[rule.column]
        if not isinstance(series, pd.Series):
            raise ValueError(tr("Aynı adlı sütunlar önce benzersiz adlarla içe aktarılmalıdır."))
        key = (rule.column, rule.kind)
        # Inference always uses the full source, never an already filtered subset.
        if key not in inferred:
            inferred[key] = _kind(series, rule.kind)
        mask = _rule_mask(series, rule, inferred[key]).fillna(False).astype(bool)
        if combined is None:
            combined = mask
        else:
            combined = combined & mask if match == "all" else combined | mask
    if combined is None:
        combined = pd.Series(True, index=df.index, dtype=bool)
    query = normalize_text(search).strip()
    if query:
        search_mask = pd.Series(False, index=df.index, dtype=bool)
        for column in df.columns:
            search_mask |= df[column].map(lambda value: _text_matches(value, query))
        combined &= search_mask
    return df.loc[combined].copy()


def sort_frame(
    df: pd.DataFrame,
    column: str,
    ascending: bool = True,
    kind: str = "auto",
    number_format: str = "auto",
) -> pd.DataFrame:
    _validate_number_format(number_format)
    if column not in df.columns:
        raise ValueError(tr("Sütun bulunamadı: {column}", column=column))
    series = df[column]
    if not isinstance(series, pd.Series):
        raise ValueError(tr("Aynı adlı sütunlar önce benzersiz adlarla içe aktarılmalıdır."))
    current_kind = _kind(series, kind)
    keys = _keys(series, current_kind, number_format)
    keys = keys.mask(series.map(_empty))
    # Stable sorting preserves ties and source indexes without changing cells.
    order = (
        keys.reset_index(drop=True).sort_values(ascending=ascending, kind="stable", na_position="last").index
    )
    return df.iloc[order].copy()
