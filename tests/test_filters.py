"""Tests for utils/filters.py — filter DSL, order-by, date ranges, aggregations."""

import json

import pytest
import typer

from ga_cli.utils.filters import (
    _parse_single_filter,
    parse_date_ranges,
    parse_dim_filters,
    parse_filter_json,
    parse_metric_filters,
    parse_minute_ranges,
    parse_order_bys,
    validate_metric_aggregations,
)

# ---------------------------------------------------------------------------
# _parse_single_filter
# ---------------------------------------------------------------------------

class TestParseSingleFilter:
    def test_exact_match(self):
        result = _parse_single_filter("country==US")
        assert result == {
            "filter": {
                "fieldName": "country",
                "stringFilter": {"matchType": "EXACT", "value": "US"},
            }
        }

    def test_exact_match_with_spaces(self):
        result = _parse_single_filter("  country == US  ")
        assert result["filter"]["fieldName"] == "country"
        assert result["filter"]["stringFilter"]["value"] == "US"

    def test_not_equal(self):
        result = _parse_single_filter("country!=US")
        assert "notExpression" in result
        inner = result["notExpression"]
        assert inner["filter"]["fieldName"] == "country"
        assert inner["filter"]["stringFilter"]["matchType"] == "EXACT"
        assert inner["filter"]["stringFilter"]["value"] == "US"

    def test_contains(self):
        result = _parse_single_filter("pagePath contains /blog")
        assert result["filter"]["fieldName"] == "pagePath"
        assert result["filter"]["stringFilter"]["matchType"] == "CONTAINS"
        assert result["filter"]["stringFilter"]["value"] == "/blog"

    def test_begins_with(self):
        result = _parse_single_filter("pagePath begins_with /products")
        assert result["filter"]["stringFilter"]["matchType"] == "BEGINS_WITH"
        assert result["filter"]["stringFilter"]["value"] == "/products"

    def test_ends_with(self):
        result = _parse_single_filter("pagePath ends_with .html")
        assert result["filter"]["stringFilter"]["matchType"] == "ENDS_WITH"
        assert result["filter"]["stringFilter"]["value"] == ".html"

    def test_regex(self):
        result = _parse_single_filter("pagePath=~^/blog/.*")
        assert result["filter"]["stringFilter"]["matchType"] == "FULL_REGEXP"
        assert result["filter"]["stringFilter"]["value"] == "^/blog/.*"

    def test_in_list(self):
        result = _parse_single_filter("country in US,UK,CA")
        assert result["filter"]["fieldName"] == "country"
        assert result["filter"]["inListFilter"]["values"] == ["US", "UK", "CA"]

    def test_in_list_with_spaces(self):
        result = _parse_single_filter("country in US, UK, CA")
        assert result["filter"]["inListFilter"]["values"] == ["US", "UK", "CA"]

    def test_greater_than(self):
        result = _parse_single_filter("sessions>100")
        assert result["filter"]["numericFilter"]["operation"] == "GREATER_THAN"
        assert result["filter"]["numericFilter"]["value"] == {"int64Value": "100"}

    def test_greater_equal(self):
        result = _parse_single_filter("sessions>=100")
        assert result["filter"]["numericFilter"]["operation"] == "GREATER_THAN_OR_EQUAL"

    def test_less_than(self):
        result = _parse_single_filter("sessions<50")
        assert result["filter"]["numericFilter"]["operation"] == "LESS_THAN"
        assert result["filter"]["numericFilter"]["value"] == {"int64Value": "50"}

    def test_less_equal(self):
        result = _parse_single_filter("sessions<=50")
        assert result["filter"]["numericFilter"]["operation"] == "LESS_THAN_OR_EQUAL"

    def test_numeric_float(self):
        result = _parse_single_filter("revenue>10.5")
        assert result["filter"]["numericFilter"]["value"] == {"doubleValue": 10.5}

    def test_between(self):
        result = _parse_single_filter("sessions between 100,500")
        f = result["filter"]["betweenFilter"]
        assert f["fromValue"] == {"int64Value": "100"}
        assert f["toValue"] == {"int64Value": "500"}

    def test_between_floats(self):
        result = _parse_single_filter("revenue between 10.5,100.0")
        f = result["filter"]["betweenFilter"]
        assert f["fromValue"] == {"doubleValue": 10.5}
        assert f["toValue"] == {"doubleValue": 100.0}

    def test_between_missing_second_value(self):
        with pytest.raises(typer.BadParameter, match="two comma-separated"):
            _parse_single_filter("sessions between 100")

    def test_invalid_expression(self):
        with pytest.raises(typer.BadParameter, match="Cannot parse"):
            _parse_single_filter("nosuchop")

    def test_invalid_numeric(self):
        with pytest.raises(typer.BadParameter, match="Invalid numeric"):
            _parse_single_filter("sessions>abc")

    def test_keyword_case_insensitive(self):
        result = _parse_single_filter("pagePath CONTAINS /blog")
        assert result["filter"]["stringFilter"]["matchType"] == "CONTAINS"


# ---------------------------------------------------------------------------
# parse_dim_filters / parse_metric_filters
# ---------------------------------------------------------------------------

class TestParseDimFilters:
    def test_single_filter(self):
        result = parse_dim_filters(["country==US"])
        assert "filter" in result

    def test_multiple_filters_anded(self):
        result = parse_dim_filters(["country==US", "pagePath contains /blog"])
        assert "andGroup" in result
        assert len(result["andGroup"]["expressions"]) == 2

    def test_metric_filters_same_behavior(self):
        result = parse_metric_filters(["sessions>100", "users>50"])
        assert "andGroup" in result
        assert len(result["andGroup"]["expressions"]) == 2


