"""Report commands: run, realtime, build.

Uses the Analytics Data API v1beta.
"""

import json
import time
from pathlib import Path
from typing import Optional

import questionary
import typer

from ..api.client import get_data_alpha_client, get_data_client
from ..config.store import get_effective_value
from ..utils import console, handle_error, info, output, require_options, resolve_output_format
from ..utils.filters import (
    parse_date_ranges,
    parse_dim_filters,
    parse_filter_json,
    parse_metric_filters,
    parse_minute_ranges,
    parse_order_bys,
    validate_metric_aggregations,
)

reports_app = typer.Typer(
    name="reports", help="Run GA4 reports", no_args_is_help=True
)

# Fallback metrics/dimensions when metadata API is unavailable
_FALLBACK_METRICS = [
    "sessions",
    "totalUsers",
    "newUsers",
    "screenPageViews",
    "eventCount",
    "engagementRate",
    "averageSessionDuration",
    "conversions",
    "totalRevenue",
]

_FALLBACK_DIMENSIONS = [
    "date",
    "country",
    "city",
    "deviceCategory",
    "operatingSystem",
    "browser",
    "sourceMedium",
    "sessionDefaultChannelGroup",
    "pagePath",
    "pageTitle",
]


def _transform_report_rows(result: dict) -> tuple[list[dict], list[str], list[str]]:
    """Transform a GA Data API report response into a list of dicts.

    Returns (rows, column_keys, column_headers).
    """
    dim_headers = [h.get("name", "") for h in result.get("dimensionHeaders", [])]
    met_headers = [h.get("name", "") for h in result.get("metricHeaders", [])]

    all_keys = dim_headers + met_headers
    rows = []
    for row in result.get("rows", []):
        entry = {}
        for i, name in enumerate(dim_headers):
            entry[name] = row["dimensionValues"][i]["value"]
        for i, name in enumerate(met_headers):
            entry[name] = row["metricValues"][i]["value"]
        rows.append(entry)

    return rows, all_keys, all_keys


def _fetch_metadata(data_client, effective_property: str) -> tuple[list[str], list[str]]:
    """Fetch available metrics and dimensions from the API metadata endpoint.

    Returns (metrics, dimensions). Falls back to hardcoded lists on error.
    """
    try:
        metadata = (
            data_client.properties()
            .getMetadata(name=f"properties/{effective_property}/metadata")
            .execute()
        )
        metrics = [m["apiName"] for m in metadata.get("metrics", [])]
        dimensions = [d["apiName"] for d in metadata.get("dimensions", [])]
        return metrics, dimensions
    except Exception:
        return _FALLBACK_METRICS, _FALLBACK_DIMENSIONS


def _resolve_filters(
    dim_filter: list[str] | None,
    metric_filter: list[str] | None,
    filter_json: str | None,
) -> tuple[dict | None, dict | None]:
    """Resolve dimension and metric filters from DSL flags and/or JSON.

    Returns (dimensionFilter, metricFilter) dicts or None.
    """
    dim_result = None
    met_result = None

    if filter_json:
        if dim_filter or metric_filter:
            raise typer.BadParameter(
                "Cannot combine --dim-filter/--metric-filter with --filter-json. "
                "Use one approach or the other."
            )
        parsed = parse_filter_json(filter_json)
        # filter-json can be a single FilterExpression (applied as dimensionFilter)
        # or an object with "dimensionFilter" and/or "metricFilter" keys
        if "dimensionFilter" in parsed or "metricFilter" in parsed:
            dim_result = parsed.get("dimensionFilter")
            met_result = parsed.get("metricFilter")
        else:
            dim_result = parsed
    else:
        if dim_filter:
            dim_result = parse_dim_filters(dim_filter)
        if metric_filter:
            met_result = parse_metric_filters(metric_filter)

    return dim_result, met_result


