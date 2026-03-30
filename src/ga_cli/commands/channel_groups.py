"""Channel group management commands."""

import json
from pathlib import Path
from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, success
from ..utils.pagination import paginate_all

channel_groups_app = typer.Typer(
    name="channel-groups",
    help="Manage channel groups",
    no_args_is_help=True,
)


def _load_json_config(config_file: str) -> dict:
    """Load and parse a JSON config file."""
    config_path = Path(config_file)
    if not config_path.exists():
        raise typer.BadParameter(f"Config file not found: {config_file}")
    try:
        return json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON in config file: {exc}")


@channel_groups_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List channel groups for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_alpha_client()
        groups = paginate_all(
            lambda **kw: admin.properties()
            .channelGroups()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "channelGroups",
            pageSize=200,
        )

        output(
            groups,
            effective_format,
            columns=[
                "name",
                "displayName",
                "description",
                "systemDefined",
            ],
            headers=[
                "Resource Name",
                "Display Name",
                "Description",
                "System Defined",
            ],
        )
    except Exception as e:
        handle_error(e)


@channel_groups_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    channel_group_id: str = typer.Option(
        ..., "--channel-group-id", "-g", help="Channel group ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a channel group."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_alpha_client()
        group = (
            admin.properties()
            .channelGroups()
            .get(
                name=f"properties/{effective_property}/channelGroups/{channel_group_id}"
            )
            .execute()
        )
        output(group, effective_format)
    except Exception as e:
        handle_error(e)


@channel_groups_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON channel group config file"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a channel group from a JSON config file."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        body = _load_json_config(config_file)

        admin = get_admin_alpha_client()
        group = (
            admin.properties()
            .channelGroups()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(group, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@channel_groups_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    channel_group_id: str = typer.Option(
        ..., "--channel-group-id", "-g", help="Channel group ID"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON file with fields to update"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a channel group from a JSON config file."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        body = _load_json_config(config_file)

        if not body:
            raise typer.BadParameter("Config file must contain at least one field to update.")

        update_mask = ",".join(body.keys())

        admin = get_admin_alpha_client()
        resource_name = f"properties/{effective_property}/channelGroups/{channel_group_id}"
        group = (
            admin.properties()
            .channelGroups()
            .patch(
                name=resource_name,
                body=body,
                updateMask=update_mask,
            )
            .execute()
        )
        output(group, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@channel_groups_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    channel_group_id: str = typer.Option(
        ..., "--channel-group-id", "-g", help="Channel group ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a channel group."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete channel group {channel_group_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_alpha_client()
        resource_name = f"properties/{effective_property}/channelGroups/{channel_group_id}"
        admin.properties().channelGroups().delete(
            name=resource_name
        ).execute()
        success(f"Channel group {channel_group_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
