from datetime import datetime
from decimal import Decimal

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from datadesk.core import (
    ColumnKind,
    FilterRule,
    apply_filters,
    display_value,
    infer_kind,
    parse_date,
    parse_number,
    sort_frame,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (12.5, 12.5),
        ("12.5", 12.5),
        ("12,5", 12.5),
        ("1.234", 1.234),
        ("1,234", 1.234),
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1.234.567", 1234567),
        ("1,234,567", 1234567),
        ("1 234,56", 1234.56),
        ("1\u00a0234,56", 1234.56),
        ("₺ 1.234,56", 1234.56),
        ("1.234,56 TL", 1234.56),
        ("$1,234.56", 1234.56),
        ("(1.234,56) TL", -1234.56),
        ("(₺1.234,56)", -1234.56),
        ("-12,5", -12.5),
        ("+12.5", 12.5),
        ("1e3", 1000),
        ("1,5E-2", 0.015),
        ("12,5%", 0.125),
        (".5", 0.5),
        ("0", 0),
    ],
)
def test_number_locales(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        pd.NA,
        float("nan"),
        float("inf"),
        "",
        "NA",
        "AB123",
        "31.12.2026",
        "1.2.3",
        "12 34",
        "1EUR2",
        "1,2,3",
        "(-10)",
        True,
        "1e1000",
    ],
)
def test_invalid_number_never_invents_value(raw):
    assert parse_number(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        "31.12.2026",
        "31/12/2026",
        "31-12-2026",
        "2026-12-31",
        "2026/12/31",
        "31.12.26",
        datetime(2026, 12, 31),
    ],
)
def test_explicit_dates(raw):
    assert parse_date(raw) == pd.Timestamp("2026-12-31")


@pytest.mark.parametrize(
    "raw", [1, 2026, 45200.0, "123", "2026", "31.02.2026", "2026-13-01", "ABC", "", pd.NaT]
)
def test_number_or_invalid_value_never_becomes_date(raw):
    assert parse_date(raw) is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1, 2, 3], ColumnKind.NUMBER),
        (["1.5", "2,5", ""], ColumnKind.NUMBER),
        (["00123", "00456"], ColumnKind.TEXT),
        (["0123", "bad"], ColumnKind.TEXT),
        (["9007199254740992", "9007199254740993"], ColumnKind.TEXT),
        (["2026", "2025"], ColumnKind.NUMBER),
        (["2026-12-31", "01.01.2027", None], ColumnKind.DATE),
        (["2026-12-31", "invalid"], ColumnKind.TEXT),
        (["1", "bad"], ColumnKind.TEXT),
        ([None, "", "  "], ColumnKind.TEXT),
        ([True, False], ColumnKind.BOOLEAN),
        (["Evet", "Hayır"], ColumnKind.BOOLEAN),
        (["NA", "NULL", "nan"], ColumnKind.TEXT),
    ],
)
def test_conservative_inference(values, expected):
    assert infer_kind(pd.Series(values)) == expected


def test_preserves_literal_na_and_source_values():
    data = pd.DataFrame(
        {"id": ["001", "002", "003"], "amount": ["1.234,56", "12.5", "bad"], "literal": ["NA", "nan", None]},
        index=[20, 40, 60],
    )
    original = data.copy(deep=True)
    result = apply_filters(data, [FilterRule("amount", "between", "10", "1300", "number")])
    assert result.index.tolist() == [20, 40]
    assert result.iloc[0]["amount"] == "1.234,56"
    assert result.iloc[0]["id"] == "001"
    assert_frame_equal(data, original)
    assert display_value("nan") == "nan"
    assert display_value("NA") == "NA"
    assert display_value(pd.NA) == ""


def test_date_display_does_not_hide_time_precision():
    assert display_value(pd.Timestamp("2026-12-31 12:30:45.123456789")) == "31.12.2026 12:30:45.123456789"
    assert display_value(pd.Timestamp("2026-12-31 00:00:00.000000001")) == "31.12.2026 00:00:00.000000001"
    assert display_value(pd.Timestamp("2026-12-31T12:30:00+03:00")) == "31.12.2026 12:30:00+03:00"


