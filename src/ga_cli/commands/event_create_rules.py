"""Event create rule management commands."""

import json
from pathlib import Path
from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

event_create_rules_app = typer.Typer(
    name="event-create-rules",
    help="Manage event create rules",
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


@event_create_rules_app.command("list")
def list_cmd(
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
    """List event create rules for a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        parent = f"properties/{effective_property}/dataStreams/{stream_id}"
        rules = paginate_all(
            lambda **kw: admin.properties()
            .dataStreams()
            .eventCreateRules()
            .list(parent=parent, **kw)
            .execute(),
            "eventCreateRules",
            pageSize=200,
        )

        output(
            rules,
            effective_format,
            columns=[
                "name",
                "destinationEvent",
                "sourceCopyParameters",
            ],
            headers=[
                "Resource Name",
                "Destination Event",
                "Copy Source Params",
            ],
        )
    except Exception as e:
        handle_error(e)


@event_create_rules_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    rule_id: str = typer.Option(
        ..., "--rule-id", "-r", help="Event create rule ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for an event create rule."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/eventCreateRules/{rule_id}"
        )
        rule = (
            admin.properties()
            .dataStreams()
            .eventCreateRules()
            .get(name=resource_name)
            .execute()
        )
        output(rule, effective_format)
    except Exception as e:
        handle_error(e)


@event_create_rules_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON event create rule config file"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create an event create rule from a JSON config file."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = _load_json_config(config_file)

        admin = get_admin_alpha_client()
        parent = f"properties/{effective_property}/dataStreams/{stream_id}"
        rule = (
            admin.properties()
            .dataStreams()
            .eventCreateRules()
            .create(parent=parent, body=body)
            .execute()
        )
        output(rule, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@event_create_rules_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    rule_id: str = typer.Option(
        ..., "--rule-id", "-r", help="Event create rule ID"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON file with fields to update"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update an event create rule from a JSON config file."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = _load_json_config(config_file)

        if not body:
            raise typer.BadParameter("Config file must contain at least one field to update.")

        update_mask = ",".join(body.keys())

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/eventCreateRules/{rule_id}"
        )
        rule = (
            admin.properties()
            .dataStreams()
            .eventCreateRules()
            .patch(
                name=resource_name,
                body=body,
                updateMask=update_mask,
            )
            .execute()
        )
        output(rule, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@event_create_rules_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    rule_id: str = typer.Option(
        ..., "--rule-id", "-r", help="Event create rule ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete an event create rule."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete event create rule {rule_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/eventCreateRules/{rule_id}"
        )
        admin.properties().dataStreams().eventCreateRules().delete(
            name=resource_name
        ).execute()
        success(f"Event create rule {rule_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
