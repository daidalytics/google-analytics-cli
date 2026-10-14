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

# Creates gcloud Application Default Credentials that carry the scopes GA needs.
# gcloud *user* ADC ignores the scopes a client requests unless it was created
# with them (SPEC B4), so every ADC hint names them explicitly.
ADC_LOGIN_COMMAND = (
    "gcloud auth application-default login --scopes="
    "https://www.googleapis.com/auth/analytics.readonly,"
    "https://www.googleapis.com/auth/cloud-platform"
)

# Google's ErrorInfo reason for an access token that lacks a required scope.
SCOPE_INSUFFICIENT_REASON = "ACCESS_TOKEN_SCOPE_INSUFFICIENT"

ADC_SCOPE_HINT = (
    "These credentials come from gcloud Application Default Credentials "
    f"without the Analytics scopes. Run: {ADC_LOGIN_COMMAND}"
)


class NotAuthenticatedError(RuntimeError):
    """No usable credentials for the active profile. Exit 2 (``auth_error``)."""


class ProfileNotFoundError(RuntimeError):
    """The selected named profile does not exist. Exit 2 (``auth_error``).

    Raised before any credential source is read or API client is built: a typo
    in ``--profile`` must never fall back to another identity.
    """

    @classmethod
    def for_profile(cls, profile: str) -> ProfileNotFoundError:
        """Build the error with the known-profiles list and the create hint."""
        from ..config.constants import list_profiles

        return cls(
            f"Profile '{profile}' does not exist. "
            f"Known profiles: {', '.join(list_profiles())}.\n"
            f"Create it with: ga --profile {profile} auth login"
        )


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

    # Our own credential-resolution errors
    if isinstance(err, (NotAuthenticatedError, ProfileNotFoundError)):
        return 2, "auth_error"

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

    # Any other RuntimeError that mentions auth (kept for messages raised
    # without one of the explicit classes above)
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


def _error_reasons(err: Exception) -> set[str]:
    """The ``reason`` values in a Google API error body's ``error.details``.

    Empty for anything that is not an HttpError with a parseable body.
    """
    from googleapiclient.errors import HttpError

    if not isinstance(err, HttpError):
        return set()
    try:
        details = json.loads(err.content.decode()).get("error", {}).get("details")
    except (ValueError, AttributeError):  # ValueError covers JSON and Unicode errors
        return set()
    if not isinstance(details, list):
        return set()
    return {
        detail["reason"]
        for detail in details
        if isinstance(detail, dict) and isinstance(detail.get("reason"), str)
    }


def error_hint(err: Exception) -> str | None:
    """Advice to show alongside an error, or None.

    Only case today: a 403 ``ACCESS_TOKEN_SCOPE_INSUFFICIENT`` while the
    credentials came from gcloud ADC. User ADC ignores the scopes a client asks
    for unless it was created with them (SPEC B4), so the fix is a re-login.
    """
    from googleapiclient.errors import HttpError

    if not isinstance(err, HttpError) or err.resp.status != 403:
        return None
    if SCOPE_INSUFFICIENT_REASON not in _error_reasons(err):
        return None

    # Imported lazily: api.client imports this module.
    from ..api.client import get_last_auth_method

    if get_last_auth_method() != "adc":
        return None
    return ADC_SCOPE_HINT


def handle_error(err: Exception) -> NoReturn:
    """Print error and exit with a classified exit code.

    When output format is JSON (explicit or non-TTY), emit structured
    JSON to stderr. Otherwise, emit human-readable Rich text. Advice from
    ``error_hint()`` goes in a separate ``"hint"`` field (JSON) or on its own
    line after the message (text); the message itself is never altered.
    """
    from .output import get_current_output_format

    exit_code, category = classify_error(err)
    message = format_api_error(err)
    hint = error_hint(err)
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
        if hint:
            payload["hint"] = hint

        # Write raw JSON to stderr — avoid Rich Console which may wrap lines
        print(json.dumps(payload, default=str), file=sys.stderr)
    else:
        print_error(f"{message}\n{hint}" if hint else message)

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
