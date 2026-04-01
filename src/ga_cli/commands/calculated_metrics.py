"""Calculated metric management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

calculated_metrics_app = typer.Typer(
    name="calculated-metrics",
    help="Manage calculated metrics",
    no_args_is_help=True,
)

_VALID_METRIC_UNITS = (
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


@calculated_metrics_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List calculated metrics for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        metrics = paginate_all(
            lambda **kw: admin.properties()
            .calculatedMetrics()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "calculatedMetrics",
            pageSize=200,
        )

        output(
            metrics,
            effective_format,
            columns=[
                "name",
                "calculatedMetricId",
                "displayName",
                "formula",
                "metricUnit",
            ],
            headers=[
                "Resource Name",
                "Metric ID",
                "Display Name",
                "Formula",
                "Metric Unit",
            ],
        )
    except Exception as e:
        handle_error(e)


@calculated_metrics_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metric_id: str = typer.Option(
        ..., "--metric-id", "-m", help="Calculated metric ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a calculated metric."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        metric = (
            admin.properties()
            .calculatedMetrics()
            .get(
                name=f"properties/{effective_property}/calculatedMetrics/{metric_id}"
            )
            .execute()
        )
        output(metric, effective_format)
    except Exception as e:
        handle_error(e)


@calculated_metrics_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    calculated_metric_id: str = typer.Option(
        ..., "--calculated-metric-id", help="Unique metric ID (e.g., 'revenuePerUser')"
    ),
    display_name: str = typer.Option(..., "--display-name", help="Display name"),
    formula: str = typer.Option(
        ..., "--formula", help='Formula (e.g., "{{totalRevenue}} / {{totalUsers}}")'
    ),
    metric_unit: str = typer.Option(
        ..., "--metric-unit", help="Metric unit (STANDARD, CURRENCY, etc.)"
    ),
    description: str = typer.Option("", "--description", help="Description"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a calculated metric."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        unit_upper = metric_unit.upper()
        if unit_upper not in _VALID_METRIC_UNITS:
            raise typer.BadParameter(
                f"Invalid metric unit '{metric_unit}'. "
                f"Must be one of: {', '.join(_VALID_METRIC_UNITS)}"
            )

        admin = get_admin_alpha_client()
        body = {
            "displayName": display_name,
            "description": description,
            "formula": formula,
            "metricUnit": unit_upper,
        }
        metric = (
            admin.properties()
            .calculatedMetrics()
            .create(
                parent=f"properties/{effective_property}",
                calculatedMetricId=calculated_metric_id,
                body=body,
            )
            .execute()
        )
        output(metric, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@calculated_metrics_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metric_id: str = typer.Option(
        ..., "--metric-id", "-m", help="Calculated metric ID"
    ),
    display_name: Optional[str] = typer.Option(
        None, "--display-name", help="New display name"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="New description"
    ),
    formula: Optional[str] = typer.Option(None, "--formula", help="New formula"),
    metric_unit: Optional[str] = typer.Option(
        None, "--metric-unit", help="New metric unit"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a calculated metric."""
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
        if formula is not None:
            body["formula"] = formula
            mask_fields.append("formula")
        if metric_unit is not None:
            unit_upper = metric_unit.upper()
            if unit_upper not in _VALID_METRIC_UNITS:
                raise typer.BadParameter(
                    f"Invalid metric unit '{metric_unit}'. "
                    f"Must be one of: {', '.join(_VALID_METRIC_UNITS)}"
                )
            body["metricUnit"] = unit_upper
            mask_fields.append("metricUnit")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: "
                "--display-name, --description, --formula, --metric-unit"
            )

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/calculatedMetrics/{metric_id}"
        )
        metric = (
            admin.properties()
            .calculatedMetrics()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(metric, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@calculated_metrics_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    metric_id: str = typer.Option(
        ..., "--metric-id", "-m", help="Calculated metric ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a calculated metric."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete calculated metric {metric_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_alpha_client()
        resource_name = (
            f"properties/{effective_property}/calculatedMetrics/{metric_id}"
        )
        admin.properties().calculatedMetrics().delete(
            name=resource_name
        ).execute()
        success(f"Calculated metric {metric_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