def _build_report_body(
    *,
    metrics: str,
    dimensions: str | None,
    start_date: str,
    end_date: str,
    limit: int,
    dim_filter: list[str] | None = None,
    metric_filter: list[str] | None = None,
    filter_json: str | None = None,
    order_by: list[str] | None = None,
    offset: int | None = None,
    date_ranges: list[str] | None = None,
    metric_aggregations: list[str] | None = None,
    currency_code: str | None = None,
    keep_empty_rows: bool = False,
    return_property_quota: bool = False,
) -> dict:
    """Build a runReport request body from CLI parameters."""
    metric_list = [m.strip() for m in metrics.split(",")]
    dim_list = [d.strip() for d in dimensions.split(",")] if dimensions else []

    body: dict = {
        "metrics": [{"name": m} for m in metric_list],
        "limit": limit,
    }

    # Date ranges
    if date_ranges:
        body["dateRanges"] = parse_date_ranges(date_ranges)
    else:
        body["dateRanges"] = [{"startDate": start_date, "endDate": end_date}]

    if dim_list:
        body["dimensions"] = [{"name": d} for d in dim_list]

    # Filters
    dim_f, met_f = _resolve_filters(dim_filter, metric_filter, filter_json)
    if dim_f:
        body["dimensionFilter"] = dim_f
    if met_f:
        body["metricFilter"] = met_f

    # Order by
    if order_by:
        body["orderBys"] = parse_order_bys(
            order_by, metrics=metric_list, dimensions=dim_list
        )

    # Offset
    if offset is not None:
        body["offset"] = offset

    # Metric aggregations
    if metric_aggregations:
        body["metricAggregations"] = validate_metric_aggregations(metric_aggregations)

    # Simple scalar options
    if currency_code:
        body["currencyCode"] = currency_code
    if keep_empty_rows:
        body["keepEmptyRows"] = True
    if return_property_quota:
        body["returnPropertyQuota"] = True

    return body


def _display_aggregations(result: dict, effective_format: str) -> None:
    """Render totals/minimums/maximums as a summary table below the main data."""
    met_headers = [h.get("name", "") for h in result.get("metricHeaders", [])]
    agg_rows = []
    for agg_type in ("totals", "minimums", "maximums"):
        for i, row in enumerate(result.get(agg_type, [])):
            entry: dict = {"aggregation": agg_type.rstrip("s").upper()}
            if len(result.get("dateRanges", result.get("dateRanges", []))) > 1:
                entry["dateRange"] = str(i)
            vals = row.get("metricValues", [])
            for j, name in enumerate(met_headers):
                entry[name] = vals[j].get("value", "") if j < len(vals) else ""
            agg_rows.append(entry)

    if not agg_rows:
        return

    columns = list(agg_rows[0].keys())
    headers = list(agg_rows[0].keys())
    if effective_format == "table":
        console.print("\n[bold]Aggregations[/bold]")
    output(agg_rows, effective_format, columns=columns, headers=headers)


def _display_quota(result: dict) -> None:
    """Display property quota information if present."""
    quota = result.get("propertyQuota")
    if not quota:
        return
    parts = []
    for key in ("tokensPerDay", "tokensPerHour", "concurrentRequests",
                "serverErrorsPerProjectPerHour", "potentiallyThresholdedRequestsPerHour"):
        q = quota.get(key)
        if q:
            parts.append(f"{key}: {q.get('consumed', '?')}/{q.get('remaining', '?')}")
    if parts:
        info(f"Quota: {', '.join(parts)}")


