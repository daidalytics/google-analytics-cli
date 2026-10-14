"""Authentication commands: login, logout, status.

Equivalent to GTM CLI's commands/auth.ts.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import typer

from ..api.client import clear_client_cache, resolve_credentials
from ..auth.credentials import has_credentials
from ..auth.oauth import get_auth_status, login, logout
from ..auth.service_account import (
    clear_auth_method,
    load_auth_method,
    login_with_service_account,
    validate_service_account_key,
)
from ..config.constants import get_active_profile, is_named_profile
from ..utils import error, info, output, resolve_output_format, success
from ..utils.errors import NotAuthenticatedError, ProfileNotFoundError

auth_app = typer.Typer(name="auth", help="Manage authentication", no_args_is_help=True)

_SETUP_GUIDE = r"""# GA CLI — OAuth Credential Setup

GA CLI requires your own Google Cloud Platform OAuth credentials.
Follow these steps to create them.

## Step 1: Create or Select a GCP Project

1. Go to the Google Cloud Console: https://console.cloud.google.com/
2. Create a new project or select an existing one
3. Note your project ID

## Step 2: Enable Required APIs

In the GCP Console, go to APIs & Services > Library and enable:
- Google Analytics Admin API
- Google Analytics Data API

Or via gcloud CLI:

    gcloud services enable analyticsadmin.googleapis.com analyticsdata.googleapis.com

## Step 3: Configure OAuth Consent Screen

1. Go to APIs & Services > OAuth consent screen
2. Choose "External" user type (or "Internal" if using Google Workspace)
3. Fill in the required fields: app name, user support email, developer contact
4. In "Testing" mode no scopes need to be added manually — GA CLI requests them
   at login time and Google shows them on the consent screen. If you publish the
   app to "In production", add the scopes GA CLI requests (see `ga auth status`)
   to the consent screen, or Google may drop unregistered ones
5. For personal use, leave the app in "Testing" mode — it works for the
   project owner and up to 100 added test users without Google verification

## Step 4: Create OAuth Client ID

1. Go to APIs & Services > Credentials
2. Click "Create Credentials" > "OAuth client ID"
3. Choose "Desktop app" as the application type
4. Give it a name (e.g., "GA CLI")
5. Click "Create" and download the JSON file

## Step 5: Provide Credentials to GA CLI

Option A — Place the downloaded JSON file (recommended):

    mkdir -p ~/.config/ga-cli
    cp /path/to/downloaded/client_secret_*.json ~/.config/ga-cli/client_secret.json

Option B — Set environment variables:

    export GA_CLI_CLIENT_ID="your-client-id.apps.googleusercontent.com"
    export GA_CLI_CLIENT_SECRET="your-client-secret"

## Step 6: Authenticate

    ga auth login

This opens your browser for Google OAuth consent and stores the token
locally at ~/.config/ga-cli/credentials.json.

## Verification

    ga auth status          # Check authentication state
    ga accounts list        # Verify API access

## Notes

- "Testing" mode is sufficient for personal use — no Google verification needed
- For team use, publish the consent screen to "Production" within your GCP project
- Service account auth (ga auth login --service-account /path/key.json) does not
  require OAuth credentials and works independently
