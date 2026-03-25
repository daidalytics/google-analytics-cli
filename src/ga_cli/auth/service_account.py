"""Service account authentication.

Supports:
1. GA_CLI_SERVICE_ACCOUNT env var (path to key file)
2. GOOGLE_APPLICATION_CREDENTIALS env var (standard Google convention)
3. Saved auth method from a previous ``ga auth login --service-account`` call

Equivalent to GTM CLI's auth/service-account.ts.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from ..config.constants import OAUTH_SCOPES, get_auth_method_path, get_config_dir

logger = logging.getLogger(__name__)


def validate_service_account_key(key_path: str) -> dict:
    """Validate a service account key file.

    Checks that the JSON is valid and contains required fields.
    Returns the parsed key data.

    Raises:
        FileNotFoundError: If the key file does not exist.
        ValueError: If the file is not valid service account JSON.
    """
    path = Path(key_path)

    if not path.exists():
        raise FileNotFoundError(f"Service account key file not found: {key_path}")

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in service account key file: {key_path}"
        ) from exc

    if data.get("type") != "service_account":
        raise ValueError(
            f"Invalid key file: expected type 'service_account', "
            f"got '{data.get('type', '<missing>')}'"
        )

    missing = [f for f in ("private_key", "client_email") if not data.get(f)]
    if missing:
        raise ValueError(
            f"Invalid key file: missing required fields: {', '.join(missing)}"
        )

    return data


def login_with_service_account(key_path: str) -> str:
    """Login with a service account key file.

    Validates the key, tests authentication, and saves the auth method.
    Returns the service account email.

    Raises:
        FileNotFoundError: If the key file does not exist.
        ValueError: If the key file is invalid.
        google.auth.exceptions.RefreshError: If authentication fails.
    """
    key_data = validate_service_account_key(key_path)

    # Test that we can actually get a token
    creds = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=OAUTH_SCOPES,
    )
    creds.refresh(Request())

    # Save auth method config
    _save_auth_method(
        {
            "method": "service-account",
            "service_account_path": str(Path(key_path).resolve()),
            "service_account_email": key_data["client_email"],
        }
    )

    return key_data["client_email"]


def get_service_account_credentials() -> Optional[service_account.Credentials]:
    """Get service account credentials if configured.

    Check order:
    1. GA_CLI_SERVICE_ACCOUNT env var
    2. GOOGLE_APPLICATION_CREDENTIALS env var
    3. Saved auth method from previous login

    Returns None if no service account is configured (OAuth should be used).
    """
    # Check env vars first
    for env_var in ("GA_CLI_SERVICE_ACCOUNT", "GOOGLE_APPLICATION_CREDENTIALS"):
        key_path = os.environ.get(env_var)
        if key_path:
            validate_service_account_key(key_path)
            return service_account.Credentials.from_service_account_file(
                key_path,
                scopes=OAUTH_SCOPES,
            )

    # Check saved auth method
    auth_method = _load_auth_method()
    if auth_method and auth_method.get("method") == "service-account":
        key_path = auth_method.get("service_account_path")
        if key_path:
            validate_service_account_key(key_path)
            return service_account.Credentials.from_service_account_file(
                key_path,
                scopes=OAUTH_SCOPES,
            )

    return None


def _save_auth_method(config: dict) -> None:
    """Save auth method configuration."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    get_auth_method_path().write_text(json.dumps(config, indent=2))


def _load_auth_method() -> Optional[dict]:
    """Load auth method configuration."""
    try:
        return json.loads(get_auth_method_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def clear_auth_method() -> None:
    """Delete auth method configuration."""
    try:
        get_auth_method_path().unlink()
    except FileNotFoundError:
        pass


def load_auth_method() -> Optional[dict]:
    """Public access to load auth method (used by auth status command)."""
    return _load_auth_method()
