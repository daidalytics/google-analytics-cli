"""Data retention settings commands."""

from typing import Optional

import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, output, require_options, success

data_retention_app = typer.Typer(
    name="data-retention",
    help="Manage data retention settings for a property",
    no_args_is_help=True,
)

_RETENTION_CHOICES = [
    "TWO_MONTHS",
    "FOURTEEN_MONTHS",
    "TWENTY_SIX_MONTHS",
    "THIRTY_EIGHT_MONTHS",
    "FIFTY_MONTHS",
]


@data_retention_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get data retention settings for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        settings = (
            admin.properties()
            .getDataRetentionSettings(name=f"properties/{effective_property}/dataRetentionSettings")
            .execute()
        )
        output(
            settings,
            effective_format,
            columns=[
                "name",
                "eventDataRetention",
                "userDataRetention",
                "resetUserDataOnNewActivity",
            ],
            headers=[
                "Resource Name",
                "Event Data Retention",
                "User Data Retention",
                "Reset on New Activity",
            ],
        )
    except Exception as e:
        handle_error(e)


@data_retention_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    event_data_retention: Optional[str] = typer.Option(
        None,
        "--event-data-retention",
        help=f"Event data retention period ({', '.join(_RETENTION_CHOICES)})",
    ),
    user_data_retention: Optional[str] = typer.Option(
        None,
        "--user-data-retention",
        help=f"User data retention period ({', '.join(_RETENTION_CHOICES)})",
    ),
    reset_on_new_activity: Optional[bool] = typer.Option(
        None,
        "--reset-on-new-activity/--no-reset-on-new-activity",
        help="Reset user data retention on new activity",
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update data retention settings for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        field_map = {
            "eventDataRetention": event_data_retention,
            "userDataRetention": user_data_retention,
            "resetUserDataOnNewActivity": reset_on_new_activity,
        }
        body = {k: v for k, v in field_map.items() if v is not None}

        if not body:
            raise typer.BadParameter(
                "At least one of --event-data-retention, --user-data-retention, "
                "or --reset-on-new-activity must be specified."
            )

        # Validate retention values
        for key in ("eventDataRetention", "userDataRetention"):
            val = body.get(key)
            if val and val not in _RETENTION_CHOICES:
                raise typer.BadParameter(
                    f"Invalid value '{val}' for {key}. "
                    f"Must be one of: {', '.join(_RETENTION_CHOICES)}"
                )

        update_mask = ",".join(body.keys())

        admin = get_admin_client()
        settings = (
            admin.properties()
            .updateDataRetentionSettings(
                name=f"properties/{effective_property}/dataRetentionSettings",
                updateMask=update_mask,
                body=body,
            )
            .execute()
        )
        success("Data retention settings updated.")
        output(settings, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)