def test_text_search_is_literal_and_turkish_case_insensitive():
    data = pd.DataFrame({"city": ["İSTANBUL", "ısparta", "Ankara", "a.b", "axb", None]})
    assert apply_filters(data, [FilterRule("city", "contains", "istanbul")]).index.tolist() == [0]
    assert apply_filters(data, [FilterRule("city", "starts_with", "Isp")]).index.tolist() == [1]
    assert apply_filters(data, [FilterRule("city", "contains", "a.b")]).index.tolist() == [3]
    assert apply_filters(data, [FilterRule("city", "ends_with", "ARA")]).index.tolist() == [2]
    assert apply_filters(data, [FilterRule("city", "not_contains", "a.b")]).index.tolist() == [0, 1, 2, 4, 5]


def test_and_or_have_distinct_meaning():
    data = pd.DataFrame({"text": ["elma armut", "elma", "armut", "kiraz"], "number": [1, 2, 3, 4]})
    assert apply_filters(data, [FilterRule("text", "all_words", "elma armut")]).index.tolist() == [0]
    assert apply_filters(data, [FilterRule("text", "any_words", "elma armut")]).index.tolist() == [0, 1, 2]
    rules = [FilterRule("text", "contains", "elma"), FilterRule("number", "gte", "3")]
    assert apply_filters(data, rules, match="all").empty
    assert apply_filters(data, rules, match="any").index.tolist() == [0, 1, 2, 3]


def test_global_search_intersects_rules():
    data = pd.DataFrame({"city": ["İzmir", "İzmir", "Ankara"], "value": [1, 2, 3]})
    assert apply_filters(data, [FilterRule("value", "gte", "2")], search="IZMIR").index.tolist() == [1]
    assert_frame_equal(apply_filters(data, []), data)
    assert apply_filters(data, [], search="missing").empty


def test_numeric_and_identifier_equality_are_different():
    data = pd.DataFrame({"id": ["001", "1", None], "amount": ["1.234,56", "1234.56", "0"]})
    assert apply_filters(data, [FilterRule("id", "equals", "1")]).index.tolist() == [1]
    assert apply_filters(data, [FilterRule("id", "equals", "1", kind="number")]).index.tolist() == [0, 1]
    assert apply_filters(data, [FilterRule("amount", "equals", "1234,56")]).index.tolist() == [0, 1]
    assert apply_filters(data, [FilterRule("id", "not_equals", "1")]).index.tolist() == [0, 2]


def test_blank_filters_include_whitespace_but_not_literal_tokens():
    data = pd.DataFrame({"value": [None, "", "   ", pd.NA, "NA", "nan", "0", 0]})
    assert apply_filters(data, [FilterRule("value", "is_empty")]).index.tolist() == [0, 1, 2, 3]
    assert apply_filters(data, [FilterRule("value", "not_empty")]).index.tolist() == [4, 5, 6, 7]


def test_date_range_and_equality_include_end_of_day():
    data = pd.DataFrame(
        {"date": ["30.12.2026 23:59:59", "31.12.2026", "2026-12-31 23:59:59", "2027-01-01", None]}
    )
    assert apply_filters(
        data, [FilterRule("date", "between", "31.12.2026", "31.12.2026")]
    ).index.tolist() == [1, 2]
    assert apply_filters(data, [FilterRule("date", "equals", "31.12.2026")]).index.tolist() == [1, 2]
    assert apply_filters(data, [FilterRule("date", "lte", "31.12.2026")]).index.tolist() == [0, 1, 2]
    assert apply_filters(data, [FilterRule("date", "gt", "31.12.2026")]).index.tolist() == [3]


@pytest.mark.parametrize(
    ("operator", "expected"),
    [("gt", [2]), ("gte", [1, 2]), ("lt", [0]), ("lte", [0, 1]), ("between", [1, 2])],
)
def test_numeric_boundaries(operator, expected):
    data = pd.DataFrame({"value": [1.5, 2.5, 3.5, None]})
    rule = FilterRule("value", operator, "2.5", "3.5")
    assert apply_filters(data, [rule]).index.tolist() == expected


def test_in_values_are_exact_and_typed():
    data = pd.DataFrame({"city": ["Ankara", "İzmir", "İzmir merkez"], "value": [1, 2, 3]})
    assert apply_filters(data, [FilterRule("city", "in", "ankara\nizmir")]).index.tolist() == [0, 1]
    assert apply_filters(data, [FilterRule("value", "in", "1,3")]).index.tolist() == [0, 2]


