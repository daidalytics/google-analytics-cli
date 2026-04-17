"""User-provided data settings commands for a property."""

from typing import Optional

import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, output, require_options, resolve_output_format

user_provided_data_app = typer.Typer(
    name="user-provided-data",
    help="Manage user-provided data settings for a property",
    no_args_is_help=True,
)


@user_provided_data_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get user-provided data settings for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        settings = (
            admin.properties()
            .getUserProvidedDataSettings(
                name=f"properties/{effective_property}/userProvidedDataSettings"
            )
            .execute()
        )
        output(
            settings,
            effective_format,
            columns=[
                "name",
                "userProvidedDataCollectionEnabled",
                "automaticallyDetectedDataCollectionEnabled",
            ],
            headers=[
                "Resource Name",
                "Data Collection Enabled",
                "Auto-Detection Enabled",
            ],
        )
    except Exception as e:
        handle_error(e)
