"""OAuth 2.0 authentication flow.

Uses google-auth-oauthlib's InstalledAppFlow which handles:
- Local HTTP server for the callback
- Browser opening
- CSRF state parameter
- Authorization code exchange
- Token retrieval

This replaces ~300 lines of manual OAuth code in the GTM CLI.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..config.constants import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    OAUTH_CALLBACK_PORT,
    OAUTH_SCOPES,
    get_client_secret_path,
)
from .credentials import (
    delete_credentials,
    get_valid_credentials,
    load_credentials,
    save_credentials,
)

logger = logging.getLogger(__name__)


def _get_client_config() -> dict:
    """Build the OAuth client config dict from env vars / constants."""
    return {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"http://localhost:{OAUTH_CALLBACK_PORT}"],
        }
    }


def login() -> Credentials:
    """Run the full OAuth login flow.

    Opens a browser, starts a local server, waits for the callback,
    exchanges the code for tokens, and saves credentials to disk.

    Raises:
        ValueError: If client credentials are not configured.
        OSError: If the callback port is already in use.
    """
    client_secret_path = get_client_secret_path()

    if client_secret_path.exists():
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            scopes=OAUTH_SCOPES,
        )
    else:
        if GOOGLE_CLIENT_ID == "__OAUTH_CLIENT_ID__":
            raise ValueError(
                "OAuth client credentials not configured. "
                "Either place a client_secret.json in "
                f"{client_secret_path.parent} or set GA_CLI_CLIENT_ID "
                "and GA_CLI_CLIENT_SECRET environment variables."
            )
        flow = InstalledAppFlow.from_client_config(
            _get_client_config(),
            scopes=OAUTH_SCOPES,
        )

    credentials = flow.run_local_server(
        port=OAUTH_CALLBACK_PORT,
        prompt="consent",
        access_type="offline",
        open_browser=True,
    )

    save_credentials(credentials)
    return credentials


def logout() -> None:
    """Revoke tokens and delete local credentials.

    Attempts to revoke the token with Google (best-effort),
    then deletes the local credentials file.
    """
    creds = load_credentials()

    if creds and creds.token:
        try:
            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": creds.token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
        except requests.RequestException:
            logger.debug("Token revocation failed (token may already be revoked)")

    delete_credentials()


def get_auth_status() -> dict:
    """Get current OAuth authentication status.

    Returns a dict with authentication state, suitable for display.
    """
    creds = load_credentials()

    if creds is None:
        return {"authenticated": False}

    result: dict = {
        "authenticated": True,
        "token_valid": creds.valid,
        "expired": creds.expired,
        "has_refresh_token": creds.refresh_token is not None,
    }

    if creds.expiry:
        result["expires_at"] = creds.expiry.isoformat()

    # Try to fetch user info if we have a valid or refreshable token
    if creds.valid or (creds.expired and creds.refresh_token):
        valid_creds = get_valid_credentials()
        if valid_creds and valid_creds.token:
            user_info = _fetch_user_info(valid_creds.token)
            if user_info:
                result["email"] = user_info.get("email")
                result["name"] = user_info.get("name")

    return result


def _fetch_user_info(access_token: str) -> Optional[dict]:
    """Fetch user info from Google (email, name)."""
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.ok:
            return resp.json()
    except requests.RequestException:
        logger.debug("Failed to fetch user info")
    return None
