"""Reporting data annotation management commands."""

import datetime
from typing import Optional

import questionary
import typer

from ..api.client import get_admin_alpha_client
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
    color: str = typer.Option(
        "BLUE",
        "--color",
        help="Annotation color (PURPLE, BROWN, BLUE, GREEN, RED, CYAN)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create a reporting data annotation."""
    valid_colors = {"PURPLE", "BROWN", "BLUE", "GREEN", "RED", "CYAN"}
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        try:
            d = datetime.date.fromisoformat(annotation_date)
        except ValueError:
            raise typer.BadParameter(
                f"Invalid date '{annotation_date}'. Use YYYY-MM-DD format."
            )

        if len(description) > 150:
            raise typer.BadParameter(
                "Description must be 150 characters or fewer."
            )

        color_upper = color.upper()
        if color_upper not in valid_colors:
            raise typer.BadParameter(
                f"Invalid color '{color}'. Must be one of: {', '.join(sorted(valid_colors))}"
            )

        body = {
            "title": title,
            "annotationDate": {"year": d.year, "month": d.month, "day": d.day},
            "description": description,
            "color": color_upper,
        }

        if dry_run:
            handle_dry_run("create", "POST", f"properties/{effective_property}", body)

        admin = get_admin_alpha_client()
        annotation = (
            admin.properties()
            .reportingDataAnnotations()
            .create(parent=f"properties/{effective_property}", body=body)
            .execute()
        )
        output(annotation, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
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
    color: Optional[str] = typer.Option(
        None, "--color", help="New color (PURPLE, BROWN, BLUE, GREEN, RED, CYAN)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Update a reporting data annotation."""
    valid_colors = {"PURPLE", "BROWN", "BLUE", "GREEN", "RED", "CYAN"}
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
            if len(description) > 150:
                raise typer.BadParameter(
                    "Description must be 150 characters or fewer."
                )
            body["description"] = description
            mask_fields.append("description")
        if color is not None:
            color_upper = color.upper()
            if color_upper not in valid_colors:
                raise typer.BadParameter(
                    f"Invalid color '{color}'. Must be one of: {', '.join(sorted(valid_colors))}"
                )
            body["color"] = color_upper
            mask_fields.append("color")

        if not mask_fields:
            raise typer.BadParameter(
                "At least one field must be specified: --title, --description, --color"
            )

        resource_name = f"properties/{effective_property}/reportingDataAnnotations/{annotation_id}"
        if dry_run:
            handle_dry_run(
                "update", "PATCH", resource_name,
                body, update_mask=",".join(mask_fields),
            )

        admin = get_admin_alpha_client()
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
    except (typer.BadParameter, typer.Exit):
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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
):
    """Delete a reporting data annotation."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])

        if dry_run:
            handle_dry_run(
                "delete", "DELETE",
                f"properties/{effective_property}/reportingDataAnnotations/{annotation_id}",
                None,
            )

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
