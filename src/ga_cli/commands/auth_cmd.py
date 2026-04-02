"""Authentication commands: login, logout, status.

Equivalent to GTM CLI's commands/auth.ts.
"""

from typing import Optional

import typer

from ..api.client import clear_client_cache
from ..auth.oauth import get_auth_status, login, logout
from ..auth.service_account import (
    clear_auth_method,
    load_auth_method,
    login_with_service_account,
)
from ..utils import error, info, output, success

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
4. No scopes need to be added manually — GA CLI requests them at login time
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
    output_format: str = typer.Option("table", "--output", "-o", help="Output format"),
):
    """Show current authentication status."""
    try:
        import os

        # Check for env var override (same priority as GTM CLI)
        env_key = os.environ.get("GA_CLI_SERVICE_ACCOUNT") or os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        if env_key:
            data = {
                "authenticated": True,
                "method": "service-account",
                "source": "environment variable",
                "key_path": env_key,
            }
            output(data, output_format)
            return

        # Check saved auth method
        auth_method = load_auth_method()
        if auth_method and auth_method.get("method") == "service-account":
            data = {
                "authenticated": True,
                "method": "service-account",
                "email": auth_method.get("service_account_email"),
                "key_path": auth_method.get("service_account_path"),
            }
            output(data, output_format)
            return

        # Fall back to OAuth
        auth_status = get_auth_status()
        auth_status["method"] = "oauth"
        output(auth_status, output_format)

        if not auth_status.get("authenticated"):
            info("Run 'ga auth login' to authenticate.")

    except Exception as e:
        error(f"Failed to get status: {e}")
        raise typer.Exit(1)
