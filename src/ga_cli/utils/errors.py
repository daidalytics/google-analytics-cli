"""Error handling utilities.

Provides consistent error formatting for Google API errors.
When the output format is JSON, errors are emitted as structured JSON
to stderr with distinct exit codes for different failure categories.
"""

from __future__ import annotations

import json
import sys
from typing import NoReturn

from .output import error as print_error


def format_api_error(err: Exception) -> str:
    """Extract a human-readable message from a Google API error.

    Handles googleapiclient.errors.HttpError and generic exceptions.
    """
    # google-api-python-client raises HttpError
    from googleapiclient.errors import HttpError

    if isinstance(err, HttpError):
        try:
            detail = json.loads(err.content.decode())
            message = detail.get("error", {}).get("message", str(err))
            return message
        except (json.JSONDecodeError, AttributeError):
            return str(err)

    return str(err)


def classify_error(err: Exception) -> tuple[int, str]:
    """Classify an exception into (exit_code, category).

    Exit codes:
        1 — client_error: bad input, missing flags, validation failure
        2 — auth_error: not authenticated, token expired, permission denied (401/403)
        3 — api_error: Google returned 4xx (not auth) or 5xx
        4 — network_error: connection timeout, DNS failure, unreachable

    Returns:
        (exit_code, category)
    """
    from googleapiclient.errors import HttpError

    if isinstance(err, HttpError):
        status = err.resp.status
        if status in (401, 403):
            return 2, "auth_error"
        return 3, "api_error"

    # Auth-specific exceptions
    try:
        from google.auth.exceptions import DefaultCredentialsError, RefreshError

        if isinstance(err, (RefreshError, DefaultCredentialsError)):
            return 2, "auth_error"
    except ImportError:
        pass

    # Network errors
    try:
        from requests.exceptions import ConnectionError as RequestsConnectionError
        from requests.exceptions import Timeout

        if isinstance(err, (RequestsConnectionError, Timeout)):
            return 4, "network_error"
    except ImportError:
        pass

    try:
        from urllib3.exceptions import NewConnectionError

        if isinstance(err, NewConnectionError):
            return 4, "network_error"
    except ImportError:
        pass

    if isinstance(err, OSError) and _is_network_os_error(err):
        return 4, "network_error"

    # RuntimeError from our own auth code ("Not authenticated...")
    if isinstance(err, RuntimeError) and "auth" in str(err).lower():
        return 2, "auth_error"

    return 3, "api_error"


def _is_network_os_error(err: OSError) -> bool:
    """Check if an OSError is network-related (vs file I/O, permissions, etc.)."""
    import errno

    network_errnos = {
        errno.ECONNREFUSED,
        errno.ECONNRESET,
        errno.ECONNABORTED,
        errno.ETIMEDOUT,
        errno.EHOSTUNREACH,
        errno.ENETUNREACH,
    }
    return err.errno in network_errnos


def handle_error(err: Exception) -> NoReturn:
    """Print error and exit with a classified exit code.

    When output format is JSON (explicit or non-TTY), emit structured
    JSON to stderr. Otherwise, emit human-readable Rich text.
    """
    from .output import get_current_output_format

    exit_code, category = classify_error(err)
    message = format_api_error(err)
    fmt = get_current_output_format()

    if fmt == "json":
        payload: dict = {
            "error": True,
            "exit_code": exit_code,
            "category": category,
            "message": message,
        }
        from googleapiclient.errors import HttpError

        if isinstance(err, HttpError):
            payload["status_code"] = err.resp.status

        # Write raw JSON to stderr — avoid Rich Console which may wrap lines
        print(json.dumps(payload, default=str), file=sys.stderr)
    else:
        print_error(message)

    sys.exit(exit_code)


def require_options(options: dict, required: list[str]) -> None:
    """Validate that required options are present.

    Raises typer.BadParameter if any are missing.
    """
    import typer

    missing = [k for k in required if not options.get(k)]
    if missing:
        formatted = [f"--{k.replace('_', '-')}" for k in missing]
        raise typer.BadParameter(f"Missing required options: {', '.join(formatted)}")
