"""Access binding management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, success
from ..utils.pagination import paginate_all

access_bindings_app = typer.Typer(
    name="access-bindings",
    help="Manage access bindings (user-role assignments)",
    no_args_is_help=True,
)


def _resolve_parent(
    account_id: Optional[str], property_id: Optional[str]
) -> tuple[str, str]:
    """Resolve the parent resource for access binding commands.

    Exactly one of account_id or property_id must be provided.
    property_id falls back to config default if not explicitly set.

    Returns (parent_string, parent_type) where parent_type is
    "accounts" or "properties".
    """
    effective_property = get_effective_value(property_id, "default_property_id")

    if account_id and effective_property:
        raise typer.BadParameter(
            "Provide either --account-id or --property-id, not both."
        )
    if account_id:
        return f"accounts/{account_id}", "accounts"
    if effective_property:
        return f"properties/{effective_property}", "properties"
    raise typer.BadParameter(
        "Either --account-id or --property-id is required."
    )


def _get_access_bindings_resource(admin, parent_type: str):
    """Get the correct accessBindings API resource for the parent type."""
    if parent_type == "accounts":
        return admin.accounts().accessBindings()
    return admin.properties().accessBindings()


def _format_roles(roles: list[str]) -> str:
    """Strip predefinedRoles/ prefix for display."""
    return ", ".join(r.removeprefix("predefinedRoles/") for r in roles)


@access_bindings_app.command("list")
def list_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID"
    ),
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List access bindings for an account or property."""
    try:
        parent, parent_type = _resolve_parent(account_id, property_id)
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_alpha_client()
        resource = _get_access_bindings_resource(admin, parent_type)
        bindings = paginate_all(
            lambda **kw: resource.list(parent=parent, **kw).execute(),
            "accessBindings",
            pageSize=500,
        )

        # Format roles for table display
        for b in bindings:
            if "roles" in b:
                b["_roles_display"] = _format_roles(b["roles"])

        output(
            bindings,
            effective_format,
            columns=["name", "user", "_roles_display"],
            headers=["Resource Name", "User", "Roles"],
        )
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@access_bindings_app.command("get")
def get_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID"
    ),
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    binding_id: str = typer.Option(
        ..., "--binding-id", "-b", help="Access binding ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for an access binding."""
    try:
        parent, parent_type = _resolve_parent(account_id, property_id)
        effective_format = get_effective_value(output_format, "output_format") or "table"

        admin = get_admin_alpha_client()
        resource = _get_access_bindings_resource(admin, parent_type)
        resource_name = f"{parent}/accessBindings/{binding_id}"
        binding = resource.get(name=resource_name).execute()
        output(binding, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@access_bindings_app.command("create")
def create_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID"
    ),
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    user: str = typer.Option(
        ..., "--user", "-u", help="Email address of the user"
    ),
    roles: str = typer.Option(
        ..., "--roles", "-r", help="Comma-separated roles (e.g. viewer,editor)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create an access binding for a user."""
    try:
        parent, parent_type = _resolve_parent(account_id, property_id)
        effective_format = get_effective_value(output_format, "output_format") or "table"

        role_list = [
            r.strip() if "/" in r.strip() else f"predefinedRoles/{r.strip()}"
            for r in roles.split(",")
            if r.strip()
        ]

        if not role_list:
            raise typer.BadParameter("--roles must contain at least one role.")

        body = {"user": user, "roles": role_list}

        admin = get_admin_alpha_client()
        resource = _get_access_bindings_resource(admin, parent_type)
        binding = resource.create(parent=parent, body=body).execute()
        output(binding, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@access_bindings_app.command("update")
def update_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID"
    ),
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    binding_id: str = typer.Option(
        ..., "--binding-id", "-b", help="Access binding ID"
    ),
    roles: str = typer.Option(
        ..., "--roles", "-r", help="Comma-separated roles (e.g. viewer,editor)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update roles for an access binding."""
    try:
        parent, parent_type = _resolve_parent(account_id, property_id)
        effective_format = get_effective_value(output_format, "output_format") or "table"

        role_list = [
            r.strip() if "/" in r.strip() else f"predefinedRoles/{r.strip()}"
            for r in roles.split(",")
            if r.strip()
        ]

        if not role_list:
            raise typer.BadParameter("--roles must contain at least one role.")

        resource_name = f"{parent}/accessBindings/{binding_id}"
        body = {"name": resource_name, "roles": role_list}

        admin = get_admin_alpha_client()
        resource = _get_access_bindings_resource(admin, parent_type)
        binding = resource.patch(name=resource_name, body=body).execute()
        output(binding, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@access_bindings_app.command("delete")
def delete_cmd(
    account_id: Optional[str] = typer.Option(
        None, "--account-id", "-a", help="Account ID"
    ),
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    binding_id: str = typer.Option(
        ..., "--binding-id", "-b", help="Access binding ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete an access binding."""
    try:
        parent, parent_type = _resolve_parent(account_id, property_id)

        if not yes:
            confirmed = questionary.confirm(
                f"Delete access binding {binding_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        resource_name = f"{parent}/accessBindings/{binding_id}"
        admin = get_admin_alpha_client()
        resource = _get_access_bindings_resource(admin, parent_type)
        resource.delete(name=resource_name).execute()
        success(f"Access binding {binding_id} deleted.")
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)
