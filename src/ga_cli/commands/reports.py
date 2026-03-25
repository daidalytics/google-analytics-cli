"""Report commands: run, realtime, build.

Uses the Analytics Data API v1beta.
"""

import time
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
