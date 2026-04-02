"""Account management commands."""

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

accounts_app = typer.Typer(name="accounts", help="Manage GA4 accounts", no_args_is_help=True)


@accounts_app.command("list")
def list_cmd(
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List all accessible GA4 accounts."""
    try:
        effective_format = resolve_output_format(output_format)

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
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a specific account."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        account = admin.accounts().get(name=f"accounts/{effective_account}").execute()
        output(account, effective_format)
    except Exception as e:
        handle_error(e)


@accounts_app.command("update")
def update_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID (numeric)"
    ),
    name: str = typer.Option(..., "--name", help="New display name"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a GA4 account."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = resolve_output_format(output_format)

        body = {"displayName": name}
        if dry_run:
            handle_dry_run(
                "update", "PATCH", f"accounts/{effective_account}",
                body, update_mask="displayName",
            )

        admin = get_admin_client()
        account = (
            admin.accounts()
            .patch(
                name=f"accounts/{effective_account}",
                body=body,
                updateMask="displayName",
            )
            .execute()
        )
        output(account, effective_format)
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)


@accounts_app.command("delete")
def delete_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID (numeric)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
):
    """Delete a GA4 account (soft delete, moves to trash)."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])

        if dry_run:
            handle_dry_run("delete", "DELETE", f"accounts/{effective_account}", None)

        if not yes:
            confirmed = questionary.confirm(
                f"Delete account {effective_account}? "
                "All child resources (properties, streams, links) will be trashed."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        admin.accounts().delete(name=f"accounts/{effective_account}").execute()
        success(f"Account {effective_account} deleted (moved to trash).")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)


@accounts_app.command("get-data-sharing")
def get_data_sharing_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get data sharing settings for an account (read-only)."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        settings = (
            admin.accounts()
            .getDataSharingSettings(name=f"accounts/{effective_account}/dataSharingSettings")
            .execute()
        )
        output(
            settings,
            effective_format,
            columns=[
                "name",
                "sharingWithGoogleSupportEnabled",
                "sharingWithGoogleAssignedSalesEnabled",
                "sharingWithGoogleProductsEnabled",
                "sharingWithOthersEnabled",
            ],
            headers=[
                "Resource Name",
                "Google Support",
                "Google Sales",
                "Google Products",
                "Others",
            ],
        )
    except Exception as e:
        handle_error(e)


def _extract_resource_name(change: dict) -> str:
    """Extract a human-readable resource name from a change entry."""
    for key in ("resourceAfterChange", "resourceBeforeChange"):
        container = change.get(key)
        if not container:
            continue
        for resource_obj in container.values():
            if isinstance(resource_obj, dict):
                return resource_obj.get("displayName") or resource_obj.get("name", "")
    return ""


def _flatten_change_events(events: list) -> list[dict]:
    """Flatten change history events into one row per change."""
    rows = []
    for event in events:
        for change in event.get("changes", []):
            rows.append(
                {
                    "changeTime": event.get("changeTime", ""),
                    "actor": event.get("userActorEmail") or event.get("actorType", ""),
                    "resourceType": change.get("resource", ""),
                    "action": change.get("action", ""),
                    "resourceName": _extract_resource_name(change),
                }
            )
    return rows


@accounts_app.command("change-history")
def change_history_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID (numeric)"
    ),
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Filter to specific property"
    ),
    resource_type: Optional[str] = typer.Option(
        None, "--resource-type", help="Filter by resource type (ACCOUNT, PROPERTY, etc.)"
    ),
    action: Optional[str] = typer.Option(
        None, "--action", help="Filter by action (CREATED, UPDATED, DELETED)"
    ),
    earliest_change_time: Optional[str] = typer.Option(
        None, "--since", help="Earliest change time (ISO 8601)"
    ),
    latest_change_time: Optional[str] = typer.Option(
        None, "--until", help="Latest change time (ISO 8601)"
    ),
    limit: int = typer.Option(100, "--limit", "-l", help="Max results to return"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
) -> None:
    """Search change history events for an account."""
    try:
        effective_account = get_effective_value(account_id, "default_account_id")
        require_options({"account_id": effective_account}, ["account_id"])
        effective_format = resolve_output_format(output_format)

        body: dict = {}
        if property_id:
            body["property"] = f"properties/{property_id}"
        if resource_type:
            body["resourceType"] = [resource_type.upper()]
        if action:
            body["action"] = [action.upper()]
        if earliest_change_time:
            body["earliestChangeTime"] = earliest_change_time
        if latest_change_time:
            body["latestChangeTime"] = latest_change_time

        admin = get_admin_client()
        events = paginate_all(
            lambda **kw: (
                admin.accounts()
                .searchChangeHistoryEvents(
                    account=f"accounts/{effective_account}",
                    body={**body, **kw},
                )
                .execute()
            ),
            "changeHistoryEvents",
            pageSize=200,
        )

        events = events[:limit]

        if not events:
            info("No changes found.")
            return

        if effective_format == "json":
            output(events, effective_format)
        else:
            rows = _flatten_change_events(events)
            output(
                rows,
                effective_format,
                columns=["changeTime", "actor", "resourceType", "action", "resourceName"],
                headers=["Time", "Actor", "Resource Type", "Action", "Resource Name"],
            )
    except Exception as e:
        handle_error(e)
