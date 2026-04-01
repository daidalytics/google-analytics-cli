"""Reporting data annotation management commands."""

from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, info, output, require_options, resolve_output_format, success
from ..utils.pagination import paginate_all

annotations_app = typer.Typer(
    name="annotations",
    help="Manage reporting data annotations",
    no_args_is_help=True,
)


@annotations_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List reporting data annotations for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        annotations = paginate_all(
            lambda **kw: admin.properties()
            .reportingDataAnnotations()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "reportingDataAnnotations",
            pageSize=200,
        )

        output(
            annotations,
            effective_format,
            columns=[
                "name",
                "title",
                "annotationDate",
                "description",
                "color",
            ],
            headers=[
                "Resource Name",
                "Title",
                "Date",
                "Description",
                "Color",
            ],
        )
    except Exception as e:
        handle_error(e)


@annotations_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    annotation_id: str = typer.Option(
        ..., "--annotation-id", "-a", help="Annotation ID"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get details for a reporting data annotation."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        annotation = (
            admin.properties()
            .reportingDataAnnotations()
            .get(
                name=f"properties/{effective_property}/reportingDataAnnotations/{annotation_id}"
            )
            .execute()
        )
        output(annotation, effective_format)
    except Exception as e:
        handle_error(e)


@annotations_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    title: str = typer.Option(..., "--title", help="Annotation title"),
    annotation_date: str = typer.Option(
        ..., "--annotation-date", help="Date in YYYY-MM-DD format"
    ),
    description: str = typer.Option("", "--description", help="Annotation description"),
    color: Optional[str] = typer.Option(None, "--color", help="Annotation color"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a reporting data annotation."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        admin = get_admin_alpha_client()
        body = {
            "title": title,
            "annotationDate": annotation_date,
            "description": description,
        }
        if color is not None:
            body["color"] = color

        annotation = (
            admin.properties()
            .reportingDataAnnotations()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(annotation, effective_format)
    except Exception as e:
        handle_error(e)


@annotations_app.command("update")
def update_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    annotation_id: str = typer.Option(
        ..., "--annotation-id", "-a", help="Annotation ID"
    ),
    title: Optional[str] = typer.Option(None, "--title", help="New title"),
    description: Optional[str] = typer.Option(None, "--description", help="New description"),
    color: Optional[str] = typer.Option(None, "--color", help="New color"),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a reporting data annotation."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        body = {}
        mask_fields = []
        if title is not None:
            body["title"] = title
            mask_fields.append("title")
        if description is not None:
            body["description"] = description
            mask_fields.append("description")
        if color is not None:
            body["color"] = color
            mask_fields.append("color")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: --title, --description, --color"
            )

        admin = get_admin_alpha_client()
        resource_name = f"properties/{effective_property}/reportingDataAnnotations/{annotation_id}"
        annotation = (
            admin.properties()
            .reportingDataAnnotations()
            .patch(
                name=resource_name,
                body=body,
                updateMask=",".join(mask_fields),
            )
            .execute()
        )
        output(annotation, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


@annotations_app.command("delete")
def delete_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    annotation_id: str = typer.Option(
        ..., "--annotation-id", "-a", help="Annotation ID"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a reporting data annotation."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if not yes:
            confirmed = questionary.confirm(
                f"Delete annotation {annotation_id}? This cannot be undone."
            ).ask()
            if not confirmed:
                info("Cancelled.")
                raise typer.Exit()

        admin = get_admin_alpha_client()
        resource_name = f"properties/{effective_property}/reportingDataAnnotations/{annotation_id}"
        admin.properties().reportingDataAnnotations().delete(
            name=resource_name
        ).execute()
        success(f"Annotation {annotation_id} deleted.")
    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