"""


@auth_app.command("setup")
def setup_cmd():
    """Show step-by-step instructions for obtaining GCP OAuth credentials."""
    print(_SETUP_GUIDE)


@auth_app.command("login")
def login_cmd(
    service_account: Optional[str] = typer.Option(
        None, "--service-account", "-s",
        help="Path to service account key JSON file",
    ),
):
    """Authenticate with Google Analytics."""
    try:
        if service_account:
            info(f"Authenticating with service account: {service_account}")
            email = login_with_service_account(service_account)
            success(f"Authenticated as {email}")
            info("Service account credentials are now active.")
            return

        # OAuth (default)
        status = get_auth_status()
        if status.get("authenticated") and status.get("email"):
            info(f"Already authenticated as {status['email']}")
            info("Run 'ga auth logout' first, or 'ga auth status' to view details.")
            return

        info("Opening browser for authentication...")
        login()
        clear_client_cache()

        # Fetch user info to display
        status = get_auth_status()
        email = status.get("email", "unknown")
        success(f"Authenticated as {email}")
    except Exception as e:
        error(f"Authentication failed: {e}")
        raise typer.Exit(1)


@auth_app.command("logout")
def logout_cmd():
    """Sign out and revoke access tokens."""
    try:
        auth_method = load_auth_method()
        status = get_auth_status()

        if not auth_method and not status.get("authenticated"):
            info("Not currently authenticated.")
            return

        if auth_method and auth_method.get("method") == "service-account":
            clear_auth_method()
            email = auth_method.get("service_account_email", "")
            success(f"Cleared service account configuration ({email})")
            info("The service account key file was not deleted.")

        if status.get("authenticated"):
            logout()
            clear_client_cache()
            success("Logged out from OAuth session.")

    except Exception as e:
        error(f"Logout failed: {e}")
        raise typer.Exit(1)


@auth_app.command("status")
def status_cmd(
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Show the active profile's authentication status.

    Reports the credentials API commands would actually use (service account,
    OAuth, or gcloud ADC), resolved the same way. Not being authenticated is
    reported, not an error: exit code 0 with "authenticated": false.
    """
    output_format = resolve_output_format(output_format)
    try:
        output(_auth_status(), output_format)
    except Exception as e:
        error(f"Failed to get status: {e}")
        raise typer.Exit(1)


def _auth_status() -> dict[str, Any]:
    """Status of the active profile, via the same resolution API calls use."""
    profile = get_active_profile()
    try:
        creds, method = resolve_credentials()
    except (NotAuthenticatedError, ProfileNotFoundError) as exc:
        # A stored OAuth login that can no longer be used is still "oauth".
        return _not_authenticated(profile, "oauth" if has_credentials() else "none", exc)
    except (FileNotFoundError, ValueError) as exc:
        # Only a configured service account key raises these: missing or invalid.
        return _not_authenticated(profile, "service-account", exc)

    if method == "service-account":
        details = _service_account_details(creds)
    elif method == "oauth":
        details = {k: v for k, v in get_auth_status().items() if k != "authenticated"}
    else:
        details = _adc_details(creds)
    return {"profile": profile, "authenticated": True, "method": method, **details}


def _not_authenticated(profile: str, method: str, exc: Exception) -> dict[str, Any]:
    return {
        "profile": profile,
        "authenticated": False,
        "method": method,
        "message": str(exc),
    }


def _string_attr(obj: object, name: str) -> Optional[str]:
    value = getattr(obj, name, None)
    return value if isinstance(value, str) and value else None


def _service_account_details(creds: object) -> dict[str, Any]:
    """Identity and key file of the service account resolution picked."""
    email = _string_attr(creds, "service_account_email")
    env_key = None if is_named_profile() else _env_service_account_key()
    if env_key:
        return {"source": "environment variable", "email": email, "key_path": env_key}

    saved = load_auth_method() or {}
    return {
        "email": email or saved.get("service_account_email"),
        "key_path": saved.get("service_account_path"),
    }


def _env_service_account_key() -> Optional[str]:
    """The env var key the default profile's service account came from, if any.

    Mirrors get_service_account_credentials(): ``GA_CLI_SERVICE_ACCOUNT`` wins;
    ``GOOGLE_APPLICATION_CREDENTIALS`` counts only when it is a service account
    key (any other credential type was skipped in favor of the saved account).
    """
    key = os.environ.get("GA_CLI_SERVICE_ACCOUNT")
    if key:
        return key
    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not key:
        return None
    try:
        validate_service_account_key(key)
    except (OSError, ValueError):
        return None
    return key


def _adc_details(creds: object) -> dict[str, Any]:
    """What gcloud ADC credentials reveal without a network call.

    The ADC project is not shown: resolve_credentials() does not keep it, and
    asking google.auth.default() again could mean another slow metadata probe.
    """
    details: dict[str, Any] = {}
    # Service account flavors carry an email; GCE says "default" until refreshed.
    email = _string_attr(creds, "service_account_email")
    if email and "@" in email:
        details["email"] = email
    quota_project = _string_attr(creds, "quota_project_id")
    if quota_project:
        details["quota_project"] = quota_project
    return details
