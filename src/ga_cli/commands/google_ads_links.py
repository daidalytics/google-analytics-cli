"""Google Ads link management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, success
from ..utils.pagination import paginate_all

google_ads_links_app = typer.Typer(
    name="google-ads-links",
    help="Manage Google Ads links",
    no_args_is_help=True,
)


@google_ads_links_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List Google Ads links for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        links = paginate_all(
            lambda **kw: admin.properties()
            .googleAdsLinks()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "googleAdsLinks",
            pageSize=200,
        )

        output(
            links,
            effective_format,
            columns=[
                "name",
                "customerId",
                "canManageClients",
                "adsPersonalizationEnabled",
                "createTime",
            ],
            headers=[
                "Resource Name",
                "Customer ID",
                "Can Manage Clients",
                "Ads Personalization",
                "Create Time",
            ],
        )
    except Exception as e:
        handle_error(e)


@google_ads_links_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    customer_id: str = typer.Option(
        ..., "--customer-id", help="Google Ads customer ID"
    ),
    ads_personalization: bool = typer.Option(
        True,
        "--ads-personalization/--no-ads-personalization",
        help="Enable ads personalization",
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a Google Ads link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        body = {
            "customerId": customer_id,
            "adsPersonalizationEnabled": ads_personalization,
        }
        link = (
            admin.properties()
            .googleAdsLinks()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(link, effective_format)
    except Exception as e:
        handle_error(e)


@google_ads_links_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    link_id: str = typer.Option(
        ..., "--link-id", help="Google Ads link ID"
    ),
    ads_personalization: Optional[bool] = typer.Option(
        None,
        "--ads-personalization/--no-ads-personalization",
        help="Enable or disable ads personalization",
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a Google Ads link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = get_effective_value(output_format, "output_format") or "table"

        body = {}
        mask_fields = []
        if ads_personalization is not None:
            body["adsPersonalizationEnabled"] = ads_personalization
            mask_fields.append("adsPersonalizationEnabled")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: "
                "--ads-personalization / --no-ads-personalization"
            )

        admin = get_admin_client()
        resource_name = f"properties/{effective_property}/googleAdsLinks/{link_id}"
        link = (
            admin.properties()
            .googleAdsLinks()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(link, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@google_ads_links_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    link_id: str = typer.Option(
        ..., "--link-id", help="Google Ads link ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a Google Ads link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete Google Ads link {link_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        resource_name = f"properties/{effective_property}/googleAdsLinks/{link_id}"
        admin.properties().googleAdsLinks().delete(name=resource_name).execute()
        success(f"Google Ads link {link_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
