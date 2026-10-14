"""Audience export commands (Data API v1beta ``properties.audienceExports``)."""

import re
import time
from typing import Any, Optional

import typer

from ..api.client import get_data_client
from ..config.store import get_effective_value
from ..utils import (
    format_api_error,
    handle_dry_run,
    handle_error,
    info,
    output,
    require_options,
    resolve_output_format,
    warn,
)
from ..utils.pagination import paginate_all

audience_exports_app = typer.Typer(
    name="audience-exports",
    help="Create, list, and query audience exports (snapshots of audience users)",
    no_args_is_help=True,
)

_EXPORT_NAME_RE = re.compile(r"^properties/[^/]+/audienceExports/([^/]+)$")
_AUDIENCE_NAME_RE = re.compile(r"^properties/[^/]+/audiences/[^/]+$")

_POLL_INITIAL_SECONDS = 10
_POLL_MAX_SECONDS = 60


class AudienceExportError(Exception):
    """An export is not usable (still CREATING, FAILED, or never became ACTIVE).

    Deliberately a plain Exception: ``classify_error`` maps it to exit 3 /
    ``api_error`` and ``handle_error`` prints ``str(err)`` (or structured JSON).
    """


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


def _not_active_message(export: dict) -> str:
    """Explain why a non-ACTIVE export can't be used yet."""
    export_id = _export_id(export.get("name", ""))
    state = export.get("state")
    if state == "FAILED":
        detail = export.get("errorMessage") or "no error message returned"
        return f"export {export_id} FAILED: {detail}"
    percent = _format_percent(export.get("percentageCompleted"))
    progress = f" ({percent})" if percent else ""
    if state == "CREATING":
        return f"export {export_id} is still CREATING{progress} — try again later"
    return f"export {export_id} is {state}, not ACTIVE{progress} — try again later"


def _raise_if_not_active(data, name: str, err: Exception) -> None:
    """After a failed ``query``, raise a friendly error if the export isn't ACTIVE.

    Only 4xx responses are checked. Returns quietly (so the caller re-raises the
    original error) when the export is ACTIVE, has no state, or can't be read.
    """
    from googleapiclient.errors import HttpError

    if not isinstance(err, HttpError) or not 400 <= err.resp.status < 500:
        return
    try:
        export = data.properties().audienceExports().get(name=name).execute()
    except Exception:
        return
    state = export.get("state")
    if state and state != "ACTIVE":
        raise AudienceExportError(_not_active_message({**export, "name": name})) from err


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


def _query_table(response: dict) -> tuple[list[dict], list[str]]:
    """Turn a QueryAudienceExportResponse into rows keyed by dimension name."""
    dimensions = (response.get("audienceExport") or {}).get("dimensions") or []
    columns = [d.get("dimensionName") or f"dimension{i + 1}" for i, d in enumerate(dimensions)]
    rows = []
    for audience_row in response.get("audienceRows") or []:
        values = [v.get("value", "") for v in audience_row.get("dimensionValues") or []]
        rows.append(dict(zip(columns, values)))
    return rows, columns


