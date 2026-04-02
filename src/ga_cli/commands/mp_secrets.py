"""Measurement Protocol secret management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import (
    handle_dry_run,
    handle_error,
    info,
    output,
    require_options,
    resolve_output_format,
    success,
)
from ..utils.pagination import paginate_all

mp_secrets_app = typer.Typer(
    name="mp-secrets",
    help="Manage Measurement Protocol secrets",
    no_args_is_help=True,
)


@mp_secrets_app.command("list")
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
    """List Measurement Protocol secrets for a data stream."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        parent = f"properties/{effective_property}/dataStreams/{stream_id}"
        secrets = paginate_all(
            lambda **kw: admin.properties()
            .dataStreams()
            .measurementProtocolSecrets()
            .list(parent=parent, **kw)
            .execute(),
            "measurementProtocolSecrets",
            pageSize=200,
        )

        output(
            secrets,
            effective_format,
            columns=["name", "displayName", "secretValue"],
            headers=["Resource Name", "Display Name", "Secret Value"],
        )
    except Exception as e:
        handle_error(e)


@mp_secrets_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    secret_id: str = typer.Option(
        ..., "--secret-id", help="Measurement Protocol secret ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a Measurement Protocol secret."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/measurementProtocolSecrets/{secret_id}"
        )
        secret = (
            admin.properties()
            .dataStreams()
            .measurementProtocolSecrets()
            .get(name=resource_name)
            .execute()
        )
        output(secret, effective_format)
    except Exception as e:
        handle_error(e)


@mp_secrets_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    display_name: str = typer.Option(
        ..., "--display-name", help="Display name for the secret"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a Measurement Protocol secret."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        parent = f"properties/{effective_property}/dataStreams/{stream_id}"
        body = {"displayName": display_name}
        if dry_run:
            handle_dry_run("create", "POST", parent, body)

        admin = get_admin_client()
        secret = (
            admin.properties()
            .dataStreams()
            .measurementProtocolSecrets()
            .create(parent=parent, body=body)
            .execute()
        )
        output(secret, effective_format)
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)


@mp_secrets_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    secret_id: str = typer.Option(
        ..., "--secret-id", help="Measurement Protocol secret ID"
    ),
    display_name: Optional[str] = typer.Option(
        None, "--display-name", help="New display name"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a Measurement Protocol secret."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = {}
        mask_fields = []
        if display_name is not None:
            body["displayName"] = display_name
            mask_fields.append("displayName")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: --display-name"
            )

        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/measurementProtocolSecrets/{secret_id}"
        )
        if dry_run:
            handle_dry_run(
                "update", "PATCH", resource_name,
                body, update_mask=",".join(mask_fields),
            )

        admin = get_admin_client()
        secret = (
            admin.properties()
            .dataStreams()
            .measurementProtocolSecrets()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(secret, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)


@mp_secrets_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    secret_id: str = typer.Option(
        ..., "--secret-id", help="Measurement Protocol secret ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
):
    """Delete a Measurement Protocol secret."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if dry_run:
            resource_name = (
                f"properties/{effective_property}/dataStreams/{stream_id}"
                f"/measurementProtocolSecrets/{secret_id}"
            )
            handle_dry_run("delete", "DELETE", resource_name, None)

        if not yes:
            confirmed = questionary.confirm(
                f"Delete Measurement Protocol secret {secret_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            f"/measurementProtocolSecrets/{secret_id}"
        )
        admin.properties().dataStreams().measurementProtocolSecrets().delete(
            name=resource_name
        ).execute()
        success(f"Measurement Protocol secret {secret_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
