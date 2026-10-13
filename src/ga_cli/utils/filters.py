"""Parsing utilities for GA4 report filters, order-bys, date ranges, and aggregations."""

import json
import math
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
        value = float(s)
    except ValueError:
        raise typer.BadParameter(f"Invalid numeric value: '{s}'")
    # float() also accepts nan/inf, which JSON can't carry to the API
    if not math.isfinite(value):
        raise typer.BadParameter(f"Invalid numeric value: '{s}'")
    return {"doubleValue": value}


def _parse_single_filter(expr: str, metric: bool = False) -> dict:
    """Parse a single DSL filter expression into a FilterExpression dict.

    With ``metric=True``, ``==``/``!=`` build a numeric EQUAL filter (the API
    rejects stringFilter in a metricFilter) and string-only operators are refused.
    """
    expr = expr.strip()
    for pattern, op in _OPERATORS:
        m = pattern.match(expr)
        if not m:
            continue

        field = m.group(1).strip()
        value = m.group(2).strip()

        if metric:
            if op in ("EXACT", "NOT_EXACT"):
                filter_expr = {
                    "filter": {
                        "fieldName": field,
                        "numericFilter": {
                            "operation": "EQUAL",
                            "value": _parse_numeric(value),
                        },
                    }
                }
                if op == "NOT_EXACT":
                    return {"notExpression": filter_expr}
                return filter_expr
            if op not in _NUMERIC_OPS and op != "BETWEEN":
                raise typer.BadParameter(
                    f"Operator in '{expr}' is not supported for metric filters. "
                    f"Supported: ==, !=, >, >=, <, <=, between"
                )

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
    return _wrap_and([_parse_single_filter(e, metric=True) for e in expressions])


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


def _first_direction(parts: list[str], start: int) -> int:
    """Index of the first ``asc``/``desc`` in ``parts[start:]``, else ``len(parts)``."""
    return next(
        (i for i in range(start, len(parts)) if parts[i].lower() in ("asc", "desc")),
        len(parts),
    )


def parse_order_bys(
    expressions: list[str],
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
) -> list[dict]:
    """Parse order-by DSL strings into OrderBy dicts.

    Format: ``fieldName:direction:orderType``

    - direction: ``asc`` or ``desc`` (default ``desc``)
    - orderType (dimensions only): ``alpha``, ``ialpha``, ``numeric``

    Field names may themselves contain ``:`` (``keyEvents:sign_up``,
    ``customEvent:plan``); they are resolved against the requested
    metrics/dimensions, which the API requires order-by fields to be in.
    """
    metrics = metrics or []
    dimensions = dimensions or []
    known_fields = set(metrics) | set(dimensions)
    result = []

    for expr in expressions:
        parts = [p.strip() for p in expr.split(":")]
        # Longest colon-joined prefix that names a requested field. Failing
        # that, everything before the first asc/desc, so the error below names
        # the whole field; with no fields to check against, the first part.
        split = next(
            (i for i in range(len(parts), 0, -1) if ":".join(parts[:i]) in known_fields),
            None,
        )
        if split is None and known_fields:
            split = _first_direction(parts, 1)
        elif split is None:
            split = 1
        field = ":".join(parts[:split])
        rest = parts[split:]
        if known_fields and field not in known_fields:
            raise typer.BadParameter(
                f"--order-by field '{field}' is not one of the requested metrics/dimensions "
                f"({', '.join([*metrics, *dimensions])}). Add it to -m or -d."
            )
        direction = "desc"
        order_type = None

        if len(rest) >= 1:
            d = rest[0].lower()
            if d not in ("asc", "desc"):
                message = f"Invalid sort direction '{rest[0]}'. Must be 'asc' or 'desc'."
                if known_fields:
                    # Possibly the rest of a field name that wasn't requested
                    # (keyEvents:purchase with only -m keyEvents)
                    end = _first_direction(parts, split)
                    message += f" If '{':'.join(parts[:end])}' is a field name, add it to -m or -d."
                raise typer.BadParameter(message)
            direction = d

        if len(rest) >= 2:
            ot = rest[1].lower()
            if ot not in _ORDER_TYPE_MAP:
                raise typer.BadParameter(
                    f"Invalid order type '{rest[1]}'. "
                    f"Must be one of: alpha, ialpha, numeric."
                )
            order_type = _ORDER_TYPE_MAP[ot]
            if field in metrics:
                raise typer.BadParameter(
                    f"Order type '{rest[1]}' applies only to dimensions; "
                    f"'{field}' is a metric."
                )

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
    """Parse ``start,end`` strings into minuteRanges dicts for realtime reports.

    Both are minutes ago, so ``29,0`` is the last 30 minutes; the API rejects
    a start later (fewer minutes ago) than the end.
    """
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
        if start < end:
            raise typer.BadParameter(
                f"Minute range is START,END in minutes ago, so START must be >= END "
                f"(got '{r}'; did you mean '{end},{start}'?)"
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
