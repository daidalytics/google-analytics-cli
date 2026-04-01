"""Firebase link management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

firebase_links_app = typer.Typer(
    name="firebase-links",
    help="Manage Firebase links",
    no_args_is_help=True,
)


@firebase_links_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List Firebase links for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        links = paginate_all(
            lambda **kw: admin.properties()
            .firebaseLinks()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "firebaseLinks",
            pageSize=200,
        )

        output(
            links,
            effective_format,
            columns=["name", "project", "createTime"],
            headers=["Resource Name", "Project", "Create Time"],
        )
    except Exception as e:
        handle_error(e)


@firebase_links_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    project: str = typer.Option(
        ..., "--project", help="Firebase project resource name (e.g., projects/my-project)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a Firebase link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_client()
        body = {"project": project}
        link = (
            admin.properties()
            .firebaseLinks()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(link, effective_format)
    except Exception as e:
        handle_error(e)


@firebase_links_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    link_id: str = typer.Option(
        ..., "--link-id", help="Firebase link ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a Firebase link."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete Firebase link {link_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_client()
        resource_name = f"properties/{effective_property}/firebaseLinks/{link_id}"
        admin.properties().firebaseLinks().delete(name=resource_name).execute()
        success(f"Firebase link {link_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
