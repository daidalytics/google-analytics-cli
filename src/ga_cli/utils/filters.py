"""Parsing utilities for GA4 report filters, order-bys, date ranges, and aggregations."""

import json
import re
from pathlib import Path

import typer

# Ordered operator patterns: try longest/most specific first
_OPERATORS = [
    (re.compile(r"^(.+?)\s*==\s*(.+)$"), "EXACT"),
    (re.compile(r"^(.+?)\s*!=\s*(.+)$"), "NOT_EXACT"),
    (re.compile(r"^(.+?)\s*=~\s*(.+)$"), "FULL_REGEXP"),
    (re.compile(r"^(.+?)\s*>=\s*(.+)$"), "GREATER_THAN_OR_EQUAL"),
    (re.compile(r"^(.+?)\s*<=\s*(.+)$"), "LESS_THAN_OR_EQUAL"),
    (re.compile(r"^(.+?)\s*>\s*(.+)$"), "GREATER_THAN"),
    (re.compile(r"^(.+?)\s*<\s*(.+)$"), "LESS_THAN"),
    (re.compile(r"^(.+?)\s+contains\s+(.+)$", re.IGNORECASE), "CONTAINS"),
    (re.compile(r"^(.+?)\s+begins_with\s+(.+)$", re.IGNORECASE), "BEGINS_WITH"),
    (re.compile(r"^(.+?)\s+ends_with\s+(.+)$", re.IGNORECASE), "ENDS_WITH"),
    (re.compile(r"^(.+?)\s+in\s+(.+)$", re.IGNORECASE), "IN_LIST"),
    (re.compile(r"^(.+?)\s+between\s+(.+)$", re.IGNORECASE), "BETWEEN"),
]

_STRING_OPS = {"EXACT", "NOT_EXACT", "FULL_REGEXP", "CONTAINS", "BEGINS_WITH", "ENDS_WITH"}
_NUMERIC_OPS = {"GREATER_THAN", "GREATER_THAN_OR_EQUAL", "LESS_THAN", "LESS_THAN_OR_EQUAL"}
_VALID_AGGREGATIONS = {"TOTAL", "MINIMUM", "MAXIMUM"}
_ORDER_TYPE_MAP = {
    "alpha": "ALPHANUMERIC",
    "ialpha": "CASE_INSENSITIVE_ALPHANUMERIC",
    "numeric": "NUMERIC",
}


def _parse_numeric(s: str) -> dict:
    """Parse a string into a NumericValue dict."""
    s = s.strip()
    try:
        return {"int64Value": str(int(s))}
    except ValueError:
        pass
    try:
        return {"doubleValue": float(s)}
    except ValueError:
        raise typer.BadParameter(f"Invalid numeric value: '{s}'")


def _parse_single_filter(expr: str) -> dict:
    """Parse a single DSL filter expression into a FilterExpression dict."""
    expr = expr.strip()
    for pattern, op in _OPERATORS:
        m = pattern.match(expr)
        if not m:
            continue

        field = m.group(1).strip()
        value = m.group(2).strip()

        if op in _STRING_OPS:
            match_type = op if op != "NOT_EXACT" else "EXACT"
            filter_expr = {
                "filter": {
                    "fieldName": field,
                    "stringFilter": {"matchType": match_type, "value": value},
                }
            }
            if op == "NOT_EXACT":
                return {"notExpression": filter_expr}
            return filter_expr

        if op in _NUMERIC_OPS:
            return {
                "filter": {
                    "fieldName": field,
                    "numericFilter": {
                        "operation": op,
                        "value": _parse_numeric(value),
                    },
                }
            }

        if op == "IN_LIST":
            values = [v.strip() for v in value.split(",")]
            return {
                "filter": {
                    "fieldName": field,
                    "inListFilter": {"values": values},
                }
            }

        if op == "BETWEEN":
            parts = [p.strip() for p in value.split(",")]
            if len(parts) != 2:
                raise typer.BadParameter(
                    f"'between' requires two comma-separated values, got: '{value}'"
                )
            return {
                "filter": {
                    "fieldName": field,
                    "betweenFilter": {
                        "fromValue": _parse_numeric(parts[0]),
                        "toValue": _parse_numeric(parts[1]),
                    },
                }
            }

    supported = (
        "==, !=, =~, >, >=, <, <=, contains, begins_with, ends_with, in, between"
    )
    raise typer.BadParameter(
        f"Cannot parse filter expression: '{expr}'. "
        f"Supported operators: {supported}"
    )


