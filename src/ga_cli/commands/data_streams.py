"""Data stream management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

data_streams_app = typer.Typer(
    name="data-streams", help="Manage GA4 data streams", no_args_is_help=True
)

# Stream types that require additional configuration
_WEB_STREAM = "WEB_DATA_STREAM"
_ANDROID_STREAM = "ANDROID_APP_DATA_STREAM"
_IOS_STREAM = "IOS_APP_DATA_STREAM"


@data_streams_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List data streams for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        streams = paginate_all(
            lambda **kw: admin.properties()
            .dataStreams()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "dataStreams",
            pageSize=200,
        )

        output(
            streams,
            effective_format,
            columns=["name", "type", "displayName", "createTime"],
            headers=["Resource Name", "Type", "Display Name", "Created"],
        )
    except Exception as e:
        handle_error(e)


@data_streams_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data Stream ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get data stream details."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        stream = (
            admin.properties()
            .dataStreams()
            .get(
                name=f"properties/{effective_property}/dataStreams/{stream_id}",
            )
            .execute()
        )
        output(stream, effective_format)
    except Exception as e:
        handle_error(e)


@data_streams_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    display_name: str = typer.Option(
        ..., "--display-name", help="Stream display name"
    ),
    stream_type: str = typer.Option(
        _WEB_STREAM,
        "--type",
        "-t",
        help="Stream type: WEB_DATA_STREAM, ANDROID_APP_DATA_STREAM, IOS_APP_DATA_STREAM",
    ),
    url: Optional[str] = typer.Option(
        None, "--url", help="Default URI (required for web streams)"
    ),
    bundle_id: Optional[str] = typer.Option(
        None, "--bundle-id", help="App bundle ID (required for app streams)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a new data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = {
            "displayName": display_name,
            "type": stream_type,
        }

        # Validate and add type-specific data
        if stream_type == _WEB_STREAM:
            if not url:
                raise typer.BadParameter(
                    "--url is required for WEB_DATA_STREAM type"
                )
            body["webStreamData"] = {"defaultUri": url}
        elif stream_type == _ANDROID_STREAM:
            if not bundle_id:
                raise typer.BadParameter(
                    "--bundle-id is required for ANDROID_APP_DATA_STREAM type"
                )
            body["androidAppStreamData"] = {"packageName": bundle_id}
        elif stream_type == _IOS_STREAM:
            if not bundle_id:
                raise typer.BadParameter(
                    "--bundle-id is required for IOS_APP_DATA_STREAM type"
                )
            body["iosAppStreamData"] = {"bundleId": bundle_id}

        admin = get_admin_client()
        stream = (
            admin.properties()
            .dataStreams()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(stream, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@data_streams_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data Stream ID"
    ),
    display_name: Optional[str] = typer.Option(
        None, "--display-name", help="New display name"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        field_map = {
            "displayName": display_name,
        }
        body = {k: v for k, v in field_map.items() if v is not None}

        if not body:
            raise typer.BadParameter(
                "At least one of --display-name must be specified."
            )

        update_mask = ",".join(body.keys())

        admin = get_admin_client()
        stream = (
            admin.properties()
            .dataStreams()
            .patch(
                name=f"properties/{effective_property}/dataStreams/{stream_id}",
                body=body,
                updateMask=update_mask,
            )
            .execute()
        )
        output(stream, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@data_streams_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data Stream ID"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
):
    """Delete a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete data stream {stream_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        admin.properties().dataStreams().delete(
            name=f"properties/{effective_property}/dataStreams/{stream_id}",
        ).execute()
        success(f"Data stream {stream_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
