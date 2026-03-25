"""Error handling utilities.

Provides consistent error formatting for Google API errors.
Equivalent to GTM CLI's utils/errors.ts.
"""

from __future__ import annotations

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
            import json
            detail = json.loads(err.content.decode())
            message = detail.get("error", {}).get("message", str(err))
            return message
        except (json.JSONDecodeError, AttributeError):
            return str(err)

    return str(err)


def handle_error(err: Exception) -> NoReturn:
    """Print error to stderr and exit with code 1.

    Equivalent to GTM CLI's handleError().
    """
    message = format_api_error(err)
    print_error(message)
    sys.exit(1)


def require_options(options: dict, required: list[str]) -> None:
    """Validate that required options are present.

    Raises typer.BadParameter if any are missing.
    Equivalent to GTM CLI's requireOptions().
    """
    import typer
    missing = [k for k in required if not options.get(k)]
    if missing:
        formatted = [f"--{k.replace('_', '-')}" for k in missing]
        raise typer.BadParameter(f"Missing required options: {', '.join(formatted)}")