@reports_app.command("run")
def run_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metrics: str = typer.Option(
        "sessions,totalUsers", "--metrics", "-m", help="Comma-separated metrics"
    ),
    dimensions: Optional[str] = typer.Option(
        None, "--dimensions", "-d", help="Comma-separated dimensions"
    ),
    start_date: str = typer.Option("7daysAgo", "--start-date", help="Start date"),
    end_date: str = typer.Option("today", "--end-date", help="End date"),
    limit: int = typer.Option(100, "--limit", help="Max rows to return"),
    dim_filter: Optional[list[str]] = typer.Option(
        None, "--dim-filter", help="Dimension filter (repeatable). E.g. 'country==US'"
    ),
    metric_filter: Optional[list[str]] = typer.Option(
        None, "--metric-filter", help="Metric filter (repeatable). E.g. 'sessions>100'"
    ),
    filter_json: Optional[str] = typer.Option(
        None, "--filter-json", help="Raw JSON FilterExpression or @file.json"
    ),
    order_by: Optional[list[str]] = typer.Option(
        None, "--order-by", help="Sort expression (repeatable). E.g. 'sessions:desc'"
    ),
    offset: Optional[int] = typer.Option(
        None, "--offset", help="Row offset for pagination"
    ),
    date_ranges: Optional[list[str]] = typer.Option(
        None, "--date-range",
        help="Date range as start,end (repeatable, overrides --start-date/--end-date)",
    ),
    metric_aggregations: Optional[list[str]] = typer.Option(
        None, "--metric-aggregation", help="Request aggregation rows: TOTAL, MINIMUM, MAXIMUM"
    ),
    currency_code: Optional[str] = typer.Option(
        None, "--currency-code", help="ISO 4217 currency code (e.g. USD)"
    ),
    keep_empty_rows: bool = typer.Option(
        False, "--keep-empty-rows", help="Include rows with all zero metric values"
    ),
    return_property_quota: bool = typer.Option(
        False, "--return-property-quota", help="Return property quota information"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Run a custom report."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        data = get_data_client()

        body = _build_report_body(
            metrics=metrics,
            dimensions=dimensions,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            dim_filter=dim_filter,
            metric_filter=metric_filter,
            filter_json=filter_json,
            order_by=order_by,
            offset=offset,
            date_ranges=date_ranges,
            metric_aggregations=metric_aggregations,
            currency_code=currency_code,
            keep_empty_rows=keep_empty_rows,
            return_property_quota=return_property_quota,
        )

        result = data.properties().runReport(
            property=f"properties/{effective_property}",
            body=body,
        ).execute()

        rows, columns, headers = _transform_report_rows(result)
        row_count = result.get("rowCount", len(rows))

        output(rows, effective_format, columns=columns, headers=headers)

        if effective_format == "table" and row_count > 0:
            console.print(f"\n[dim]{row_count} total rows[/dim]")

        if metric_aggregations:
            _display_aggregations(result, effective_format)

        if return_property_quota:
            _display_quota(result)

    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@reports_app.command("realtime")
def realtime_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metrics: str = typer.Option(
        "activeUsers", "--metrics", "-m", help="Comma-separated metrics"
    ),
    dimensions: Optional[str] = typer.Option(
        None, "--dimensions", "-d", help="Comma-separated dimensions"
    ),
    interval: Optional[int] = typer.Option(
        None, "--interval", help="Refresh interval in seconds (enables polling)"
    ),
    dim_filter: Optional[list[str]] = typer.Option(
        None, "--dim-filter", help="Dimension filter (repeatable). E.g. 'country==US'"
    ),
    metric_filter: Optional[list[str]] = typer.Option(
        None, "--metric-filter", help="Metric filter (repeatable). E.g. 'activeUsers>10'"
    ),
    filter_json: Optional[str] = typer.Option(
        None, "--filter-json", help="Raw JSON FilterExpression or @file.json"
    ),
    order_by: Optional[list[str]] = typer.Option(
        None, "--order-by", help="Sort expression (repeatable). E.g. 'activeUsers:desc'"
    ),
    minute_ranges: Optional[list[str]] = typer.Option(
        None, "--minute-range", help="Minute range as start,end (repeatable). E.g. '0,4'"
    ),
    metric_aggregations: Optional[list[str]] = typer.Option(
        None, "--metric-aggregation", help="Request aggregation rows: TOTAL, MINIMUM, MAXIMUM"
    ),
    return_property_quota: bool = typer.Option(
        False, "--return-property-quota", help="Return property quota information"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get real-time analytics data."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        data_client = get_data_client()

        metric_list = [m.strip() for m in metrics.split(",")]
        dim_list = [d.strip() for d in dimensions.split(",")] if dimensions else []

        body: dict = {
            "metrics": [{"name": m} for m in metric_list],
        }
        if dim_list:
            body["dimensions"] = [{"name": d} for d in dim_list]

        # Filters
        dim_f, met_f = _resolve_filters(dim_filter, metric_filter, filter_json)
        if dim_f:
            body["dimensionFilter"] = dim_f
        if met_f:
            body["metricFilter"] = met_f

        # Order by
        if order_by:
            body["orderBys"] = parse_order_bys(
                order_by, metrics=metric_list, dimensions=dim_list
            )

        # Minute ranges
        if minute_ranges:
            body["minuteRanges"] = parse_minute_ranges(minute_ranges)

        # Metric aggregations
        if metric_aggregations:
            body["metricAggregations"] = validate_metric_aggregations(metric_aggregations)

        if return_property_quota:
            body["returnPropertyQuota"] = True

        if interval:
            info(f"Monitoring real-time data (refresh every {interval}s). Press Ctrl+C to stop.")
            try:
                while True:
                    result = data_client.properties().runRealtimeReport(
                        property=f"properties/{effective_property}",
                        body=body,
                    ).execute()

                    console.clear()
                    rows, columns, headers = _transform_report_rows(result)
                    output(rows, effective_format, columns=columns, headers=headers)

                    time.sleep(interval)
            except KeyboardInterrupt:
                info("Stopped monitoring.")
        else:
            result = data_client.properties().runRealtimeReport(
                property=f"properties/{effective_property}",
                body=body,
            ).execute()

            rows, columns, headers = _transform_report_rows(result)
            output(rows, effective_format, columns=columns, headers=headers)

            if metric_aggregations:
                _display_aggregations(result, effective_format)

            if return_property_quota:
                _display_quota(result)

    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@reports_app.command("pivot")
def pivot_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metrics: str = typer.Option(..., "--metrics", "-m", help="Comma-separated metrics"),
    dimensions: str = typer.Option(
        ..., "--dimensions", "-d", help="Comma-separated dimensions (all used in pivots)"
    ),
    pivot_field: str = typer.Option(
        ..., "--pivot-field", help="Dimension to pivot on (must be in --dimensions)"
    ),
    start_date: str = typer.Option("28daysAgo", "--start-date", help="Start date"),
    end_date: str = typer.Option("yesterday", "--end-date", help="End date"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max rows per pivot group"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Run a pivot report (cross-tabulation)."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        dim_list = [d.strip() for d in dimensions.split(",")]
        pivot_field_clean = pivot_field.strip()

        if pivot_field_clean not in dim_list:
            raise typer.BadParameter(
                f"--pivot-field '{pivot_field_clean}' must be one "
                f"of the --dimensions: {', '.join(dim_list)}"
            )

        row_dims = [d for d in dim_list if d != pivot_field_clean]

        data = get_data_client()

        pivots = [
            {"fieldNames": [pivot_field_clean], "limit": 5},
        ]
        if row_dims:
            pivots.append({"fieldNames": row_dims, "limit": limit})

        body = {
            "metrics": [{"name": m.strip()} for m in metrics.split(",")],
            "dimensions": [{"name": d} for d in dim_list],
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "pivots": pivots,
        }

        result = data.properties().runPivotReport(
            property=f"properties/{effective_property}",
            body=body,
        ).execute()

        if effective_format != "table":
            output(result, effective_format)
            return

        rows, columns, headers = _transform_pivot_rows(result, pivot_field_clean)
        if not rows:
            info("No data returned.")
        else:
            output(rows, effective_format, columns=columns, headers=headers)

    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


def _transform_pivot_rows(
    result: dict, pivot_field: str
) -> tuple[list[dict], list[str], list[str]]:
    """Transform pivot report response into flat rows for table display."""
    pivot_headers = result.get("pivotHeaders", [])
    dim_headers = [h.get("name", "") for h in result.get("dimensionHeaders", [])]
    met_headers = [h.get("name", "") for h in result.get("metricHeaders", [])]

    # Build pivot column values from pivot headers
    pivot_values = []
    if pivot_headers:
        for group in pivot_headers[0].get("pivotDimensionHeaders", []):
            vals = group.get("dimensionValues", [])
            label = vals[0].get("value", "") if vals else ""
            pivot_values.append(label)

    # Non-pivot dimensions
    row_dims = [d for d in dim_headers if d != pivot_field]

    # Build column keys: row dims + pivot_value/metric combos
    columns = list(row_dims)
    headers = list(row_dims)
    for pv in pivot_values:
        for m in met_headers:
            col_key = f"{pv}_{m}"
            columns.append(col_key)
            headers.append(f"{pv} / {m}")

    rows = []
    for row in result.get("rows", []):
        entry = {}
        # Fill row dimensions (skip the pivot field dimension)
        dim_vals = row.get("dimensionValues", [])
        for i, dname in enumerate(dim_headers):
            if dname != pivot_field and i < len(dim_vals):
                entry[dname] = dim_vals[i].get("value", "")

        # Fill metric values per pivot group
        met_vals = row.get("metricValues", [])
        idx = 0
        for pv in pivot_values:
            for m in met_headers:
                col_key = f"{pv}_{m}"
                entry[col_key] = met_vals[idx].get("value", "") if idx < len(met_vals) else ""
                idx += 1

        rows.append(entry)

    return rows, columns, headers


@reports_app.command("check-compatibility")
def check_compatibility_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metrics: Optional[str] = typer.Option(
        None, "--metrics", "-m", help="Comma-separated metrics to check"
    ),
    dimensions: Optional[str] = typer.Option(
        None, "--dimensions", "-d", help="Comma-separated dimensions to check"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Check compatibility of dimensions and metrics."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        if not metrics and not dimensions:
            raise typer.BadParameter(
                "At least one of --metrics or --dimensions must be specified."
            )

        body = {}
        if metrics:
            body["metrics"] = [{"name": m.strip()} for m in metrics.split(",")]
        if dimensions:
            body["dimensions"] = [{"name": d.strip()} for d in dimensions.split(",")]

        data = get_data_client()
        result = data.properties().checkCompatibility(
            property=f"properties/{effective_property}",
            body=body,
        ).execute()

        if effective_format != "table":
            output(result, effective_format)
            return

        # Build a flat list for table output
        rows = []
        for item in result.get("dimensionCompatibilities", []):
            dim_meta = item.get("dimensionMetadata", {})
            rows.append({
                "type": "dimension",
                "apiName": dim_meta.get("apiName", ""),
                "uiName": dim_meta.get("uiName", ""),
                "compatibility": item.get("compatibility", "UNKNOWN"),
            })
        for item in result.get("metricCompatibilities", []):
            met_meta = item.get("metricMetadata", {})
            rows.append({
                "type": "metric",
                "apiName": met_meta.get("apiName", ""),
                "uiName": met_meta.get("uiName", ""),
                "compatibility": item.get("compatibility", "UNKNOWN"),
            })

        output(
            rows,
            effective_format,
            columns=["type", "apiName", "uiName", "compatibility"],
            headers=["Type", "API Name", "UI Name", "Compatibility"],
        )

    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@reports_app.command("metadata")
def metadata_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    filter_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter by 'metrics' or 'dimensions'"
    ),
    search: Optional[str] = typer.Option(
        None, "--search", "-s", help="Filter names containing this string"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Browse available metrics and dimensions for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        data = get_data_client()
        metadata = (
            data.properties()
            .getMetadata(name=f"properties/{effective_property}/metadata")
            .execute()
        )

        rows = []

        if filter_type != "metrics":
            for d in metadata.get("dimensions", []):
                rows.append({
                    "type": "dimension",
                    "apiName": d.get("apiName", ""),
                    "uiName": d.get("uiName", ""),
                    "category": d.get("category", ""),
                    "custom": str(d.get("customDefinition", False)),
                })

        if filter_type != "dimensions":
            for m in metadata.get("metrics", []):
                rows.append({
                    "type": "metric",
                    "apiName": m.get("apiName", ""),
                    "uiName": m.get("uiName", ""),
                    "category": m.get("category", ""),
                    "custom": str(m.get("customDefinition", False)),
                })

        if search:
            search_lower = search.lower()
            rows = [
                r for r in rows
                if search_lower in r["apiName"].lower()
                or search_lower in r["uiName"].lower()
            ]

        if not rows:
            info("No metadata found.")
        else:
            output(
                rows,
                effective_format,
                columns=["type", "apiName", "uiName", "category", "custom"],
                headers=["Type", "API Name", "UI Name", "Category", "Custom"],
            )

    except Exception as e:
        handle_error(e)


@reports_app.command("batch")
def batch_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON batch config file"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Run multiple reports in a single API call (max 5)."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        # Read and parse config file
        config_path = Path(config_file)
        if not config_path.exists():
            raise typer.BadParameter(f"Config file not found: {config_file}")

        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON in config file: {exc}")

        reports = config.get("reports")
        if not isinstance(reports, list) or len(reports) == 0:
            raise typer.BadParameter("Config must contain a non-empty 'reports' array.")

        if len(reports) > 5:
            raise typer.BadParameter(
                f"Batch supports at most 5 reports, got {len(reports)}."
            )

        # Validate each report has metrics, then build request bodies
        requests = []
        for i, spec in enumerate(reports):
            if not spec.get("metrics"):
                raise typer.BadParameter(
                    f"Report {i + 1} is missing required 'metrics' field."
                )
            # Normalise shorthand: list of strings → list of dicts
            if isinstance(spec["metrics"][0], str):
                spec["metrics"] = [{"name": m} for m in spec["metrics"]]
            dims = spec.get("dimensions")
            if dims and isinstance(dims[0], str):
                spec["dimensions"] = [{"name": d} for d in spec["dimensions"]]
            requests.append(spec)

        data = get_data_client()
        result = (
            data.properties()
            .batchRunReports(
                property=f"properties/{effective_property}",
                body={"requests": requests},
            )
            .execute()
        )

        if effective_format != "table":
            output(result, effective_format)
            return

        for idx, report in enumerate(result.get("reports", [])):
            console.print(f"\n[bold]--- Report {idx + 1} ---[/bold]")
            rows, columns, headers = _transform_report_rows(report)
            row_count = report.get("rowCount", len(rows))
            output(rows, effective_format, columns=columns, headers=headers)
            if row_count > 0:
                console.print(f"[dim]{row_count} total rows[/dim]")

    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


def _transform_funnel_rows(result: dict) -> tuple[list[dict], list[str], list[str]]:
    """Transform a funnel report response into flat rows for table display."""
    rows = []
    funnel_table = result.get("funnelTable", {})

    dim_headers = [h.get("name", "") for h in funnel_table.get("dimensionHeaders", [])]
    raw_met_headers = [h.get("name", "") for h in funnel_table.get("metricHeaders", [])]

    for row in funnel_table.get("rows", []):
        entry = {}
        for i, name in enumerate(dim_headers):
            vals = row.get("dimensionValues", [])
            entry[name] = vals[i].get("value", "") if i < len(vals) else ""
        metric_vals = row.get("metricValues", [])
        # Deduplicate metric headers — API may return duplicates; use
        # only as many headers as there are values in this row.
        met_headers = raw_met_headers[:len(metric_vals)]
        # Make header keys unique by appending suffix for duplicates
        seen: dict[str, int] = {}
        unique_headers: list[str] = []
        for name in met_headers:
            if name in seen:
                seen[name] += 1
                unique_headers.append(f"{name}_{seen[name]}")
            else:
                seen[name] = 0
                unique_headers.append(name)
        for i, name in enumerate(unique_headers):
            entry[name] = metric_vals[i].get("value", "") if i < len(metric_vals) else ""
        rows.append(entry)

    columns = [
        "funnelStepName", "activeUsers",
        "funnelStepCompletionRate", "funnelStepAbandonments",
        "funnelStepAbandonmentRate",
    ]
    headers = ["Step Name", "Active Users", "Completion Rate", "Abandonments", "Abandonment Rate"]

    # Only include columns that actually exist in the data
    if rows:
        available = set(rows[0].keys())
        filtered = [(c, h) for c, h in zip(columns, headers) if c in available]
        # Add any extra columns not in our predefined list
        for key in rows[0]:
            if key not in columns:
                filtered.append((key, key))
        columns, headers = zip(*filtered) if filtered else ([], [])
        columns, headers = list(columns), list(headers)

    return rows, columns, headers


@reports_app.command("funnel")
def funnel_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON funnel config file"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Run a funnel report (v1alpha)."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        config_path = Path(config_file)
        if not config_path.exists():
            raise typer.BadParameter(f"Config file not found: {config_file}")

        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON in config file: {exc}")

        funnel = config.get("funnel")
        if not isinstance(funnel, dict) or not funnel.get("steps"):
            raise typer.BadParameter(
                "Config must contain a 'funnel' object with a non-empty 'steps' array."
            )

        data_alpha = get_data_alpha_client()
        result = (
            data_alpha.properties()
            .runFunnelReport(
                property=f"properties/{effective_property}",
                body=config,
            )
            .execute()
        )

        if effective_format != "table":
            output(result, effective_format)
            return

        rows, columns, headers = _transform_funnel_rows(result)
        if not rows:
            info("No funnel data returned.")
        else:
            output(rows, effective_format, columns=columns, headers=headers)

    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


_DIM_FILTER_OPERATORS = [
    "equals (==)",
    "not equals (!=)",
    "contains",
    "begins_with",
    "ends_with",
    "regex (=~)",
    "in list",
]

_METRIC_FILTER_OPERATORS = [
    "greater than (>)",
    "greater or equal (>=)",
    "less than (<)",
    "less or equal (<=)",
    "between",
]

_OPERATOR_SYMBOL_MAP = {
    "equals (==)": "==",
    "not equals (!=)": "!=",
    "contains": " contains ",
    "begins_with": " begins_with ",
    "ends_with": " ends_with ",
    "regex (=~)": "=~",
    "in list": " in ",
    "greater than (>)": ">",
    "greater or equal (>=)": ">=",
    "less than (<)": "<",
    "less or equal (<=)": "<=",
    "between": " between ",
}


def _interactive_filters(
    selected_fields: list[str], operators: list[str], label: str
) -> list[str]:
    """Interactively build filter DSL expressions."""
    filters: list[str] = []
    while True:
        add = questionary.confirm(f"Add a {label} filter?", default=False).ask()
        if not add:
            break

        field = questionary.select(f"Select {label}:", choices=selected_fields).ask()
        op = questionary.select("Operator:", choices=operators).ask()
        value = questionary.text("Value (comma-separated for 'in list'/'between'):").ask()
        if not value:
            continue

        symbol = _OPERATOR_SYMBOL_MAP[op]
        filters.append(f"{field}{symbol}{value}")

    return filters


def _interactive_order_bys(
    selected_metrics: list[str], selected_dims: list[str]
) -> list[str]:
    """Interactively build order-by expressions."""
    order_bys: list[str] = []
    while True:
        add = questionary.confirm("Add a sort?", default=False).ask()
        if not add:
            break

        all_fields = selected_metrics + (selected_dims or [])
        field = questionary.select("Sort by:", choices=all_fields).ask()
        direction = questionary.select("Direction:", choices=["desc", "asc"], default="desc").ask()
        expr = f"{field}:{direction}"

        if field in (selected_dims or []):
            ot = questionary.select(
                "Order type:",
                choices=["default", "alpha", "ialpha", "numeric"],
                default="default",
            ).ask()
            if ot != "default":
                expr += f":{ot}"

        order_bys.append(expr)

    return order_bys


@reports_app.command("build")
def build_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Interactive report builder with available metrics and dimensions."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        data_client = get_data_client()

        # Fetch available metrics/dimensions from the API
        info("Fetching available metrics and dimensions...")
        available_metrics, available_dimensions = _fetch_metadata(
            data_client, effective_property
        )

        selected_metrics = questionary.checkbox(
            "Select metrics:",
            choices=available_metrics,
        ).ask()

        if not selected_metrics:
            info("No metrics selected. Aborting.")
            return

        selected_dims = questionary.checkbox(
            "Select dimensions (optional, press Enter to skip):",
            choices=available_dimensions,
        ).ask()

        date_range = questionary.select(
            "Date range:",
            choices=["7daysAgo", "30daysAgo", "90daysAgo"],
            default="7daysAgo",
        ).ask()

        # --- Filters ---
        dim_filter_exprs: list[str] = []
        if selected_dims:
            dim_filter_exprs = _interactive_filters(
                selected_dims, _DIM_FILTER_OPERATORS, "dimension"
            )

        metric_filter_exprs = _interactive_filters(
            selected_metrics, _METRIC_FILTER_OPERATORS, "metric"
        )

        # --- Order by ---
        order_by_exprs = _interactive_order_bys(selected_metrics, selected_dims or [])

        # --- Additional options ---
        extra_options = questionary.checkbox(
            "Additional options (optional, press Enter to skip):",
            choices=["Keep empty rows", "Return property quota",
                     "Aggregation: TOTAL", "Aggregation: MINIMUM", "Aggregation: MAXIMUM"],
        ).ask()
        extra_options = extra_options or []

        keep_empty = "Keep empty rows" in extra_options
        return_quota = "Return property quota" in extra_options
        agg_values = []
        for opt in extra_options:
            if opt.startswith("Aggregation: "):
                agg_values.append(opt.split(": ", 1)[1])

        info(f"Running report: metrics={selected_metrics}, dimensions={selected_dims or []}")

        body: dict = {
            "metrics": [{"name": m} for m in selected_metrics],
            "dateRanges": [{"startDate": date_range, "endDate": "today"}],
        }
        if selected_dims:
            body["dimensions"] = [{"name": d} for d in selected_dims]

        if dim_filter_exprs:
            body["dimensionFilter"] = parse_dim_filters(dim_filter_exprs)
        if metric_filter_exprs:
            body["metricFilter"] = parse_metric_filters(metric_filter_exprs)
        if order_by_exprs:
            body["orderBys"] = parse_order_bys(
                order_by_exprs, metrics=selected_metrics, dimensions=selected_dims
            )
        if keep_empty:
            body["keepEmptyRows"] = True
        if return_quota:
            body["returnPropertyQuota"] = True
        if agg_values:
            body["metricAggregations"] = validate_metric_aggregations(agg_values)

        result = data_client.properties().runReport(
            property=f"properties/{effective_property}",
            body=body,
        ).execute()

        rows, columns, headers = _transform_report_rows(result)
        row_count = result.get("rowCount", len(rows))

        output(rows, effective_format, columns=columns, headers=headers)

        if effective_format == "table" and row_count > 0:
            console.print(f"\n[dim]{row_count} total rows[/dim]")

        if agg_values:
            _display_aggregations(result, effective_format)

        if return_quota:
            _display_quota(result)

    except Exception as e:
        handle_error(e)
