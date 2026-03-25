"""User configuration persistence.

Implements the same pattern as GTM CLI:
- JSON file at ~/.config/ga-cli/config.json
- In-memory cache for performance
- CLI flag > config file > None resolution via get_effective_value()
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal, Optional

from .constants import get_config_dir, get_config_path

OutputFormat = Literal["json", "table", "compact"]


@dataclass
class UserConfig:
    """User configuration. GA-specific fields."""

    default_property_id: Optional[str] = None
    default_account_id: Optional[str] = None
    output_format: OutputFormat = "table"


# In-memory cache (same pattern as GTM CLI)
_cached_config: Optional[UserConfig] = None


def load_config() -> UserConfig:
    """Load config from disk, merge with defaults, cache in memory."""
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    config_path = get_config_path()
    try:
        data = json.loads(config_path.read_text())
        _cached_config = UserConfig(
            default_property_id=data.get("default_property_id"),
            default_account_id=data.get("default_account_id"),
            output_format=data.get("output_format", "table"),
        )
    except (FileNotFoundError, json.JSONDecodeError):
        _cached_config = UserConfig()

    return _cached_config


def save_config(config: UserConfig) -> None:
    """Write config to disk and update cache."""
    global _cached_config
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    # Only write non-None values
    data = {k: v for k, v in asdict(config).items() if v is not None}
    get_config_path().write_text(json.dumps(data, indent=2))
    _cached_config = config


def update_config(**updates: str) -> UserConfig:
    """Merge updates into current config and save."""
    config = load_config()
    for key, value in updates.items():
        if hasattr(config, key):
            setattr(config, key, value)
    save_config(config)
    return config


def get_config_value(key: str) -> Optional[str]:
    """Get a single config value by key name."""
    config = load_config()
    return getattr(config, key, None)


def set_config_value(key: str, value: str) -> None:
    """Set a single config value."""
    update_config(**{key: value})


def unset_config_value(key: str) -> None:
    """Remove a config value (set to None)."""
    config = load_config()
    if hasattr(config, key):
        setattr(config, key, None)
    save_config(config)


def clear_config() -> None:
    """Reset config to defaults."""
    save_config(UserConfig())


def get_effective_value(cli_value: Optional[str], config_key: str) -> Optional[str]:
    """Resolve a value: CLI flag > config file > None.

    This is the critical resolution function used by every command.
    Equivalent to GTM CLI's getEffectiveValue().
    """
    if cli_value:
        return cli_value
    return get_config_value(config_key)


# Valid config keys (for validation in set/unset commands)
VALID_CONFIG_KEYS = {
    "default_property_id": "Default GA4 Property ID",
    "default_account_id": "Default Account ID",
    "output_format": "Output format (json, table, compact)",
}
