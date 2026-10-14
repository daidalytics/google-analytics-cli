"""Service account authentication.

Supports, for the default profile:
1. GA_CLI_SERVICE_ACCOUNT env var (path to key file)
2. GOOGLE_APPLICATION_CREDENTIALS env var (standard Google convention), when
   it points to a service account key
3. Saved auth method from a previous ``ga auth login --service-account`` call

A named profile supports only (3), from its own directory.

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

from ..config.constants import OAUTH_SCOPES, get_auth_method_path, is_named_profile

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
    """Get the active profile's service account credentials, if configured.

    Default profile, in order:
    1. ``GA_CLI_SERVICE_ACCOUNT``: must be a service account key, else
       ``ValueError``.
    2. ``GOOGLE_APPLICATION_CREDENTIALS``, only when it is a service account
       key. A file of any other type (``external_account`` from Workload
       Identity Federation, ``authorized_user``, ...) is skipped and left to
       ``google.auth.default()``. A missing or malformed file still raises.
    3. Saved auth method from a previous ``ga auth login --service-account``.

    A named profile uses only (3), read from its own directory. It ignores both
    env vars: an exported key must never override an explicitly chosen client.

    Returns None if no service account is configured (OAuth should be used).
    """
    if not is_named_profile():
        key_path = os.environ.get("GA_CLI_SERVICE_ACCOUNT")
        if key_path:
            return _credentials_from_key(key_path)

        key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if key_path and not _is_other_credential_type(key_path):
            return _credentials_from_key(key_path)

    auth_method = _load_auth_method()
    if auth_method and auth_method.get("method") == "service-account":
        key_path = auth_method.get("service_account_path")
        if key_path:
            return _credentials_from_key(key_path)

    return None


def _credentials_from_key(key_path: str) -> service_account.Credentials:
    """Validate a service account key file and build credentials from it."""
    validate_service_account_key(key_path)
    return service_account.Credentials.from_service_account_file(
        key_path,
        scopes=OAUTH_SCOPES,
    )


def _is_other_credential_type(key_path: str) -> bool:
    """True when ``key_path`` is a credential file that is not a service account key.

    Missing, unreadable, or malformed files return False, so
    ``validate_service_account_key()`` raises its usual error for them.
    """
    try:
        data = json.loads(Path(key_path).read_text())
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("type") != "service_account"


def _save_auth_method(config: dict) -> None:
    """Save auth method configuration, creating the active profile's dir."""
    path = get_auth_method_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))


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
