"""Access report commands: who accessed what data and when.

Uses the Analytics Admin API v1beta runAccessReport endpoint.
"""

from typing import Optional

import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import console, handle_error, info, output, require_options, resolve_output_format

access_reports_app = typer.Typer(
    name="access-reports",
    help="Run data-access reports (who accessed what)",
    no_args_is_help=True,
)

_DEFAULT_DIMENSIONS = "userEmail,epochTimeMicros"
_DEFAULT_METRICS = "accessCount"


def _build_access_report_body(
    dimensions: str,
    metrics: str,
    start_date: str,
    end_date: str,
    limit: int,
    offset: int,
    include_all_users: bool,
    expand_groups: bool,
) -> dict:
    """Build the request body for runAccessReport."""
    body: dict = {
        "dimensions": [{"dimensionName": d.strip()} for d in dimensions.split(",")],
        "metrics": [{"metricName": m.strip()} for m in metrics.split(",")],
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "limit": limit,
    }
    if offset > 0:
        body["offset"] = offset
    if include_all_users:
        body["includeAllUsers"] = True
    if expand_groups:
        body["expandGroups"] = True
    return body


def _transform_access_rows(result: dict) -> tuple[list[dict], list[str], list[str]]:
    """Transform an access report response into a list of dicts."""
    dim_headers = [h.get("dimensionName", "") for h in result.get("dimensionHeaders", [])]
    met_headers = [h.get("metricName", "") for h in result.get("metricHeaders", [])]

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


@access_reports_app.command("run-account")
def run_account_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID (numeric)"
    ),
    dimensions: str = typer.Option(
        _DEFAULT_DIMENSIONS, "--dimensions", "-d", help="Comma-separated dimension names"
    ),
    metrics: str = typer.Option(
        _DEFAULT_METRICS, "--metrics", "-m", help="Comma-separated metric names"
    ),
    start_date: str = typer.Option("7daysAgo", "--start-date", help="Start date"),
    end_date: str = typer.Option("today", "--end-date", help="End date"),
    limit: int = typer.Option(10000, "--limit", "-l", help="Max rows to return"),
    offset: int = typer.Option(0, "--offset", help="Row offset for pagination"),
    include_all_users: bool = typer.Option(
        False, "--include-all-users", help="Include users who never made an API call"
    ),
    expand_groups: bool = typer.Option(
        False, "--expand-groups", help="Expand user group members (requires --include-all-users)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Run a data-access report for an account."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = resolve_output_format(output_format)

        body = _build_access_report_body(
            dimensions,
            metrics,
            start_date,
            end_date,
            limit,
            offset,
            include_all_users,
            expand_groups,
        )

        admin = get_admin_client()
        result = (
            admin.accounts()
            .runAccessReport(
                entity=f"accounts/{effective_account}",
                body=body,
            )
            .execute()
        )

        rows, columns, headers = _transform_access_rows(result)
        row_count = result.get("rowCount", len(rows))

        if not rows:
            info("No access data found.")
            return

        output(rows, effective_format, columns=columns, headers=headers)

        if effective_format == "table" and row_count > 0:
            console.print(f"\n[dim]{row_count} total rows[/dim]")

    except Exception as e:
        handle_error(e)


@access_reports_app.command("run-property")
def run_property_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    dimensions: str = typer.Option(
        _DEFAULT_DIMENSIONS, "--dimensions", "-d", help="Comma-separated dimension names"
    ),
    metrics: str = typer.Option(
        _DEFAULT_METRICS, "--metrics", "-m", help="Comma-separated metric names"
    ),
    start_date: str = typer.Option("7daysAgo", "--start-date", help="Start date"),
    end_date: str = typer.Option("today", "--end-date", help="End date"),
    limit: int = typer.Option(10000, "--limit", "-l", help="Max rows to return"),
    offset: int = typer.Option(0, "--offset", help="Row offset for pagination"),
    include_all_users: bool = typer.Option(
        False, "--include-all-users", help="Include users who never made an API call"
    ),
    expand_groups: bool = typer.Option(
        False, "--expand-groups", help="Expand user group members (requires --include-all-users)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Run a data-access report for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = _build_access_report_body(
            dimensions,
            metrics,
            start_date,
            end_date,
            limit,
            offset,
            include_all_users,
            expand_groups,
        )

        admin = get_admin_client()
        result = (
            admin.properties()
            .runAccessReport(
                entity=f"properties/{effective_property}",
                body=body,
            )
            .execute()
        )

        rows, columns, headers = _transform_access_rows(result)
        row_count = result.get("rowCount", len(rows))

        if not rows:
            info("No access data found.")
            return

        output(rows, effective_format, columns=columns, headers=headers)

        if effective_format == "table" and row_count > 0:
            console.print(f"\n[dim]{row_count} total rows[/dim]")

    except Exception as e:
        handle_error(e)
