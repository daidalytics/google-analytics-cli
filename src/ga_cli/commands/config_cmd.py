"""Configuration management commands.

Equivalent to GTM CLI's commands/config.ts.
"""

from typing import Optional

import typer

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
from ..utils import error, info, output, success

config_app = typer.Typer(name="config", help="Manage CLI configuration", no_args_is_help=True)


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

    output_format = questionary.select(
        "Default output format:",
        choices=["table", "json", "compact"],
        default="table",
    ).ask()

    config = UserConfig(
        default_account_id=account_id or None,
        default_property_id=property_id or None,
        output_format=output_format or "table",
    )
    save_config(config)
    success("Configuration saved.")


@config_app.command("get")
def get_cmd(key: Optional[str] = typer.Argument(None, help="Config key to retrieve")):
    """Get configuration values."""
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
    unset_config_value(key)
    success(f"Unset {key}")


@config_app.command("path")
def path():
    """Show configuration file path."""
    print(get_config_path())


@config_app.command("reset")
def reset():
    """Reset all configuration to defaults."""
    import questionary
    if questionary.confirm("Reset all configuration to defaults?", default=False).ask():
        clear_config()
        success("Configuration reset.")
    else:
        info("Reset cancelled.")
