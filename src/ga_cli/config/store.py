"""User configuration persistence.

Implements the same pattern as GTM CLI:
- JSON file at ~/.config/ga-cli/config.json (the default profile), or
  ~/.config/ga-cli/profiles/<name>/config.json for a named profile
- In-memory cache for performance, keyed by the file it was read from
- CLI flag > config file > None resolution via get_effective_value()
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from .constants import get_config_dir, get_config_path

OutputFormat = Literal["json", "table", "compact"]


@dataclass
class UserConfig:
    """User configuration. GA-specific fields."""

    default_property_id: Optional[str] = None
    default_account_id: Optional[str] = None
    # None = not configured: table in a terminal, JSON when piped
    output_format: Optional[OutputFormat] = None
    # Allowlist (config/allowlist.py). None = not set; [] = set but empty (denies all)
    allowed_account_ids: Optional[list[str]] = None
    allowed_property_ids: Optional[list[str]] = None


class ConfigFileError(Exception):
    """config.json exists but couldn't be read, so it won't be overwritten."""


# In-memory cache (same pattern as GTM CLI), keyed by the file each entry came
# from: the allowlist reads the root config.json next to a named profile's, and
# switching profiles can never serve another profile's config. Each entry holds
# the config and why the file couldn't be read (None when it was read or doesn't
# exist).
_cache: dict[Path, tuple[UserConfig, Optional[str]]] = {}


def reset_cache() -> None:
    """Forget everything cached in memory (tests, and anything that edits the file directly)."""
    _cache.clear()


def get_root_config_path() -> Path:
    """The config root's config.json: the default profile's, and the global allowlist's."""
    return get_config_dir() / "config.json"


def load_config_at(path: Path) -> UserConfig:
    """Load the config.json at ``path``, merged with defaults and cached in memory.

    An unreadable file also loads as the defaults, so commands that only use defaults
    keep working, but config_error(path) reports it: the allowlist fails closed on it
    and save_config won't overwrite it.
    """
    cached = _cache.get(path)
    if cached is not None:
        return cached[0]

    reason = None
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        config = UserConfig(
            default_property_id=data.get("default_property_id"),
            default_account_id=data.get("default_account_id"),
            output_format=data.get("output_format"),
            allowed_account_ids=data.get("allowed_account_ids"),
            allowed_property_ids=data.get("allowed_property_ids"),
        )
    except FileNotFoundError:
        config = UserConfig()
    except (OSError, ValueError) as e:  # includes JSONDecodeError and UnicodeDecodeError
        reason = f"Can't read {path} ({e})"
        config = UserConfig()

    _cache[path] = (config, reason)
    return config


def load_config() -> UserConfig:
    """Load the active profile's config.json (see load_config_at)."""
    return load_config_at(get_config_path())


def config_error(path: Optional[Path] = None) -> Optional[str]:
    """Why a config.json couldn't be read, or None if it was read or doesn't exist.

    ``path`` defaults to the active profile's config.json.
    """
    path = get_config_path() if path is None else path
    load_config_at(path)
    return _cache[path][1]


def save_config(config: UserConfig) -> None:
    """Write config to disk atomically and update cache.

    Creates the active profile's directory on first write. Raises ConfigFileError
    instead of overwriting a config.json that couldn't be read, which would silently
    drop any allowlist in it.
    """
    config_path = get_config_path()
    reason = config_error(config_path)
    if reason:
        raise ConfigFileError(reason)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Only write non-None values
    data = {k: v for k, v in asdict(config).items() if v is not None}
    # Temp file + rename, so a crash can't leave a truncated file. resolve() writes
    # through a symlinked config.json instead of replacing the link.
    path = config_path.resolve()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data, indent=2))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    _cache[config_path] = (config, None)


def update_config(**updates: object) -> UserConfig:
    """Merge updates into current config and save."""
    config = load_config()
    for key, value in updates.items():
        if hasattr(config, key):
            setattr(config, key, value)
    save_config(config)
    return config


def get_config_value(key: str) -> Any:
    """Get a single config value by key name (a list for the allowlist keys)."""
    config = load_config()
    return getattr(config, key, None)


def set_config_value(key: str, value: object) -> None:
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
    "output_format": "Output format (json, table, compact); table applies only in a terminal",
    "allowed_account_ids": "Allowlisted account IDs, comma-separated (interactive only)",
    "allowed_property_ids": "Allowlisted property IDs, comma-separated (interactive only)",
}

# Keys that can only be changed from an interactive terminal
ALLOWLIST_CONFIG_KEYS = ("allowed_account_ids", "allowed_property_ids")
