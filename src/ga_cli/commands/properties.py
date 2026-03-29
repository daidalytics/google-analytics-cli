"""Property management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, success
from ..utils.pagination import paginate_all

properties_app = typer.Typer(name="properties", help="Manage GA4 properties", no_args_is_help=True)


@properties_app.command("list")
def list_cmd(
    account_id: Optional[str] = typer.Option(None, "--account-id", "-a", help="Account ID"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List GA4 properties for an account."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        properties = paginate_all(
            lambda **kw: (
                admin.properties()
                .list(filter=f"parent:accounts/{effective_account}", **kw)
                .execute()
            ),
            "properties",
            pageSize=200,
        )

        output(
            properties,
            effective_format,
            columns=["name", "displayName", "timeZone", "currencyCode"],
            headers=["Resource Name", "Display Name", "Time Zone", "Currency"],
        )
    except Exception as e:
        handle_error(e)


@properties_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a specific property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        prop = admin.properties().get(name=f"properties/{effective_property}").execute()
        output(prop, effective_format)
    except Exception as e:
        handle_error(e)


@properties_app.command("create")
def create_cmd(
    display_name: str = typer.Option(..., "--name", help="Property display name"),
    account_id: Optional[str] = typer.Option(None, "--account-id", "-a", help="Account ID"),
    timezone: str = typer.Option("America/Los_Angeles", "--timezone", help="Reporting time zone"),
    currency: str = typer.Option("USD", "--currency", help="Currency code"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a new GA4 property."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        body = {
            "parent": f"accounts/{effective_account}",
            "displayName": display_name,
            "timeZone": timezone,
            "currencyCode": currency,
        }
        prop = admin.properties().create(body=body).execute()
        output(prop, effective_format)
    except Exception as e:
        handle_error(e)


@properties_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="New display name"),
    timezone: Optional[str] = typer.Option(
        None, "--timezone", help="Reporting time zone (e.g., America/New_York)"
    ),
    currency: Optional[str] = typer.Option(
        None, "--currency", help="Currency code (e.g., USD, EUR)"
    ),
    industry: Optional[str] = typer.Option(None, "--industry", help="Industry category"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a GA4 property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        # Map CLI options to API field names
        field_map = {
            "displayName": name,
            "timeZone": timezone,
            "currencyCode": currency,
            "industryCategory": industry,
        }
        body = {k: v for k, v in field_map.items() if v is not None}

        if not body:
            raise typer.BadParameter(
                "At least one of --name, --timezone, --currency, or --industry must be specified."
            )

        update_mask = ",".join(body.keys())

        admin = get_admin_client()
        prop = (
            admin.properties()
            .patch(
                name=f"properties/{effective_property}",
                body=body,
                updateMask=update_mask,
            )
            .execute()
        )
        output(prop, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@properties_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a GA4 property (soft delete)."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete property {effective_property}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        admin.properties().delete(name=f"properties/{effective_property}").execute()
        success(f"Property {effective_property} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)


_UDC_ACKNOWLEDGEMENT = (
    "I acknowledge that I have the necessary privacy disclosures and rights "
    "from my end users for the collection and processing of their data, "
    "including the association of such data with the visitation information "
    "Google Analytics collects from my site and/or app property."
)


@properties_app.command("acknowledge-udc")
def acknowledge_udc_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Acknowledge user data collection for a property.

    Required before Measurement Protocol secrets can be created.
    """
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            info(f'You are about to acknowledge:\n\n  "{_UDC_ACKNOWLEDGEMENT}"\n')
            confirmed = questionary.confirm("Proceed with acknowledgement?").ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        admin.properties().acknowledgeUserDataCollection(
            property=f"properties/{effective_property}",
            body={"acknowledgement": _UDC_ACKNOWLEDGEMENT},
        ).execute()
        success(f"User data collection acknowledged for property {effective_property}.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
