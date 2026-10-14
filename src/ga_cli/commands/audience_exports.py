"""Audience export commands (Data API v1beta ``properties.audienceExports``)."""

import re
from typing import Optional

import typer

from ..api.client import get_data_client
from ..config.store import get_effective_value
from ..utils import handle_error, output, require_options, resolve_output_format
from ..utils.pagination import paginate_all

audience_exports_app = typer.Typer(
    name="audience-exports",
    help="Create, list, and query audience exports (snapshots of audience users)",
    no_args_is_help=True,
)

_EXPORT_NAME_RE = re.compile(r"^properties/[^/]+/audienceExports/([^/]+)$")


def _export_id(name: str) -> str:
    """Return the trailing ID of ``properties/P/audienceExports/E``, else ``name`` unchanged."""
    match = _EXPORT_NAME_RE.match(name or "")
    return match.group(1) if match else name


def _export_resource(property_id: str, export_id: str) -> str:
    return f"properties/{property_id}/audienceExports/{export_id}"


def _format_percent(value) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):g}%"
    except (TypeError, ValueError):
        return str(value)


def _format_time(value: Optional[str]) -> str:
    """Shorten an RFC 3339 timestamp (API output is Z-normalized) to ``YYYY-MM-DD HH:MM:SS``."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})", value or "")
    return f"{match.group(1)} {match.group(2)}" if match else (value or "")


def _summary_row(export: dict) -> dict:
    """Flatten an AudienceExport into the columns shown by ``list``."""
    return {
        "exportId": _export_id(export.get("name", "")),
        "audience": export.get("audienceDisplayName") or export.get("audience", ""),
        "state": export.get("state", ""),
        "rowCount": export.get("rowCount"),
        "percentageCompleted": _format_percent(export.get("percentageCompleted")),
        "beginCreatingTime": _format_time(export.get("beginCreatingTime")),
    }


@audience_exports_app.command("list")
def list_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List audience exports for a property."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        data = get_data_client()
        exports = paginate_all(
            lambda **kw: data.properties()
            .audienceExports()
            .list(parent=f"properties/{effective_property}", **kw)
            .execute(),
            "audienceExports",
            pageSize=1000,
        )

        if effective_format != "table":
            output(exports, effective_format)
            return

        output(
            [_summary_row(e) for e in exports],
            effective_format,
            columns=[
                "exportId",
                "audience",
                "state",
                "rowCount",
                "percentageCompleted",
                "beginCreatingTime",
            ],
            headers=["Export ID", "Audience", "State", "Rows", "% Complete", "Created (UTC)"],
        )
    except Exception as e:
        handle_error(e)


@audience_exports_app.command("get")
def get_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    export_id: str = typer.Option(
        ..., "--export-id", help="Audience export ID (numeric)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get an audience export's state and configuration."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        data = get_data_client()
        export = (
            data.properties()
            .audienceExports()
            .get(name=_export_resource(effective_property, export_id))
            .execute()
        )
        output(export, effective_format)
    except Exception as e:
        handle_error(e)
