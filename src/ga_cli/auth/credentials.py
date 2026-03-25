"""Credential storage and management.

Stores OAuth tokens at ~/.config/ga-cli/credentials.json with
restrictive permissions (0o600 on Unix).

Equivalent to GTM CLI's auth/credentials.ts.
"""

from __future__ import annotations

import json
import logging
import os
import platform
from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials

from ..config.constants import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    OAUTH_SCOPES,
    get_config_dir,
    get_credentials_path,
)

logger = logging.getLogger(__name__)


def save_credentials(credentials: Credentials) -> None:
    """Save OAuth credentials to disk.

    Stores the token data as JSON with 0o600 permissions on Unix.
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    creds_path = get_credentials_path()

    data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else OAUTH_SCOPES,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }

    creds_path.write_text(json.dumps(data, indent=2))

    # Set restrictive permissions on Unix
    if platform.system() != "Windows":
        os.chmod(creds_path, 0o600)


def load_credentials() -> Optional[Credentials]:
    """Load OAuth credentials from disk.

    Returns None if no credentials file exists or if the file is corrupt.
    """
    creds_path = get_credentials_path()

    if not creds_path.exists():
        return None

    try:
        data = json.loads(creds_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read credentials file: %s", exc)
        return None

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=data.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=data.get("scopes", OAUTH_SCOPES),
    )

    if data.get("expiry"):
        try:
            expiry = datetime.fromisoformat(data["expiry"])
            # google-auth expects expiry without tzinfo (assumes UTC internally)
            creds.expiry = expiry.replace(tzinfo=None)
        except ValueError:
            logger.warning("Invalid expiry timestamp in credentials file")

    return creds


def delete_credentials() -> None:
    """Delete stored credentials file."""
    creds_path = get_credentials_path()
    try:
        creds_path.unlink()
    except FileNotFoundError:
        pass


def has_credentials() -> bool:
    """Check if credentials file exists."""
    return get_credentials_path().exists()


def get_valid_credentials() -> Optional[Credentials]:
    """Load credentials and refresh if expired.

    This is the main entry point for getting a usable token.
    Returns None if no credentials are stored.
    """
    creds = load_credentials()
    if creds is None:
        return None

    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request

        try:
            creds.refresh(Request())
            save_credentials(creds)
        except Exception as exc:
            logger.warning("Failed to refresh token: %s", exc)
            return None

    return creds
