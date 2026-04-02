"""Custom metric management commands."""

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

custom_metrics_app = typer.Typer(
    name="custom-metrics",
    help="Manage custom metrics",
    no_args_is_help=True,
)

_VALID_SCOPES = ("EVENT",)
_VALID_MEASUREMENT_UNITS = (
    "STANDARD",
    "CURRENCY",
    "FEET",
    "METERS",
    "KILOMETERS",
    "MILES",
    "MILLISECONDS",
    "SECONDS",
    "MINUTES",
    "HOURS",
)


@custom_metrics_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List custom metrics for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        metrics = paginate_all(
            lambda **kw: admin.properties()
            .customMetrics()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "customMetrics",
            pageSize=200,
        )

        output(
            metrics,
            effective_format,
            columns=[
                "name",
                "parameterName",
                "displayName",
                "scope",
                "measurementUnit",
                "description",
            ],
            headers=[
                "Resource Name",
                "Parameter Name",
                "Display Name",
                "Scope",
                "Measurement Unit",
                "Description",
            ],
        )
    except Exception as e:
        handle_error(e)


@custom_metrics_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metric_id: str = typer.Option(
        ..., "--metric-id", "-m", help="Custom metric ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a custom metric."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        metric = (
            admin.properties()
            .customMetrics()
            .get(name=f"properties/{effective_property}/customMetrics/{metric_id}")
            .execute()
        )
        output(metric, effective_format)
    except Exception as e:
        handle_error(e)


@custom_metrics_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    parameter_name: str = typer.Option(
        ..., "--parameter-name", help="Event parameter name"
    ),
    display_name: str = typer.Option(..., "--display-name", help="Display name in GA4 UI"),
    scope: str = typer.Option(..., "--scope", help="Scope: EVENT"),
    measurement_unit: str = typer.Option(
        ...,
        "--measurement-unit",
        help="Unit: STANDARD, CURRENCY, FEET, METERS, KILOMETERS, "
        "MILES, MILLISECONDS, SECONDS, MINUTES, HOURS",
    ),
    description: str = typer.Option("", "--description", help="Description"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a custom metric."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        scope_upper = scope.upper()
        if scope_upper not in _VALID_SCOPES:
            raise typer.BadParameter(
                f"Invalid scope '{scope}'. Must be one of: {', '.join(_VALID_SCOPES)}"
            )

        unit_upper = measurement_unit.upper()
        if unit_upper not in _VALID_MEASUREMENT_UNITS:
            raise typer.BadParameter(
                f"Invalid measurement unit '{measurement_unit}'. "
                f"Must be one of: {', '.join(_VALID_MEASUREMENT_UNITS)}"
            )

        body = {
            "parameterName": parameter_name,
            "displayName": display_name,
            "scope": scope_upper,
            "measurementUnit": unit_upper,
            "description": description,
        }
        if dry_run:
            handle_dry_run("create", "POST", f"properties/{effective_property}", body)

        admin = get_admin_client()
        metric = (
            admin.properties()
            .customMetrics()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(metric, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)


@custom_metrics_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metric_id: str = typer.Option(
        ..., "--metric-id", "-m", help="Custom metric ID"
    ),
    display_name: Optional[str] = typer.Option(None, "--display-name", help="New display name"),
    description: Optional[str] = typer.Option(None, "--description", help="New description"),
    measurement_unit: Optional[str] = typer.Option(
        None, "--measurement-unit", help="New measurement unit"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a custom metric."""
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
        if measurement_unit is not None:
            unit_upper = measurement_unit.upper()
            if unit_upper not in _VALID_MEASUREMENT_UNITS:
                raise typer.BadParameter(
                    f"Invalid measurement unit '{measurement_unit}'. "
                f"Must be one of: {', '.join(_VALID_MEASUREMENT_UNITS)}"
                )
            body["measurementUnit"] = unit_upper
            mask_fields.append("measurementUnit")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: "
                "--display-name, --description, --measurement-unit"
            )

        resource_name = f"properties/{effective_property}/customMetrics/{metric_id}"
        if dry_run:
            handle_dry_run(
                "update", "PATCH", resource_name,
                body, update_mask=",".join(mask_fields),
            )

        admin = get_admin_client()
        metric = (
            admin.properties()
            .customMetrics()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(metric, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)


@custom_metrics_app.command("archive")
def archive_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metric_id: str = typer.Option(
        ..., "--metric-id", "-m", help="Custom metric ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
):
    """Archive a custom metric."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if dry_run:
            handle_dry_run(
                "archive", "POST",
                f"properties/{effective_property}/customMetrics/{metric_id}",
                None,
            )

        if not yes:
            confirmed = questionary.confirm(
                f"Archive custom metric {metric_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        resource_name = f"properties/{effective_property}/customMetrics/{metric_id}"
        admin.properties().customMetrics().archive(
            name=resource_name, body={}
        ).execute()
        success(f"Custom metric {metric_id} archived.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
