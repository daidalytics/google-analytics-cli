"""Report commands: run, realtime, build.

Uses the Analytics Data API v1beta.
"""

import json
import time
from pathlib import Path
from typing import Optional

import questionary
import typer

from ..api.client import get_data_client
from ..config.store import get_effective_value
from ..utils import console, handle_error, info, output, require_options

reports_app = typer.Typer(
    name="reports", help="Run GA4 reports", no_args_is_help=True
)

# Fallback metrics/dimensions when metadata API is unavailable
_FALLBACK_METRICS = [
    "sessions",
    "users",
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


@reports_app.command("run")
def run_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metrics: str = typer.Option(
        "sessions,users", "--metrics", "-m", help="Comma-separated metrics"
    ),
    dimensions: Optional[str] = typer.Option(
        None, "--dimensions", "-d", help="Comma-separated dimensions"
    ),
    start_date: str = typer.Option("7daysAgo", "--start-date", help="Start date"),
    end_date: str = typer.Option("today", "--end-date", help="End date"),
    limit: int = typer.Option(100, "--limit", help="Max rows to return"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Run a custom report."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        data = get_data_client()

        body = {
            "metrics": [{"name": m.strip()} for m in metrics.split(",")],
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "limit": limit,
        }
        if dimensions:
            body["dimensions"] = [{"name": d.strip()} for d in dimensions.split(",")]

        result = data.properties().runReport(
            property=f"properties/{effective_property}",
            body=body,
        ).execute()

        rows, columns, headers = _transform_report_rows(result)
        row_count = result.get("rowCount", len(rows))

        output(rows, effective_format, columns=columns, headers=headers)

        if effective_format == "table" and row_count > 0:
            console.print(f"\n[dim]{row_count} total rows[/dim]")

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
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get real-time analytics data."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        data_client = get_data_client()

        body = {
            "metrics": [{"name": m.strip()} for m in metrics.split(",")],
        }
        if dimensions:
            body["dimensions"] = [{"name": d.strip()} for d in dimensions.split(",")]

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
        effective_format = get_effective_value(output_format, "output_format") or "table"

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
        effective_format = get_effective_value(output_format, "output_format") or "table"

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
        effective_format = get_effective_value(output_format, "output_format") or "table"

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
        effective_format = get_effective_value(output_format, "output_format") or "table"

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
        effective_format = get_effective_value(output_format, "output_format") or "table"

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

        info(f"Running report: metrics={selected_metrics}, dimensions={selected_dims or []}")

        body = {
            "metrics": [{"name": m} for m in selected_metrics],
            "dateRanges": [{"startDate": date_range, "endDate": "today"}],
        }
        if selected_dims:
            body["dimensions"] = [{"name": d} for d in selected_dims]

        result = data_client.properties().runReport(
            property=f"properties/{effective_property}",
            body=body,
        ).execute()

        rows, columns, headers = _transform_report_rows(result)
        row_count = result.get("rowCount", len(rows))

        output(rows, effective_format, columns=columns, headers=headers)

        if effective_format == "table" and row_count > 0:
            console.print(f"\n[dim]{row_count} total rows[/dim]")

    except Exception as e:
        handle_error(e)
