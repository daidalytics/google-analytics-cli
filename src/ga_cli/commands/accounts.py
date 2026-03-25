"""Account management commands."""

from typing import Optional

import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, output
from ..utils.pagination import paginate_all

accounts_app = typer.Typer(
    name="accounts", help="Manage GA4 accounts", no_args_is_help=True
)


@accounts_app.command("list")
def list_cmd(
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List all accessible GA4 accounts."""
    try:
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        accounts = paginate_all(
            lambda **kw: admin.accounts().list(**kw).execute(),
            "accounts",
            pageSize=200,
        )
        output(
            accounts,
            effective_format,
            columns=["name", "displayName", "createTime"],
            headers=["Resource Name", "Display Name", "Created"],
        )
    except Exception as e:
        handle_error(e)


@accounts_app.command("get")
def get_cmd(
    account_id: str = typer.Option(
        ..., "--account-id", "-a", help="Account ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a specific account."""
    try:
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        account = admin.accounts().get(name=f"accounts/{account_id}").execute()
        output(account, effective_format)
    except Exception as e:
        handle_error(e)


@accounts_app.command("update")
def update_cmd(
    account_id: str = typer.Option(
        ..., "--account-id", "-a", help="Account ID (numeric)"
    ),
    name: str = typer.Option(..., "--name", help="New display name"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a GA4 account."""
    try:
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_client()
        account = (
            admin.accounts()
            .patch(
                name=f"accounts/{account_id}",
                body={"displayName": name},
                updateMask="displayName",
            )
            .execute()
        )
        output(account, effective_format)
    except Exception as e:
        handle_error(e)