def test_boolean_equality():
    data = pd.DataFrame({"value": [True, False, None]})
    assert apply_filters(data, [FilterRule("value", "equals", "evet", kind="boolean")]).index.tolist() == [0]


@pytest.mark.parametrize(
    "rule",
    [
        FilterRule("missing", "equals", "a"),
        FilterRule("value", "between", "3", "1"),
        FilterRule("value", "between", "1", "bad"),
        FilterRule("value", "between", "1", ""),
        FilterRule("value", "contains", ""),
        FilterRule("value", "nonsense", "1"),
        FilterRule("value", "gte", "abc"),
        FilterRule("value", "equals", ""),
        FilterRule("value", "equals", "1", kind="nonsense"),
    ],
)
def test_invalid_filter_is_actionable_error(rule):
    with pytest.raises(ValueError):
        apply_filters(pd.DataFrame({"value": [1, 2, 3]}), [rule])


def test_text_range_requires_explicit_valid_type():
    with pytest.raises(ValueError, match="Sayı veya Tarih"):
        apply_filters(pd.DataFrame({"value": ["bad", "12"]}), [FilterRule("value", "between", "1", "20")])


def test_typed_sort_is_stable_raw_and_empty_last():
    data = pd.DataFrame(
        {"value": ["12.5", "2,5", "2.50", None, "1.234,56"], "id": ["001", "002", "003", "004", "005"]},
        index=[10, 20, 30, 40, 50],
    )
    original = data.copy(deep=True)
    result = sort_frame(data, "value")
    assert result.index.tolist() == [20, 30, 10, 50, 40]
    assert_frame_equal(result, original.loc[[20, 30, 10, 50, 40]])
    assert sort_frame(data, "value", ascending=False).index.tolist() == [50, 10, 20, 30, 40]
    assert_frame_equal(data, original)


def test_date_sort_and_duplicate_indexes_do_not_duplicate_rows():
    data = pd.DataFrame({"date": ["31.12.2026", "01.01.2026", "01.02.2026"]}, index=[0, 0, 1])
    result = sort_frame(data, "date")
    assert result["date"].tolist() == ["01.01.2026", "01.02.2026", "31.12.2026"]
    assert len(result) == len(data)


def test_zero_results_keep_headers_and_dtypes():
    data = pd.DataFrame({"value": [1, 2], "id": ["001", "002"]})
    result = apply_filters(data, [FilterRule("value", "gt", "10")])
    assert result.empty
    assert result.columns.tolist() == ["value", "id"]
    assert result.dtypes.equals(data.dtypes)


def test_large_numeric_filter_and_sort():
    data = pd.DataFrame({"value": range(100_000), "id": [f"{i:06d}" for i in range(100_000)]})
    result = apply_filters(data, [FilterRule("value", "between", "99990", "99999")])
    assert len(result) == 10
    assert sort_frame(result, "value", ascending=False)["id"].iloc[0] == "099999"


def test_large_integer_and_decimal_comparison_does_not_round():
    data = pd.DataFrame({"id": ["9007199254740992", "9007199254740993", None]})
    rule = FilterRule("id", "equals", "9007199254740993", kind="number")
    assert apply_filters(data, [rule]).index.tolist() == [1]
    native = pd.DataFrame({"id": pd.Series([9007199254740992, 9007199254740993, None], dtype=object)})
    assert apply_filters(native, [rule]).index.tolist() == [1]
    decimal = pd.DataFrame({"v": ["0.100000000000000001", "0.100000000000000002"]})
    assert apply_filters(decimal, [FilterRule("v", "equals", "0.100000000000000002")]).index.tolist() == [1]


