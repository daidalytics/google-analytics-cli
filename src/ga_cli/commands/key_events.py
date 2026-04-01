"""Key event management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

key_events_app = typer.Typer(
    name="key-events",
    help="Manage key events (conversions)",
    no_args_is_help=True,
)

_VALID_COUNTING_METHODS = ("ONCE_PER_EVENT", "ONCE_PER_SESSION")


@key_events_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List key events for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        events = paginate_all(
            lambda **kw: admin.properties()
            .keyEvents()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "keyEvents",
            pageSize=200,
        )

        output(
            events,
            effective_format,
            columns=[
                "name",
                "eventName",
                "createTime",
                "deletable",
                "custom",
                "countingMethod",
            ],
            headers=[
                "Resource Name",
                "Event Name",
                "Create Time",
                "Deletable",
                "Custom",
                "Counting Method",
            ],
        )
    except Exception as e:
        handle_error(e)


@key_events_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    key_event_id: str = typer.Option(
        ..., "--key-event-id", "-k", help="Key event ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a key event."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        event = (
            admin.properties()
            .keyEvents()
            .get(name=f"properties/{effective_property}/keyEvents/{key_event_id}")
            .execute()
        )
        output(event, effective_format)
    except Exception as e:
        handle_error(e)


@key_events_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    event_name: str = typer.Option(
        ..., "--event-name", "-e", help="Event name to mark as key event"
    ),
    counting_method: str = typer.Option(
        "ONCE_PER_EVENT",
        "--counting-method",
        help="Counting method: ONCE_PER_EVENT or ONCE_PER_SESSION",
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a key event."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        method_upper = counting_method.upper()
        if method_upper not in _VALID_COUNTING_METHODS:
            raise typer.BadParameter(
                f"Invalid counting method '{counting_method}'. "
                f"Must be one of: {', '.join(_VALID_COUNTING_METHODS)}"
            )

        admin = get_admin_client()
        body = {
            "eventName": event_name,
            "countingMethod": method_upper,
        }
        event = (
            admin.properties()
            .keyEvents()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(event, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@key_events_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    key_event_id: str = typer.Option(
        ..., "--key-event-id", "-k", help="Key event ID"
    ),
    counting_method: Optional[str] = typer.Option(
        None, "--counting-method", help="New counting method"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a key event."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = {}
        mask_fields = []
        if counting_method is not None:
            method_upper = counting_method.upper()
            if method_upper not in _VALID_COUNTING_METHODS:
                raise typer.BadParameter(
                    f"Invalid counting method '{counting_method}'. "
                f"Must be one of: {', '.join(_VALID_COUNTING_METHODS)}"
                )
            body["countingMethod"] = method_upper
            mask_fields.append("countingMethod")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: --counting-method"
            )

        admin = get_admin_client()
        resource_name = f"properties/{effective_property}/keyEvents/{key_event_id}"
        event = (
            admin.properties()
            .keyEvents()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(event, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@key_events_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    key_event_id: str = typer.Option(
        ..., "--key-event-id", "-k", help="Key event ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a key event."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete key event {key_event_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        resource_name = f"properties/{effective_property}/keyEvents/{key_event_id}"
        admin.properties().keyEvents().delete(name=resource_name).execute()
        success(f"Key event {key_event_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