@audience_exports_app.command("query")
def query_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    export_id: str = typer.Option(
        ..., "--export-id", help="Audience export ID (numeric)"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", min=1,
        help="Rows to return (API default 10,000; at most 250,000 per request)",
    ),
    offset: Optional[int] = typer.Option(
        None, "--offset", min=0, help="Index of the first row to return (0-based)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Query the users in an ACTIVE audience export."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        # limit/offset are int64 in the API, which JSON-encodes them as strings.
        body: dict = {}
        if limit is not None:
            body["limit"] = str(limit)
        if offset is not None:
            body["offset"] = str(offset)

        name = _export_resource(effective_property, export_id)
        data = get_data_client()
        try:
            response = (
                data.properties().audienceExports().query(name=name, body=body).execute()
            )
        except Exception as err:
            _raise_if_not_active(data, name, err)
            raise

        if effective_format != "table":
            output(response, effective_format)
            return

        rows, columns = _query_table(response)
        output(rows, effective_format, columns=columns, headers=columns)

        total = response.get("rowCount")
        start = offset or 0
        if rows and isinstance(total, int) and start + len(rows) < total:
            info(
                f"Showing rows {start + 1}–{start + len(rows)} of {total}. "
                f"Use --offset {start + len(rows)} for the next page."
            )
    except Exception as e:
        handle_error(e)


def _audience_resource(property_id: str, audience_id: str) -> str:
    """Accept a numeric audience ID or a full ``properties/P/audiences/A`` name."""
    value = audience_id.strip()
    if value.isdigit():
        return f"properties/{property_id}/audiences/{value}"
    if _AUDIENCE_NAME_RE.match(value):
        return value
    raise typer.BadParameter(
        f"--audience-id must be a numeric audience ID or a full name like "
        f"properties/{property_id}/audiences/456 (got '{audience_id}')"
    )


def _parse_dimensions(raw: str) -> list[str]:
    names = [d.strip() for d in raw.split(",") if d.strip()]
    if not names:
        raise typer.BadParameter("--dimensions needs at least one dimension name, e.g. deviceId")
    return names


def _find_export_name(value: Any) -> Optional[str]:
    """Depth-first search for a ``properties/*/audienceExports/*`` string."""
    if isinstance(value, str):
        return value if _EXPORT_NAME_RE.match(value) else None
    if isinstance(value, dict):
        children = list(value.values())
    elif isinstance(value, list):
        children = value
    else:
        return None
    for child in children:
        found = _find_export_name(child)
        if found:
            return found
    return None


def _export_name_from_operation(operation: dict) -> Optional[str]:
    """Read the new export's name from the create Operation, if it carries one.

    The Data API guide shows it in ``response.name``; ``metadata`` is a second
    guess because the Operation's shape isn't pinned down (SPEC Open Question 3).
    """
    response = operation.get("response")
    if isinstance(response, dict):
        name = response.get("name")
        if isinstance(name, str) and _EXPORT_NAME_RE.match(name):
            return name
    return _find_export_name(operation.get("metadata"))


def _creation_sort_key(export: dict) -> tuple[str, str]:
    """Order Z-normalized RFC 3339 times that carry 0, 3, 6 or 9 fractional digits.

    A plain string compare puts ``…:00Z`` after ``…:00.5Z`` ('Z' > '.'), so the
    fraction is compared separately, right-padded to nanoseconds.
    """
    seconds, _, fraction = (export.get("beginCreatingTime") or "").rstrip("Z").partition(".")
    return seconds, fraction.ljust(9, "0")


def _newest_export_for_audience(data, property_id: str, audience: str) -> Optional[str]:
    exports = paginate_all(
        lambda **kw: data.properties()
        .audienceExports()
        .list(parent=f"properties/{property_id}", **kw)
        .execute(),
        "audienceExports",
        pageSize=1000,
    )
    matches = [e for e in exports if e.get("audience") == audience and e.get("name")]
    if not matches:
        return None
    return max(matches, key=_creation_sort_key)["name"]


def _resolve_export_name(
    data, property_id: str, operation: dict, audience: str
) -> Optional[str]:
    """Find the new export's name: Operation response, then metadata, then ``list``.

    The export already exists at this point, so a failing ``list`` only warns:
    exiting non-zero would invite a retry that charges quota tokens again.
    """
    name = _export_name_from_operation(operation)
    if name:
        return name
    try:
        name = _newest_export_for_audience(data, property_id, audience)
    except Exception as err:
        warn(f"Could not list exports to find the new export's name: {format_api_error(err)}")
        return None
    if name:
        info(f"Export name not in the create response; using the newest export for {audience}.")
    return name


def _wait_for_export(data, property_id: str, name: str, timeout: int) -> dict:
    """Poll ``get`` until ACTIVE (returned), FAILED or timeout (both raise)."""
    export_id = _export_id(name)
    deadline = time.monotonic() + timeout
    interval = _POLL_INITIAL_SECONDS
    while True:
        export = data.properties().audienceExports().get(name=name).execute()
        state = export.get("state") or "STATE_UNSPECIFIED"
        if state == "ACTIVE":
            return export
        if state == "FAILED":
            raise AudienceExportError(_not_active_message({**export, "name": name}))

        percent = _format_percent(export.get("percentageCompleted"))
        info(f"Export {export_id}: {state}" + (f" ({percent})" if percent else ""))

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AudienceExportError(
                f"export {export_id} is still {state} after {timeout}s — check later with "
                f"`ga audience-exports get -p {property_id} --export-id {export_id}`"
            )
        time.sleep(min(interval, remaining))
        interval = min(interval * 2, _POLL_MAX_SECONDS)


@audience_exports_app.command("create")
def create_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    audience_id: str = typer.Option(
        ..., "--audience-id",
        help="Audience ID (numeric) or full name properties/P/audiences/A",
    ),
    dimensions: str = typer.Option(
        ..., "--dimensions",
        help="Comma-separated dimensions to export, e.g. deviceId,userId",
    ),
    wait: bool = typer.Option(
        False, "--wait",
        help="Poll until the export is ACTIVE or FAILED (exports often take ~15 min)",
    ),
    timeout: int = typer.Option(
        1800, "--timeout", min=1, help="Seconds --wait polls before giving up"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the request without executing"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Create an audience export (charges quota tokens; completes asynchronously)."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        parent = f"properties/{effective_property}"
        body = {
            "audience": _audience_resource(effective_property, audience_id),
            "dimensions": [{"dimensionName": d} for d in _parse_dimensions(dimensions)],
        }
        if dry_run:
            handle_dry_run(
                action="create",
                method="POST",
                resource_path=f"{parent}/audienceExports",
                body=body,
            )

        data = get_data_client()
        operation = (
            data.properties().audienceExports().create(parent=parent, body=body).execute()
        )
        export_name = _resolve_export_name(
            data, effective_property, operation, body["audience"]
        )
        list_hint = f"`ga audience-exports list -p {effective_property}`"

        if not wait:
            if not export_name:
                warn(f"Could not determine the new export's name; find it with {list_hint}.")
            output(
                {
                    "exportName": export_name,
                    "exportId": _export_id(export_name) if export_name else None,
                    "operation": operation,
                },
                effective_format,
            )
            return

        if not export_name:
            raise AudienceExportError(
                f"export was created (operation {operation.get('name', 'unknown')}) but its "
                f"name could not be determined, so --wait cannot poll it; find it with "
                f"{list_hint}"
            )
        info(f"Created export {_export_id(export_name)}; waiting up to {timeout}s for ACTIVE.")
        export = _wait_for_export(data, effective_property, export_name, timeout)
        output(export, effective_format)
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as e:
        handle_error(e)