@pytest.mark.parametrize(
    ("raw", "number_format", "expected"),
    [
        ("1.234", "tr", 1234),
        ("1,234", "us", 1234),
        ("1.234,56", "tr", 1234.56),
        ("1,234.56", "us", 1234.56),
        ("1,234", "tr", 1.234),
        ("1.234", "us", 1.234),
        ("1.234.567", "tr", 1234567),
        ("1,234,567", "us", 1234567),
        ("₺ (1.234,56)", "tr", -1234.56),
        ("($1,234.56)", "us", -1234.56),
        ("1 234,56", "tr", 1234.56),
        ("1 234.56", "us", 1234.56),
        ("1,5e3", "tr", 1500),
        ("1.5e3", "us", 1500),
        ("12,5%", "tr", 0.125),
        ("12.5%", "us", 0.125),
        (",5", "tr", 0.5),
        (".5", "us", 0.5),
        (12.5, "tr", 12.5),
        (12.5, "us", 12.5),
        (1234, "tr", 1234),
        (1234, "us", 1234),
        (Decimal("12.5"), "tr", 12.5),
        (Decimal("12.5"), "us", 12.5),
    ],
)
def test_explicit_number_locale_disambiguates_grouping(raw, number_format, expected):
    assert parse_number(raw, number_format) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("raw", "number_format"),
    [
        ("1.23", "tr"),
        ("1,23", "us"),
        ("12.34.567", "tr"),
        ("12,34,567", "us"),
        ("1234.567", "tr"),
        ("1234,567", "us"),
        ("1,234.56", "tr"),
        ("1.234,56", "us"),
        ("1,2,3", "tr"),
        ("1.2.3", "us"),
        ("1 234.56", "tr"),
        ("1 234,56", "us"),
    ],
)
def test_explicit_number_locale_rejects_bad_grouping(raw, number_format):
    assert parse_number(raw, number_format) is None


@pytest.mark.parametrize(
    ("number_format", "values", "operand", "expected"),
    [
        ("tr", ["1.234", "12", "2.345", "1.23", None], "1.000", [0, 2]),
        ("us", ["1,234", "12", "2,345", "1,23", None], "1,000", [0, 2]),
        ("auto", ["1.234", "12", "2.345", "1.23", None], "2", [1, 2]),
    ],
)
def test_locale_filter_keys_and_operands_use_same_convention(number_format, values, operand, expected):
    data = pd.DataFrame({"amount": values, "id": ["001", "002", "003", "004", "005"]})
    original = data.copy(deep=True)
    result = apply_filters(
        data, [FilterRule("amount", "gte", operand, kind="number", number_format=number_format)]
    )
    assert result.index.tolist() == expected
    assert_frame_equal(data, original)


def test_locale_between_equality_and_sort_preserve_raw_cells():
    data = pd.DataFrame({"amount": ["1.234", "12,50", "2.345", "123,45", "bad", None]})
    original = data.copy(deep=True)
    between = FilterRule("amount", "between", "100,00", "2.000", "number", "tr")
    assert apply_filters(data, [between]).index.tolist() == [0, 3]
    equal = FilterRule("amount", "equals", "1.234,00", kind="number", number_format="tr")
    assert apply_filters(data, [equal]).index.tolist() == [0]
    result = sort_frame(data, "amount", kind="number", number_format="tr")
    assert result.index.tolist() == [1, 3, 0, 2, 4, 5]
    assert_frame_equal(result, original.loc[[1, 3, 0, 2, 4, 5]])
    assert_frame_equal(data, original)


@pytest.mark.parametrize(
    ("number_format", "value", "expected"),
    [
        ("tr", "1,5; 2,5", [0, 1]),
        ("tr", "1,5\n2,5", [0, 1]),
        ("tr", "1,5", [0]),
        ("auto", "1,5; 2,5", [0, 1]),
        ("us", "1.5;2.5", [0, 1]),
    ],
)
def test_number_lists_preserve_decimal_commas(number_format, value, expected):
    data = pd.DataFrame({"amount": [1.5, 2.5, 3.5]})
    rule = FilterRule("amount", "in", value, kind="number", number_format=number_format)
    assert apply_filters(data, [rule]).index.tolist() == expected


def test_us_grouped_single_value_list():
    data = pd.DataFrame({"amount": [1234, 1, 234]})
    rule = FilterRule("amount", "in", "1,234", kind="number", number_format="us")
    assert apply_filters(data, [rule]).index.tolist() == [0]


def test_locale_validation_and_invalid_operands_are_errors():
    data = pd.DataFrame({"amount": ["1.234", "2.345"]})
    with pytest.raises(ValueError, match="sayı biçimi"):
        parse_number("1", "invalid")
    with pytest.raises(ValueError, match="sayı biçimi"):
        sort_frame(data, "amount", number_format="invalid")
    with pytest.raises(ValueError, match="sayı biçimi"):
        apply_filters(data, [FilterRule("amount", "contains", "1", number_format="invalid")])
    with pytest.raises(ValueError, match="sayı biçimine"):
        apply_filters(data, [FilterRule("amount", "gte", "1.23", kind="number", number_format="tr")])
