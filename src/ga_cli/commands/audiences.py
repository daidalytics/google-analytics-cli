"""Audience management commands."""

import json
from pathlib import Path
from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, success
from ..utils.pagination import paginate_all

audiences_app = typer.Typer(
    name="audiences",
    help="Manage audiences",
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


@audiences_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List audiences for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_alpha_client()
        audiences = paginate_all(
            lambda **kw: admin.properties()
            .audiences()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "audiences",
            pageSize=200,
        )

        output(
            audiences,
            effective_format,
            columns=[
                "name",
                "displayName",
                "description",
                "membershipDurationDays",
            ],
            headers=[
                "Resource Name",
                "Display Name",
                "Description",
                "Membership Days",
            ],
        )
    except Exception as e:
        handle_error(e)


@audiences_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    audience_id: str = typer.Option(
        ..., "--audience-id", "-a", help="Audience ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for an audience."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_alpha_client()
        audience = (
            admin.properties()
            .audiences()
            .get(
                name=f"properties/{effective_property}/audiences/{audience_id}"
            )
            .execute()
        )
        output(audience, effective_format)
    except Exception as e:
        handle_error(e)


@audiences_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON audience config file"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create an audience from a JSON config file."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        body = _load_json_config(config_file)

        admin = get_admin_alpha_client()
        audience = (
            admin.properties()
            .audiences()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(audience, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@audiences_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    audience_id: str = typer.Option(
        ..., "--audience-id", "-a", help="Audience ID"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Path to JSON file with fields to update"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update an audience from a JSON config file."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        body = _load_json_config(config_file)

        if not body:
            raise typer.BadParameter("Config file must contain at least one field to update.")

        update_mask = ",".join(body.keys())

        admin = get_admin_alpha_client()
        resource_name = f"properties/{effective_property}/audiences/{audience_id}"
        audience = (
            admin.properties()
            .audiences()
            .patch(
                name=resource_name,
                body=body,
                updateMask=update_mask,
            )
            .execute()
        )
        output(audience, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@audiences_app.command("archive")
def archive_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    audience_id: str = typer.Option(
        ..., "--audience-id", "-a", help="Audience ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Archive an audience."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Archive audience {audience_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_alpha_client()
        resource_name = f"properties/{effective_property}/audiences/{audience_id}"
        admin.properties().audiences().archive(
            name=resource_name, body={}
        ).execute()
        success(f"Audience {audience_id} archived.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
