"""Configuration management commands.

Equivalent to GTM CLI's commands/config.ts.
"""

import sys
from typing import Optional

import typer

from ..config.allowlist import parse_ids
from ..config.constants import get_active_profile, is_named_profile, profile_exists
from ..config.store import (
    ALLOWLIST_CONFIG_KEYS,
    VALID_CONFIG_KEYS,
    ConfigFileError,
    clear_config,
    get_config_path,
    get_config_value,
    load_config,
    require_writable_config,
    set_config_value,
    unset_config_value,
    update_config,
)
from ..utils import error, handle_error, info, output, success
from ..utils.errors import AllowlistError, ProfileNotFoundError

config_app = typer.Typer(name="config", help="Manage CLI configuration", no_args_is_help=True)


def _require_existing_profile() -> None:
    """Exit 2 if the active named profile doesn't exist.

    Only `set` and `setup` create a profile. A typo in --profile must not read
    as an empty config, or be created by `unset`/`reset`.
    """
    profile = get_active_profile()
    if not profile_exists(profile):
        handle_error(ProfileNotFoundError.for_profile(profile))


def _stdin_is_tty() -> bool:
    return sys.stdin.isatty()


def _format_ids(ids: object) -> str:
    """An allowlist value for display; also copes with a hand-edited one (numbers, a string)."""
    if ids is None:
        return "(not set)"
    if not isinstance(ids, list):
        return str(ids)
    return ", ".join(map(str, ids)) if ids else "(empty: denies everything)"


def _require_interactive() -> None:
    """Exit 1 without a terminal, so an agent can't change its own allowlist."""
    if not _stdin_is_tty():
        error("Allowlist settings can only be changed interactively")
        raise typer.Exit(1)


def _require_readable_config() -> None:
    """Exit 1 before any prompt, rather than reach save_config's refusal afterwards."""
    try:
        require_writable_config()
    except ConfigFileError as e:
        error(str(e))
        raise typer.Exit(1)


def _allowlist_scope() -> str:
    """Which profiles the active config.json's allowlist keys apply to."""
    if is_named_profile():
        return f"profile {get_active_profile()}, narrows the global allowlist"
    return "all profiles"


def _confirm_allowlist_change(changes: dict[str, tuple]) -> bool:
    """Show old → new and ask; False if the user declines. Terminal only."""
    _require_interactive()
    import questionary

    scope = _allowlist_scope()
    for key, (old, new) in changes.items():
        info(f"{key} ({scope}): {_format_ids(old)} → {_format_ids(new)}")
    return bool(questionary.confirm("Change the allowlist?", default=False).ask())


@config_app.command("setup")
def setup():
    """Interactive configuration wizard."""
    import questionary

    _require_readable_config()
    info("GA CLI Configuration Setup")
    print()

    account_id = questionary.text(
        "Default Account ID (leave empty to skip):"
    ).ask()

    property_id = questionary.text(
        "Default Property ID (leave empty to skip):"
    ).ask()

    # "auto" leaves output_format unset: table in a terminal, JSON when piped
    output_format = questionary.select(
        "Default output format:",
        choices=["auto", "table", "json", "compact"],
        default="auto",
    ).ask()

    # Only the wizard's own keys change; the allowlist and anything else stay as they are
    update_config(
        default_account_id=account_id or None,
        default_property_id=property_id or None,
        output_format=None if output_format in (None, "auto") else output_format,
    )
    success("Configuration saved.")


@config_app.command("get")
def get_cmd(key: Optional[str] = typer.Argument(None, help="Config key to retrieve")):
    """Get configuration values."""
    _require_existing_profile()
    if key:
        if key not in VALID_CONFIG_KEYS:
            error(f"Unknown config key: {key}. Valid keys: {', '.join(VALID_CONFIG_KEYS)}")
            raise typer.Exit(1)
        value = get_config_value(key)
        if isinstance(value, list):
            print(",".join(map(str, value)))
        elif value is not None:
            print(value)
        else:
            error(f"Config key '{key}' is not set.")
            raise typer.Exit(1)
    else:
        from dataclasses import asdict
        config = load_config()
        output(asdict(config), "json")


@config_app.command("set")
def set_cmd(
    key: str = typer.Argument(help="Config key"),
    value: str = typer.Argument(help="Config value"),
):
    """Set a configuration value."""
    if key not in VALID_CONFIG_KEYS:
        error(f"Unknown config key: {key}. Valid keys: {', '.join(VALID_CONFIG_KEYS)}")
        raise typer.Exit(1)
    _require_readable_config()
    if key in ALLOWLIST_CONFIG_KEYS:
        _set_allowlist_key(key, value)
        return
    set_config_value(key, value)
    success(f"Set {key} = {value}")


def _set_allowlist_key(key: str, value: str) -> None:
    kind = "accounts" if key == "allowed_account_ids" else "properties"
    _require_interactive()
    try:
        ids = sorted(parse_ids(value, kind, key), key=int)
    except AllowlistError as e:
        error(e.reason)
        raise typer.Exit(1)
    if not _confirm_allowlist_change({key: (get_config_value(key), ids)}):
        info("Allowlist unchanged.")
        return
    set_config_value(key, ids)
    success(f"Set {key} = {_format_ids(ids)}")


@config_app.command("unset")
def unset(key: str = typer.Argument(help="Config key to remove")):
    """Remove a configuration value."""
    if key not in VALID_CONFIG_KEYS:
        error(f"Unknown config key: {key}. Valid keys: {', '.join(VALID_CONFIG_KEYS)}")
        raise typer.Exit(1)
    _require_existing_profile()
    _require_readable_config()
    # Unsetting a key that isn't set changes nothing, so it needs no terminal
    if key in ALLOWLIST_CONFIG_KEYS and get_config_value(key) is not None:
        if not _confirm_allowlist_change({key: (get_config_value(key), None)}):
            info("Allowlist unchanged.")
            return
    unset_config_value(key)
    success(f"Unset {key}")


@config_app.command("path")
def path():
    """Show the active profile's configuration file path.

    The default profile's file sits in the config root; a named profile's in
    profiles/NAME/. Printing it does not create the profile.
    """
    print(get_config_path())


@config_app.command("reset")
def reset():
    """Reset all configuration to defaults."""
    import questionary
    _require_existing_profile()
    _require_readable_config()
    config = load_config()
    allowlist = {
        key: (getattr(config, key), None)
        for key in ALLOWLIST_CONFIG_KEYS
        if getattr(config, key) is not None
    }
    if allowlist and not _confirm_allowlist_change(allowlist):
        info("Reset cancelled.")
        return
    if questionary.confirm("Reset all configuration to defaults?", default=False).ask():
        clear_config()
        success("Configuration reset.")
    else:
        info("Reset cancelled.")
