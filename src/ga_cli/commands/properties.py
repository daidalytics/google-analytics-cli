"""Property management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_client, get_data_alpha_client
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
        effective_format = resolve_output_format(output_format)

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
        effective_format = resolve_output_format(output_format)

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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a new GA4 property."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = resolve_output_format(output_format)

        body = {
            "parent": f"accounts/{effective_account}",
            "displayName": display_name,
            "timeZone": timezone,
            "currencyCode": currency,
        }
        if dry_run:
            handle_dry_run("create", "POST", f"accounts/{effective_account}", body)

        admin = get_admin_client()
        prop = admin.properties().create(body=body).execute()
        output(prop, effective_format)
    except typer.Exit:
        raise
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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a GA4 property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

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

        if dry_run:
            handle_dry_run(
                "update", "PATCH", f"properties/{effective_property}",
                body, update_mask=update_mask,
            )

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
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)


@properties_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
):
    """Delete a GA4 property (soft delete)."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if dry_run:
            handle_dry_run("delete", "DELETE", f"properties/{effective_property}", None)

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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
):
    """Acknowledge user data collection for a property.

    Required before Measurement Protocol secrets can be created.
    """
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if dry_run:
            handle_dry_run(
                "acknowledge", "POST", f"properties/{effective_property}",
                {"acknowledgement": _UDC_ACKNOWLEDGEMENT},
            )

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


def _format_quota_category(key: str) -> str:
    """Convert API field name to human-readable label (e.g. 'tokensPerDay' -> 'Tokens Per Day')."""
    import re

    # Split on camelCase boundaries
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    return words.title()


@properties_app.command("quotas")
def quotas_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Show API quota usage for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        data_alpha = get_data_alpha_client()
        result = (
            data_alpha.properties()
            .getPropertyQuotasSnapshot(
                name=f"properties/{effective_property}/propertyQuotasSnapshot"
            )
            .execute()
        )

        if effective_format != "table":
            output(result, effective_format)
            return

        rows = []
        for category_key, category_value in result.items():
            if not isinstance(category_value, dict):
                continue
            category_label = _format_quota_category(category_key)
            for metric_key, metric_value in category_value.items():
                if isinstance(metric_value, dict) and "remaining" in metric_value:
                    rows.append({
                        "category": category_label,
                        "metric": _format_quota_category(metric_key),
                        "consumed": str(metric_value.get("consumed", 0)),
                        "remaining": str(metric_value.get("remaining", 0)),
                    })

        if not rows:
            info("No quota data available.")
        else:
            output(
                rows,
                effective_format,
                columns=["category", "metric", "consumed", "remaining"],
                headers=["Quota Category", "Metric", "Consumed", "Remaining"],
            )

    except Exception as e:
        handle_error(e)
