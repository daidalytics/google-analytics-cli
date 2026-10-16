"""Named profile management commands.

Both commands work offline: they read or remove files under the config dir
and never build an API client, load credentials, or refresh a token. Each
profile is inspected by reading its own directory directly; the active
profile is never switched to look at another one.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

import questionary
import typer

from ..config.constants import (
    DEFAULT_PROFILE,
    PROFILE_NAME_RE,
    get_active_profile,
    get_config_dir,
    get_profiles_root,
    list_profiles,
    profile_exists,
)
from ..utils import error, info, output, resolve_output_format, success, warn

profiles_app = typer.Typer(
    name="profiles",
    help="Manage named profiles (stored credentials + config)",
    no_args_is_help=True,
)

_NONE_MARK = "—"


def _profile_dir(name: str) -> Path:
    """A profile's directory, computed without activating the profile."""
    if name == DEFAULT_PROFILE:
        return get_config_dir()
    return get_profiles_root() / name


def _read_json_object(path: Path) -> Optional[dict]:
    """Parse a JSON object file. Missing, unreadable, or corrupt files give None."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):  # ValueError covers JSON and Unicode decode errors
        return None
    return data if isinstance(data, dict) else None


def _as_text(value: Any) -> Optional[str]:
    """Keep a stored string (or hand-edited number) for display, drop anything else."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    return str(value) or None


def _describe_profile(name: str, active: str) -> dict:
    """Summarize one profile from its stored files.

    The method mirrors credential resolution for a profile's own files: a
    saved service account wins over a stored OAuth token.
    """
    directory = _profile_dir(name)
    auth = _read_json_object(directory / "auth-method.json") or {}
    config = _read_json_object(directory / "config.json") or {}

    email = None
    if auth.get("method") == "service-account":
        method = "service-account"
        email = _as_text(auth.get("service_account_email"))
    elif _read_json_object(directory / "credentials.json") is not None:
        method = "oauth"
    else:
        method = "none"

    return {
        "name": name,
        "active": name == active,
        "method": method,
        "service_account_email": email,
        "default_property_id": _as_text(config.get("default_property_id")),
        "path": str(directory),
    }


@profiles_app.command("list")
def list_cmd(
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """List profiles and the credentials stored in each (offline).

    Shows only stored credentials: those saved by 'ga auth login'. For the
    default profile, env-var credentials (GA_CLI_SERVICE_ACCOUNT,
    GOOGLE_APPLICATION_CREDENTIALS) and gcloud ADC can still apply at
    runtime; 'ga auth status' shows the effective method. Makes no API calls.
    """
    effective_format = resolve_output_format(output_format)
    active = get_active_profile()
    profiles = [_describe_profile(name, active) for name in list_profiles()]

    if not any(profile["active"] for profile in profiles):
        warn(
            f"Active profile '{active}' does not exist yet. "
            f"Create it with: ga --profile {active} auth login"
        )

    if effective_format == "table":
        rows = [
            {
                "active": "*" if profile["active"] else "",
                "name": profile["name"],
                "method": profile["method"],
                "identity": profile["service_account_email"] or _NONE_MARK,
                "default_property_id": profile["default_property_id"] or _NONE_MARK,
            }
            for profile in profiles
        ]
        output(
            rows,
            effective_format,
            columns=["active", "name", "method", "identity", "default_property_id"],
            headers=["Active", "Name", "Method", "Identity", "Default Property"],
        )
    else:
        output(profiles, effective_format)


def _key_inside(profile_dir: Path) -> Optional[Path]:
    """The profile's SA key path if it lies inside ``profile_dir``, else None."""
    auth = _read_json_object(profile_dir / "auth-method.json") or {}
    key_path = auth.get("service_account_path")
    if not isinstance(key_path, str) or not key_path:
        return None
    key = Path(key_path).expanduser().resolve()
    if key.is_relative_to(profile_dir.resolve()):
        return key
    return None


@profiles_app.command("delete")
def delete_cmd(
    name: str = typer.Argument(help="Name of the profile to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a named profile's stored credentials and config.

    Removes profiles/NAME/. The service account key file the profile points
    to is never deleted. The default profile cannot be deleted.
    """
    if name == DEFAULT_PROFILE:
        error(
            "The default profile cannot be deleted. To clear it, use "
            "'ga auth logout' (credentials) or 'ga config reset' (config)."
        )
        raise typer.Exit(1)

    if not PROFILE_NAME_RE.fullmatch(name):
        error(
            f"Invalid profile name {name!r}: use letters, digits, '.', '_' or '-', "
            "starting with a letter or digit."
        )
        raise typer.Exit(1)

    if not profile_exists(name):
        error(
            f"Profile '{name}' does not exist. "
            f"Known profiles: {', '.join(list_profiles())}."
        )
        raise typer.Exit(1)

    profile_dir = _profile_dir(name)

    key = _key_inside(profile_dir)
    if key is not None:
        error(
            f"Profile '{name}' uses a service account key stored inside its own "
            f"directory: {key}. Deleting the profile would delete the key, so "
            "nothing was removed. Move the key out of the profile directory, then "
            f"run 'ga --profile {name} auth login --service-account <new path>' "
            "before deleting."
        )
        raise typer.Exit(1)

    if not yes:
        confirmed = questionary.confirm(
            f"Delete profile '{name}' ({profile_dir})? "
            "Its stored credentials and config will be removed."
        ).ask()
        if not confirmed:
            info("Cancelled.")
            raise typer.Exit()

    try:
        shutil.rmtree(profile_dir)
    except OSError as exc:
        error(f"Failed to delete profile '{name}': {exc}")
        raise typer.Exit(1)

    success(f"Profile '{name}' deleted.")
