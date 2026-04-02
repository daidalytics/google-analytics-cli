"""Dry-run support for mutative commands."""

import json
import sys

import typer


def handle_dry_run(
    action: str,
    method: str,
    resource_path: str,
    body: dict | None,
    update_mask: str | None = None,
) -> None:
    """Output what would be sent to the API and exit.

    Always outputs JSON regardless of the current output format,
    since dry-run consumers are primarily agents.

    Args:
        action: "create", "update", "delete", "archive", or "acknowledge"
        method: HTTP method equivalent ("POST", "PATCH", "DELETE")
        resource_path: Full API resource path (e.g., "properties/123456")
        body: Request body dict, or None for deletes
        update_mask: For PATCH requests, the updateMask value
    """
    payload: dict = {
        "dry_run": True,
        "action": action,
        "method": method,
        "resource": resource_path,
        "idempotent": action == "delete",
    }
    if body is not None:
        payload["body"] = body
    if update_mask is not None:
        payload["update_mask"] = update_mask
    print(json.dumps(payload, indent=2), file=sys.stdout)
    raise typer.Exit(0)
