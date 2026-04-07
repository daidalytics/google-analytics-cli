"""Enhanced measurement settings commands for a data stream."""

from typing import Optional

import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import (
    handle_dry_run,
    handle_error,
    output,
    require_options,
    resolve_output_format,
    success,
)

enhanced_measurement_app = typer.Typer(
    name="enhanced-measurement",
    help="Manage enhanced measurement settings for a data stream",
    no_args_is_help=True,
)


def _resource_name(property_id: str, stream_id: str) -> str:
    return (
        f"properties/{property_id}/dataStreams/{stream_id}"
        "/enhancedMeasurementSettings"
    )


@enhanced_measurement_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get enhanced measurement settings for a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        settings = (
            admin.properties()
            .dataStreams()
            .getEnhancedMeasurementSettings(
                name=_resource_name(effective_property, stream_id)
            )
            .execute()
        )
        output(settings, effective_format)
    except Exception as e:
        handle_error(e)


@enhanced_measurement_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    stream_enabled: Optional[bool] = typer.Option(
        None,
        "--stream-enabled/--no-stream-enabled",
        help="Enable/disable enhanced measurement for this stream",
    ),
    scrolls: Optional[bool] = typer.Option(
        None, "--scrolls/--no-scrolls", help="Capture scroll events"
    ),
    outbound_clicks: Optional[bool] = typer.Option(
        None, "--outbound-clicks/--no-outbound-clicks", help="Capture outbound click events"
    ),
    site_search: Optional[bool] = typer.Option(
        None, "--site-search/--no-site-search", help="Capture site search events"
    ),
    video_engagement: Optional[bool] = typer.Option(
        None, "--video-engagement/--no-video-engagement", help="Capture video engagement events"
    ),
    file_downloads: Optional[bool] = typer.Option(
        None, "--file-downloads/--no-file-downloads", help="Capture file download events"
    ),
    page_changes: Optional[bool] = typer.Option(
        None, "--page-changes/--no-page-changes", help="Capture page change (history) events"
    ),
    form_interactions: Optional[bool] = typer.Option(
        None, "--form-interactions/--no-form-interactions", help="Capture form interaction events"
    ),
    search_query_parameter: Optional[str] = typer.Option(
        None, "--search-query-parameter", help="URL query parameters for site search"
    ),
    uri_query_parameter: Optional[str] = typer.Option(
        None, "--uri-query-parameter", help="Additional URL query parameters"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update enhanced measurement settings for a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        field_map = {
            "streamEnabled": stream_enabled,
            "scrollsEnabled": scrolls,
            "outboundClicksEnabled": outbound_clicks,
            "siteSearchEnabled": site_search,
            "videoEngagementEnabled": video_engagement,
            "fileDownloadsEnabled": file_downloads,
            "pageChangesEnabled": page_changes,
            "formInteractionsEnabled": form_interactions,
            "searchQueryParameter": search_query_parameter,
            "uriQueryParameter": uri_query_parameter,
        }
        body = {k: v for k, v in field_map.items() if v is not None}

        if not body:
            raise typer.BadParameter(
                "At least one update flag must be specified (e.g. --scrolls, "
                "--stream-enabled, --search-query-parameter)."
            )

        update_mask = ",".join(body.keys())
        resource = _resource_name(effective_property, stream_id)

        if dry_run:
            handle_dry_run("update", "PATCH", resource, body, update_mask=update_mask)

        admin = get_admin_alpha_client()
        settings = (
            admin.properties()
            .dataStreams()
            .updateEnhancedMeasurementSettings(
                name=resource, updateMask=update_mask, body=body
            )
            .execute()
        )
        success("Enhanced measurement settings updated.")
        output(settings, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)
