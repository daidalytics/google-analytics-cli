"""Authentication module for GA CLI.

Public API for OAuth and service account authentication.
"""

from .credentials import (
    delete_credentials,
    get_valid_credentials,
    has_credentials,
    load_credentials,
    save_credentials,
)
from .oauth import get_auth_status, login, logout
from .service_account import (
    get_service_account_credentials,
    load_auth_method,
    login_with_service_account,
)

__all__ = [
    # OAuth flow
    "login",
    "logout",
    "get_auth_status",
    # Credentials
    "get_valid_credentials",
    "load_credentials",
    "save_credentials",
    "delete_credentials",
    "has_credentials",
    # Service account
    "login_with_service_account",
    "get_service_account_credentials",
    "load_auth_method",
]