# ---------------------------------------------------------------------------
# parse_filter_json
# ---------------------------------------------------------------------------

class TestParseFilterJson:
    def test_inline_json(self):
        data = {
            "filter": {
                "fieldName": "country",
                "stringFilter": {"matchType": "EXACT", "value": "US"},
            }
        }
        raw = json.dumps(data)
        result = parse_filter_json(raw)
        assert result["filter"]["fieldName"] == "country"

    def test_file_reference(self, tmp_path):
        data = {
            "filter": {
                "fieldName": "country",
                "stringFilter": {"matchType": "EXACT", "value": "US"},
            }
        }
        f = tmp_path / "filter.json"
        f.write_text(json.dumps(data))
        result = parse_filter_json(f"@{f}")
        assert result["filter"]["fieldName"] == "country"

    def test_file_not_found(self):
        with pytest.raises(typer.BadParameter, match="Filter file not found"):
            parse_filter_json("@/nonexistent/filter.json")

    def test_invalid_json(self):
        with pytest.raises(typer.BadParameter, match="Invalid filter JSON"):
            parse_filter_json("{bad json")


# ---------------------------------------------------------------------------
# parse_order_bys
# ---------------------------------------------------------------------------

class TestParseOrderBys:
    def test_metric_desc_default(self):
        result = parse_order_bys(["sessions"])
        assert result == [{"metric": {"metricName": "sessions"}, "desc": True}]

    def test_metric_explicit_desc(self):
        result = parse_order_bys(["sessions:desc"])
        assert result[0]["desc"] is True

    def test_metric_asc(self):
        result = parse_order_bys(["sessions:asc"])
        assert result[0]["desc"] is False

    def test_dimension_with_order_type(self):
        result = parse_order_bys(["country:asc:alpha"])
        assert result == [{
            "dimension": {"dimensionName": "country", "orderType": "ALPHANUMERIC"},
            "desc": False,
        }]

    def test_dimension_numeric_order(self):
        result = parse_order_bys(["date:asc:numeric"])
        assert result[0]["dimension"]["orderType"] == "NUMERIC"

    def test_dimension_ialpha(self):
        result = parse_order_bys(["country:asc:ialpha"])
        assert result[0]["dimension"]["orderType"] == "CASE_INSENSITIVE_ALPHANUMERIC"

    def test_dimension_detected_from_list(self):
        result = parse_order_bys(["country:desc"], dimensions=["country"])
        assert "dimension" in result[0]

    def test_metric_detected_from_list(self):
        result = parse_order_bys(["sessions:desc"], metrics=["sessions"])
        assert "metric" in result[0]

    def test_multiple_order_bys(self):
        result = parse_order_bys(["sessions:desc", "country:asc:alpha"])
        assert len(result) == 2
        assert "metric" in result[0]
        assert "dimension" in result[1]

    def test_invalid_direction(self):
        with pytest.raises(typer.BadParameter, match="Invalid sort direction"):
            parse_order_bys(["sessions:sideways"])

    def test_invalid_order_type(self):
        with pytest.raises(typer.BadParameter, match="Invalid order type"):
            parse_order_bys(["country:asc:badtype"])


# ---------------------------------------------------------------------------
# parse_date_ranges
# ---------------------------------------------------------------------------

class TestParseDateRanges:
    def test_single_range(self):
        result = parse_date_ranges(["7daysAgo,today"])
        assert result == [{"startDate": "7daysAgo", "endDate": "today"}]

    def test_multiple_ranges(self):
        result = parse_date_ranges(["7daysAgo,today", "30daysAgo,8daysAgo"])
        assert len(result) == 2

    def test_named_range(self):
        result = parse_date_ranges(["7daysAgo,today,thisWeek"])
        assert result[0]["name"] == "thisWeek"

    def test_invalid_format(self):
        with pytest.raises(typer.BadParameter, match="must be 'start,end'"):
            parse_date_ranges(["just_a_date"])


# ---------------------------------------------------------------------------
# parse_minute_ranges
# ---------------------------------------------------------------------------

class TestParseMinuteRanges:
    def test_single_range(self):
        result = parse_minute_ranges(["0,4"])
        assert result == [{"startMinutesAgo": 0, "endMinutesAgo": 4}]

    def test_multiple_ranges(self):
        result = parse_minute_ranges(["0,4", "5,10"])
        assert len(result) == 2

    def test_invalid_non_integer(self):
        with pytest.raises(typer.BadParameter, match="must be integers"):
            parse_minute_ranges(["zero,four"])

    def test_invalid_format(self):
        with pytest.raises(typer.BadParameter, match="must be 'start,end'"):
            parse_minute_ranges(["5"])


# ---------------------------------------------------------------------------
# validate_metric_aggregations
# ---------------------------------------------------------------------------

class TestValidateMetricAggregations:
    def test_valid_values(self):
        result = validate_metric_aggregations(["TOTAL", "MINIMUM", "MAXIMUM"])
        assert result == ["TOTAL", "MINIMUM", "MAXIMUM"]

    def test_case_insensitive(self):
        result = validate_metric_aggregations(["total", "minimum"])
        assert result == ["TOTAL", "MINIMUM"]

    def test_invalid_value(self):
        with pytest.raises(typer.BadParameter, match="Invalid aggregation"):
            validate_metric_aggregations(["AVERAGE"])
