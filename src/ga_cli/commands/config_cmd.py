"""Configuration management commands.

Equivalent to GTM CLI's commands/config.ts.
"""

from typing import Optional

import typer

from ..config.constants import get_active_profile, profile_exists
from ..config.store import (
    VALID_CONFIG_KEYS,
    UserConfig,
    clear_config,
    get_config_path,
    get_config_value,
    load_config,
    save_config,
    set_config_value,
    unset_config_value,
)
from ..utils import error, handle_error, info, output, success
from ..utils.errors import ProfileNotFoundError

config_app = typer.Typer(name="config", help="Manage CLI configuration", no_args_is_help=True)


def _require_existing_profile() -> None:
    """Exit 2 if the active named profile doesn't exist.

    Only `set` and `setup` create a profile. A typo in --profile must not read
    as an empty config, or be created by `unset`/`reset`.
    """
    profile = get_active_profile()
    if not profile_exists(profile):
        handle_error(ProfileNotFoundError.for_profile(profile))


@config_app.command("setup")
def setup():
    """Interactive configuration wizard."""
    import questionary

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

    config = UserConfig(
        default_account_id=account_id or None,
        default_property_id=property_id or None,
        output_format=None if output_format in (None, "auto") else output_format,
    )
    save_config(config)
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
        if value is not None:
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
    set_config_value(key, value)
    success(f"Set {key} = {value}")


@config_app.command("unset")
def unset(key: str = typer.Argument(help="Config key to remove")):
    """Remove a configuration value."""
    if key not in VALID_CONFIG_KEYS:
        error(f"Unknown config key: {key}. Valid keys: {', '.join(VALID_CONFIG_KEYS)}")
        raise typer.Exit(1)
    _require_existing_profile()
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
    if questionary.confirm("Reset all configuration to defaults?", default=False).ask():
        clear_config()
        success("Configuration reset.")
    else:
        info("Reset cancelled.")