def _wrap_and(expressions: list[dict]) -> dict:
    """Wrap multiple FilterExpressions in an andGroup, or return single."""
    if len(expressions) == 1:
        return expressions[0]
    return {"andGroup": {"expressions": expressions}}


def parse_dim_filters(expressions: list[str]) -> dict:
    """Parse DSL strings into a dimensionFilter FilterExpression dict."""
    return _wrap_and([_parse_single_filter(e) for e in expressions])


def parse_metric_filters(expressions: list[str]) -> dict:
    """Parse DSL strings into a metricFilter FilterExpression dict."""
    return _wrap_and([_parse_single_filter(e) for e in expressions])


def parse_filter_json(raw: str) -> dict:
    """Parse a JSON string or @file reference into a FilterExpression dict."""
    if raw.startswith("@"):
        path = Path(raw[1:])
        if not path.exists():
            raise typer.BadParameter(f"Filter file not found: {path}")
        raw = path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid filter JSON: {e}")


def parse_order_bys(
    expressions: list[str],
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
) -> list[dict]:
    """Parse order-by DSL strings into OrderBy dicts.

    Format: ``fieldName:direction:orderType``

    - direction: ``asc`` or ``desc`` (default ``desc``)
    - orderType (dimensions only): ``alpha``, ``ialpha``, ``numeric``
    """
    metrics = metrics or []
    dimensions = dimensions or []
    result = []

    for expr in expressions:
        parts = [p.strip() for p in expr.split(":")]
        field = parts[0]
        direction = "desc"
        order_type = None

        if len(parts) >= 2:
            d = parts[1].lower()
            if d not in ("asc", "desc"):
                raise typer.BadParameter(
                    f"Invalid sort direction '{parts[1]}'. Must be 'asc' or 'desc'."
                )
            direction = d

        if len(parts) >= 3:
            ot = parts[2].lower()
            if ot not in _ORDER_TYPE_MAP:
                raise typer.BadParameter(
                    f"Invalid order type '{parts[2]}'. "
                    f"Must be one of: alpha, ialpha, numeric."
                )
            order_type = _ORDER_TYPE_MAP[ot]

        desc = direction == "desc"

        # Determine metric vs dimension order-by
        if order_type is not None or field in dimensions:
            order_by: dict = {
                "dimension": {"dimensionName": field},
                "desc": desc,
            }
            if order_type:
                order_by["dimension"]["orderType"] = order_type
        else:
            order_by = {
                "metric": {"metricName": field},
                "desc": desc,
            }

        result.append(order_by)

    return result


def parse_date_ranges(ranges: list[str]) -> list[dict]:
    """Parse ``start,end`` (or ``start,end,name``) strings into dateRanges dicts."""
    result = []
    for r in ranges:
        parts = [p.strip() for p in r.split(",")]
        if len(parts) < 2:
            raise typer.BadParameter(
                f"Date range must be 'start,end' (got '{r}')"
            )
        entry: dict = {"startDate": parts[0], "endDate": parts[1]}
        if len(parts) >= 3:
            entry["name"] = parts[2]
        result.append(entry)
    return result


def parse_minute_ranges(ranges: list[str]) -> list[dict]:
    """Parse ``start,end`` strings into minuteRanges dicts for realtime reports."""
    result = []
    for r in ranges:
        parts = [p.strip() for p in r.split(",")]
        if len(parts) != 2:
            raise typer.BadParameter(
                f"Minute range must be 'start,end' (got '{r}')"
            )
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError:
            raise typer.BadParameter(
                f"Minute range values must be integers (got '{r}')"
            )
        result.append({"startMinutesAgo": start, "endMinutesAgo": end})
    return result


def validate_metric_aggregations(values: list[str]) -> list[str]:
    """Validate and normalize metric aggregation enum values."""
    result = []
    for v in values:
        upper = v.strip().upper()
        if upper not in _VALID_AGGREGATIONS:
            raise typer.BadParameter(
                f"Invalid aggregation: '{v}'. Must be TOTAL, MINIMUM, or MAXIMUM."
            )
        result.append(upper)
    return result
