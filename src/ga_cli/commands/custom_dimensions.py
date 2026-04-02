"""Custom dimension management commands."""

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

custom_dimensions_app = typer.Typer(
    name="custom-dimensions",
    help="Manage custom dimensions",
    no_args_is_help=True,
)

_VALID_SCOPES = ("EVENT", "USER", "ITEM")


@custom_dimensions_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List custom dimensions for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        dimensions = paginate_all(
            lambda **kw: admin.properties()
            .customDimensions()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "customDimensions",
            pageSize=200,
        )

        output(
            dimensions,
            effective_format,
            columns=[
                "name",
                "parameterName",
                "displayName",
                "scope",
                "description",
                "disallowAdsPersonalization",
            ],
            headers=[
                "Resource Name",
                "Parameter Name",
                "Display Name",
                "Scope",
                "Description",
                "Disallow Ads",
            ],
        )
    except Exception as e:
        handle_error(e)


@custom_dimensions_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    dimension_id: str = typer.Option(
        ..., "--dimension-id", "-d", help="Custom dimension ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a custom dimension."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        dimension = (
            admin.properties()
            .customDimensions()
            .get(
                name=f"properties/{effective_property}/customDimensions/{dimension_id}"
            )
            .execute()
        )
        output(dimension, effective_format)
    except Exception as e:
        handle_error(e)


@custom_dimensions_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    parameter_name: str = typer.Option(
        ..., "--parameter-name", help="Event parameter name"
    ),
    display_name: str = typer.Option(..., "--display-name", help="Display name in GA4 UI"),
    scope: str = typer.Option(..., "--scope", help="Scope: EVENT, USER, or ITEM"),
    description: str = typer.Option("", "--description", help="Description"),
    disallow_ads: bool = typer.Option(
        False, "--disallow-ads", help="Disallow ads personalization"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a custom dimension."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        scope_upper = scope.upper()
        if scope_upper not in _VALID_SCOPES:
            raise typer.BadParameter(
                f"Invalid scope '{scope}'. Must be one of: {', '.join(_VALID_SCOPES)}"
            )

        body = {
            "parameterName": parameter_name,
            "displayName": display_name,
            "scope": scope_upper,
            "description": description,
            "disallowAdsPersonalization": disallow_ads,
        }
        if dry_run:
            handle_dry_run("create", "POST", f"properties/{effective_property}", body)

        admin = get_admin_client()
        dimension = (
            admin.properties()
            .customDimensions()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(dimension, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)


@custom_dimensions_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    dimension_id: str = typer.Option(
        ..., "--dimension-id", "-d", help="Custom dimension ID"
    ),
    display_name: Optional[str] = typer.Option(None, "--display-name", help="New display name"),
    description: Optional[str] = typer.Option(None, "--description", help="New description"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a custom dimension."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = {}
        mask_fields = []
        if display_name is not None:
            body["displayName"] = display_name
            mask_fields.append("displayName")
        if description is not None:
            body["description"] = description
            mask_fields.append("description")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: --display-name, --description"
            )

        resource_name = f"properties/{effective_property}/customDimensions/{dimension_id}"
        if dry_run:
            handle_dry_run(
                "update", "PATCH", resource_name,
                body, update_mask=",".join(mask_fields),
            )

        admin = get_admin_client()
        dimension = (
            admin.properties()
            .customDimensions()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(dimension, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)


@custom_dimensions_app.command("archive")
def archive_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    dimension_id: str = typer.Option(
        ..., "--dimension-id", "-d", help="Custom dimension ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
):
    """Archive a custom dimension."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if dry_run:
            handle_dry_run(
                "archive", "POST",
                f"properties/{effective_property}/customDimensions/{dimension_id}",
                None,
            )

        if not yes:
            confirmed = questionary.confirm(
                f"Archive custom dimension {dimension_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        resource_name = f"properties/{effective_property}/customDimensions/{dimension_id}"
        admin.properties().customDimensions().archive(
            name=resource_name, body={}
        ).execute()
        success(f"Custom dimension {dimension_id} archived.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
