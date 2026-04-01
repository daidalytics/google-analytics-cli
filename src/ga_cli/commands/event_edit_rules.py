"""Event edit rule management commands."""

import json
from pathlib import Path
from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

event_edit_rules_app = typer.Typer(
    name="event-edit-rules",
    help="Manage event edit rules",
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


@event_edit_rules_app.command("list")
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
    """List event edit rules for a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        parent = f"properties/{effective_property}/dataStreams/{stream_id}"
        rules = paginate_all(
            lambda **kw: admin.properties()
            .dataStreams()
            .eventEditRules()
            .list(parent=parent, **kw)
            .execute(),
            "eventEditRules",
            pageSize=200,
        )

        output(
            rules,
            effective_format,
            columns=[
                "name",
                "displayName",
                "processingOrder",
            ],
            headers=[
                "Resource Name",
                "Display Name",
                "Processing Order",
            ],
        )
    except Exception as e:
        handle_error(e)


@event_edit_rules_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    rule_id: str = typer.Option(
        ..., "--rule-id", "-r", help="Event edit rule ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for an event edit rule."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/eventEditRules/{rule_id}"
        )
        rule = (
            admin.properties()
            .dataStreams()
            .eventEditRules()
            .get(name=resource_name)
            .execute()
        )
        output(rule, effective_format)
    except Exception as e:
        handle_error(e)


@event_edit_rules_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON event edit rule config file"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create an event edit rule from a JSON config file."""
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
            .eventEditRules()
            .create(parent=parent, body=body)
            .execute()
        )
        output(rule, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@event_edit_rules_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    rule_id: str = typer.Option(
        ..., "--rule-id", "-r", help="Event edit rule ID"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON file with fields to update"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update an event edit rule from a JSON config file."""
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
            f"/eventEditRules/{rule_id}"
        )
        rule = (
            admin.properties()
            .dataStreams()
            .eventEditRules()
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


@event_edit_rules_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    rule_id: str = typer.Option(
        ..., "--rule-id", "-r", help="Event edit rule ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete an event edit rule."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete event edit rule {rule_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/eventEditRules/{rule_id}"
        )
        admin.properties().dataStreams().eventEditRules().delete(
            name=resource_name
        ).execute()
        success(f"Event edit rule {rule_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)


@event_edit_rules_app.command("reorder")
def reorder_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    rule_ids: str = typer.Option(
        ...,
        "--rule-ids",
        help="Comma-separated rule IDs in desired processing order (all rules must be included)",
    ),
):
    """Reorder event edit rules on a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        parent = f"properties/{effective_property}/dataStreams/{stream_id}"
        ids = [rid.strip() for rid in rule_ids.split(",") if rid.strip()]

        if not ids:
            raise typer.BadParameter("--rule-ids must contain at least one rule ID.")

        body = {
            "eventEditRules": [
                f"{parent}/eventEditRules/{rid}" for rid in ids
            ]
        }

        admin = get_admin_alpha_client()
        admin.properties().dataStreams().eventEditRules().reorder(
            parent=parent, body=body
        ).execute()
        success("Event edit rules reordered.")
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)
