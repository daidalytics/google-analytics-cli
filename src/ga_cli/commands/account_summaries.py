"""Account summaries command."""

from typing import Optional

import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, output
from ..utils.pagination import paginate_all

account_summaries_app = typer.Typer(
    name="account-summaries",
    help="View account summaries",
    no_args_is_help=True,
)


@account_summaries_app.command("list")
def list_cmd(
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List all accounts with their property summaries."""
    try:
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        summaries = paginate_all(
            lambda **kw: admin.accountSummaries().list(**kw).execute(),
            "accountSummaries",
            pageSize=200,
        )

        if effective_format != "table":
            output(summaries, effective_format)
            return

        # Flatten into rows: one row per property
        rows = []
        for acct in summaries:
            acct_name = acct.get("displayName", "")
            acct_id = acct.get("account", "").replace("accounts/", "")
            for prop in acct.get("propertySummaries", []):
                rows.append({
                    "accountName": acct_name,
                    "accountId": acct_id,
                    "propertyName": prop.get("displayName", ""),
                    "propertyId": prop.get("property", "").replace("properties/", ""),
                    "propertyType": prop.get("propertyType", ""),
                })
            if not acct.get("propertySummaries"):
                rows.append({
                    "accountName": acct_name,
                    "accountId": acct_id,
                    "propertyName": "",
                    "propertyId": "",
                    "propertyType": "",
                })

        output(
            rows,
            effective_format,
            columns=["accountName", "accountId", "propertyName", "propertyId", "propertyType"],
            headers=["Account Name", "Account ID", "Property Name", "Property ID", "Property Type"],
        )
    except Exception as e:
        handle_error(e)
