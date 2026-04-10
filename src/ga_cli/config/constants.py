"""Application constants and configuration paths."""

import os
import shutil
from pathlib import Path

# App identity
APP_NAME = "ga-cli"

# OAuth 2.0 scopes
OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
    "https://www.googleapis.com/auth/analytics.manage.users",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# OAuth callback server
OAUTH_CALLBACK_PORT = 8085

# Track whether we've already attempted the legacy macOS migration this process.
_legacy_migration_attempted = False


def _migrate_legacy_macos_config(new_dir: Path) -> None:
    """Move config from the legacy macOS path to the new XDG-style path.

    Versions <=0.2.1 used ``platformdirs``, which on macOS resolves to
    ``~/Library/Application Support/ga-cli/``. We now standardize on
    ``~/.config/ga-cli/`` across all platforms. If the legacy directory exists
    and the new one doesn't, move it. Runs at most once per process.
    """
    global _legacy_migration_attempted
    if _legacy_migration_attempted:
        return
    _legacy_migration_attempted = True

    legacy_dir = Path.home() / "Library" / "Application Support" / APP_NAME
    if legacy_dir.is_dir() and not new_dir.exists():
        try:
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_dir), str(new_dir))
        except OSError:
            # Migration is best-effort; fall through and let callers create
            # the new directory themselves if needed.
            pass


# Configuration directory
# Priority: GA_CLI_CONFIG_DIR env var > ~/.config/ga-cli/ (all platforms)
def get_config_dir() -> Path:
    """Get the configuration directory path.

    Resolution order:
      1. ``GA_CLI_CONFIG_DIR`` environment variable (used in tests too).
      2. ``~/.config/ga-cli/`` on all platforms.
    """
    env_dir = os.environ.get("GA_CLI_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    config_dir = Path.home() / ".config" / APP_NAME
    _migrate_legacy_macos_config(config_dir)
    return config_dir


def get_credentials_path() -> Path:
    """Path to stored OAuth credentials."""
    return get_config_dir() / "credentials.json"


def get_config_path() -> Path:
    """Path to user configuration file."""
    return get_config_dir() / "config.json"


def get_auth_method_path() -> Path:
    """Path to auth method tracking file."""
    return get_config_dir() / "auth-method.json"


def get_client_secret_path() -> Path:
    """Path to OAuth client secret file (alternative to env vars)."""
    return get_config_dir() / "client_secret.json"


def get_update_check_path() -> Path:
    """Path to update-check timestamp file."""
    return get_config_dir() / "update-check.json"


# Pagination defaults
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
