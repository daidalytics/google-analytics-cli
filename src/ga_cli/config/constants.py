"""Application constants and configuration paths."""

import os
from pathlib import Path

from platformdirs import user_config_dir

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

# OAuth client credentials
# For development: set env vars. For production: embed at build time.
GOOGLE_CLIENT_ID = os.environ.get("GA_CLI_CLIENT_ID", "__OAUTH_CLIENT_ID__")
GOOGLE_CLIENT_SECRET = os.environ.get("GA_CLI_CLIENT_SECRET", "__OAUTH_CLIENT_SECRET__")


# Configuration directory
# Priority: GA_CLI_CONFIG_DIR env var > platformdirs (XDG-compliant)
def get_config_dir() -> Path:
    """Get the configuration directory path."""
    env_dir = os.environ.get("GA_CLI_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(user_config_dir(APP_NAME))  # ~/.config/ga-cli/ on Linux/macOS


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
