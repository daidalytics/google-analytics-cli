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
import os
import webbrowser
import wsgiref.simple_server
import wsgiref.util
from typing import Optional

import requests
import typer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from rich.panel import Panel

from ..config.constants import (
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

_SUCCESS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GA CLI – Authentication Successful</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         Helvetica, Arial, sans-serif;
            background: #f8f9fa;
            color: #1a1a2e;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        .card {
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
            padding: 48px 40px;
            text-align: center;
            max-width: 420px;
            width: 100%;
        }
        .icon {
            width: 80px; height: 80px;
            background: #235495;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 20px;
        }
        .icon svg { width: 40px; height: 40px; }
        .brand {
            font-size: 14px;
            font-weight: 600;
            color: #dd973a;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        h1 {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .subtitle {
            font-size: 15px;
            color: #666;
            margin-bottom: 28px;
        }
        .command {
            display: inline-block;
            background: #f4f4f5;
            border: 1px solid #e4e4e7;
            border-radius: 8px;
            padding: 10px 20px;
            font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
            font-size: 14px;
            color: #1a1a2e;
        }
        .footer {
            margin-top: 32px;
            font-size: 12px;
            color: #aaa;
        }
        .footer a { color: #dd973a; text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"
                 stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 6L9 17l-5-5"/>
            </svg>
        </div>
        <div class="brand">GA CLI</div>
        <h1>Authentication Successful</h1>
        <p class="subtitle">
            You're all set! You can close this window and<br>return to your terminal.
        </p>
        <div class="command">ga accounts list</div>
        <div class="footer">
            Powered by <a href="https://github.com/daidalytics/google-analytics-cli"
                          target="_blank" rel="noopener">ga-cli</a>
        </div>
    </div>
</body>
</html>
"""


class _HtmlRedirectWSGIApp:
    """WSGI app that serves a styled HTML success page on OAuth callback."""

    def __init__(self, html: str):
        self.last_request_uri: Optional[str] = None
        self._html = html

    def __call__(self, environ, start_response):
        start_response(
            "200 OK",
            [("Content-Type", "text/html; charset=utf-8")],
        )
        self.last_request_uri = wsgiref.util.request_uri(environ)
        return [self._html.encode("utf-8")]


class _SilentRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """Request handler that logs to the logger instead of stderr."""

    def log_message(self, format, *args):  # noqa: A002
        logger.debug(format, *args)


def _get_client_config() -> dict:
    """Build the OAuth client config dict from env vars."""
    client_id = os.environ.get("GA_CLI_CLIENT_ID", "")
    client_secret = os.environ.get("GA_CLI_CLIENT_SECRET", "")
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
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
        typer.Exit: If client credentials are not configured.
        OSError: If the callback port is already in use.
    """
    client_secret_path = get_client_secret_path()

    if client_secret_path.exists():
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            scopes=OAUTH_SCOPES,
        )
    elif os.environ.get("GA_CLI_CLIENT_ID") and os.environ.get("GA_CLI_CLIENT_SECRET"):
        flow = InstalledAppFlow.from_client_config(
            _get_client_config(),
            scopes=OAUTH_SCOPES,
        )
    else:
        from ..utils.output import err_console

        err_console.print(Panel(
            "[bold]OAuth client credentials not found.[/bold]\n\n"
            "GA CLI requires your own GCP OAuth credentials. "
            "Choose one of the following:\n\n"
            "[cyan]Option 1:[/cyan] Place a client_secret.json file in:\n"
            f"  [green]{client_secret_path}[/green]\n\n"
            "[cyan]Option 2:[/cyan] Set environment variables:\n"
            "  [green]GA_CLI_CLIENT_ID[/green] and "
            "[green]GA_CLI_CLIENT_SECRET[/green]\n\n"
            "For step-by-step setup instructions, run:\n"
            "  [bold yellow]ga agent guide --section setup[/bold yellow]\n\n"
            "Create OAuth credentials in the GCP Console:\n"
            "  APIs & Services > Credentials > Create OAuth client ID (Desktop app)",
            title="[red]Missing Credentials[/red]",
            border_style="red",
            expand=False,
        ))
        raise typer.Exit(1)

    # Custom local server flow to serve a styled HTML success page
    wsgi_app = _HtmlRedirectWSGIApp(_SUCCESS_HTML)
    wsgiref.simple_server.WSGIServer.allow_reuse_address = False
    local_server = wsgiref.simple_server.make_server(
        "localhost",
        OAUTH_CALLBACK_PORT,
        wsgi_app,
        handler_class=_SilentRequestHandler,
    )

    try:
        flow.redirect_uri = f"http://localhost:{local_server.server_port}/"
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
        )

        webbrowser.open(auth_url, new=1, autoraise=True)
        print(f"Please visit this URL to authorize this application: {auth_url}")

        local_server.handle_request()

        authorization_response = wsgi_app.last_request_uri.replace(
            "http", "https"
        )
        flow.fetch_token(authorization_response=authorization_response)
    finally:
        local_server.server_close()

    credentials = flow.credentials
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
