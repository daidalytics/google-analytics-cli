"""BigQuery link management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

bigquery_links_app = typer.Typer(
    name="bigquery-links",
    help="Manage BigQuery links",
    no_args_is_help=True,
)


def _normalize_project(project: str) -> str:
    """Ensure project is in 'projects/{id}' format."""
    if project.startswith("projects/"):
        return project
    return f"projects/{project}"


@bigquery_links_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List BigQuery links for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        links = paginate_all(
            lambda **kw: admin.properties()
            .bigQueryLinks()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "bigqueryLinks",
            pageSize=200,
        )

        output(
            links,
            effective_format,
            columns=[
                "name",
                "project",
                "datasetLocation",
                "dailyExportEnabled",
                "streamingExportEnabled",
                "createTime",
            ],
            headers=[
                "Resource Name",
                "Project",
                "Dataset Location",
                "Daily Export",
                "Streaming Export",
                "Create Time",
            ],
        )
    except Exception as e:
        handle_error(e)


@bigquery_links_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    link_id: str = typer.Option(
        ..., "--link-id", "-l", help="BigQuery link ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a BigQuery link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        link = (
            admin.properties()
            .bigQueryLinks()
            .get(
                name=f"properties/{effective_property}/bigQueryLinks/{link_id}"
            )
            .execute()
        )
        output(link, effective_format)
    except Exception as e:
        handle_error(e)


@bigquery_links_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    project: str = typer.Option(
        ..., "--project", help="Google Cloud project (number or ID)"
    ),
    dataset_location: str = typer.Option(
        ..., "--dataset-location", help="BigQuery dataset location (e.g., US, EU)"
    ),
    daily_export: Optional[bool] = typer.Option(
        None, "--daily-export/--no-daily-export", help="Enable daily export"
    ),
    streaming_export: Optional[bool] = typer.Option(
        None, "--streaming-export/--no-streaming-export", help="Enable streaming export"
    ),
    fresh_daily_export: Optional[bool] = typer.Option(
        None, "--fresh-daily-export/--no-fresh-daily-export", help="Enable fresh daily export"
    ),
    include_advertising_id: Optional[bool] = typer.Option(
        None,
        "--include-advertising-id/--no-include-advertising-id",
        help="Include advertising identifiers for mobile app streams",
    ),
    export_streams: Optional[str] = typer.Option(
        None, "--export-streams", help="Comma-separated data stream IDs to export"
    ),
    excluded_events: Optional[str] = typer.Option(
        None, "--excluded-events", help="Comma-separated event names to exclude"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a BigQuery link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = {
            "project": _normalize_project(project),
            "datasetLocation": dataset_location,
        }
        if daily_export is not None:
            body["dailyExportEnabled"] = daily_export
        if streaming_export is not None:
            body["streamingExportEnabled"] = streaming_export
        if fresh_daily_export is not None:
            body["freshDailyExportEnabled"] = fresh_daily_export
        if include_advertising_id is not None:
            body["includeAdvertisingId"] = include_advertising_id
        if export_streams is not None:
            body["exportStreams"] = [
                f"properties/{effective_property}/dataStreams/{sid.strip()}"
                for sid in export_streams.split(",")
            ]
        if excluded_events is not None:
            body["excludedEvents"] = [
                e.strip() for e in excluded_events.split(",")
            ]

        admin = get_admin_alpha_client()
        link = (
            admin.properties()
            .bigQueryLinks()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(link, effective_format)
    except Exception as e:
        handle_error(e)


@bigquery_links_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    link_id: str = typer.Option(
        ..., "--link-id", "-l", help="BigQuery link ID"
    ),
    daily_export: Optional[bool] = typer.Option(
        None, "--daily-export/--no-daily-export", help="Enable daily export"
    ),
    streaming_export: Optional[bool] = typer.Option(
        None, "--streaming-export/--no-streaming-export", help="Enable streaming export"
    ),
    fresh_daily_export: Optional[bool] = typer.Option(
        None, "--fresh-daily-export/--no-fresh-daily-export", help="Enable fresh daily export"
    ),
    include_advertising_id: Optional[bool] = typer.Option(
        None,
        "--include-advertising-id/--no-include-advertising-id",
        help="Include advertising identifiers for mobile app streams",
    ),
    export_streams: Optional[str] = typer.Option(
        None, "--export-streams", help="Comma-separated data stream IDs to export"
    ),
    excluded_events: Optional[str] = typer.Option(
        None, "--excluded-events", help="Comma-separated event names to exclude"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a BigQuery link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = {}
        mask_fields = []
        if daily_export is not None:
            body["dailyExportEnabled"] = daily_export
            mask_fields.append("dailyExportEnabled")
        if streaming_export is not None:
            body["streamingExportEnabled"] = streaming_export
            mask_fields.append("streamingExportEnabled")
        if fresh_daily_export is not None:
            body["freshDailyExportEnabled"] = fresh_daily_export
            mask_fields.append("freshDailyExportEnabled")
        if include_advertising_id is not None:
            body["includeAdvertisingId"] = include_advertising_id
            mask_fields.append("includeAdvertisingId")
        if export_streams is not None:
            body["exportStreams"] = [
                f"properties/{effective_property}/dataStreams/{sid.strip()}"
                for sid in export_streams.split(",")
            ]
            mask_fields.append("exportStreams")
        if excluded_events is not None:
            body["excludedEvents"] = [
                e.strip() for e in excluded_events.split(",")
            ]
            mask_fields.append("excludedEvents")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: "
                "--daily-export, --streaming-export, --fresh-daily-export, "
                "--include-advertising-id, --export-streams, --excluded-events"
            )

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/bigQueryLinks/{link_id}"
        )
        link = (
            admin.properties()
            .bigQueryLinks()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(link, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@bigquery_links_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    link_id: str = typer.Option(
        ..., "--link-id", "-l", help="BigQuery link ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a BigQuery link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete BigQuery link {link_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/bigQueryLinks/{link_id}"
        )
        admin.properties().bigQueryLinks().delete(
            name=resource_name
        ).execute()
        success(f"BigQuery link {link_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
