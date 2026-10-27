"""Google Analytics API client wrappers.

Provides authenticated clients for the Analytics Admin API and Data API.
Uses google-api-python-client (REST-based), consistent with GTM CLI's use
of the googleapis npm package.

Credential resolution (B4 in the 0.6.0 spec, ``git show 7594078:SPEC.md``),
implemented by ``resolve_credentials()``:

Default profile:
1. ``GA_CLI_SERVICE_ACCOUNT``
2. ``GOOGLE_APPLICATION_CREDENTIALS`` (service account keys only; other
   credential types are left to step 5)
3. Saved service account (``auth-method.json``)
4. OAuth (``credentials.json``)
5. gcloud Application Default Credentials (``google.auth.default()``)

Named profile (``--profile X`` / ``GA_CLI_PROFILE=X``):
1. ``profiles/X/auth-method.json`` service account
2. ``profiles/X/credentials.json`` OAuth

A named profile never falls back: not to the env vars, not to the default
profile, not to ADC. Wrong-client data that looks right is worse than an error.

Equivalent to GTM CLI's api/client.ts.
"""

from __future__ import annotations

import os
from typing import Literal, Optional

import google.auth
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import Resource, build
from googleapiclient.http import build_http

from ..auth.credentials import get_valid_credentials, has_credentials
from ..auth.service_account import get_service_account_credentials
from ..config.allowlist import load_allowlist
from ..config.constants import (
    OAUTH_SCOPES,
    get_active_profile,
    is_named_profile,
    profile_exists,
)
from ..utils.errors import (
    ADC_IMPERSONATE_COMMAND,
    ADC_LOGIN_COMMAND,
    AllowlistConfigError,
    NotAuthenticatedError,
    ProfileNotFoundError,
)
from .allowlist_guard import AllowlistCache, AllowlistHttp, cache_for, reset_caches

AuthMethod = Literal["service-account", "oauth", "adc"]

# Cached client instances (same pattern as GTM CLI)
_cached_admin_client: Optional[Resource] = None
_cached_admin_alpha_client: Optional[Resource] = None
_cached_data_client: Optional[Resource] = None
_cached_data_alpha_client: Optional[Resource] = None

# How the most recent successful resolve_credentials() call authenticated, so
# error handling can tailor its advice (the ADC scope hint). Reset with the
# client cache.
_last_auth_method: Optional[AuthMethod] = None

# The pre-ADC "Not authenticated" message. Still used when a stored OAuth token
# exists but cannot be loaded or refreshed: that is a login to repair, and ADC
# is not consulted while it is there.
_OAUTH_UNUSABLE_MESSAGE = (
    "Not authenticated. Run 'ga auth login' or configure a service account."
)


def resolve_credentials() -> tuple[Credentials, AuthMethod]:
    """Resolve the active profile's credentials and how they were obtained.

    See the module docstring for the resolution order.

    Raises:
        ProfileNotFoundError: The named profile does not exist. Raised before
            any credential source is read.
        NotAuthenticatedError: Nothing usable is configured.
        FileNotFoundError, ValueError: A configured service account key is
            missing or invalid (there is no fallback past it).
    """
    global _last_auth_method
    _last_auth_method = None

    profile = get_active_profile()
    named = is_named_profile()

    if named and not profile_exists(profile):
        raise ProfileNotFoundError.for_profile(profile)

    # Service account. A named profile only reads its own auth-method.json.
    sa_creds = get_service_account_credentials()
    if sa_creds is not None:
        if sa_creds.expired:
            from google.auth.transport.requests import Request

            sa_creds.refresh(Request())
        _last_auth_method = "service-account"
        return sa_creds, "service-account"

    # The active profile's stored OAuth token (refreshed if expired).
    oauth_creds = get_valid_credentials()
    if oauth_creds is not None:
        _last_auth_method = "oauth"
        return oauth_creds, "oauth"

    if named:
        raise NotAuthenticatedError(
            f"Profile '{profile}' has no credentials. "
            f"Run: ga --profile {profile} auth login [--service-account KEY]"
        )

    # A configured OAuth login wins over ADC even when it is broken: switching
    # to another Google identity would hide the problem.
    if has_credentials():
        raise NotAuthenticatedError(_OAUTH_UNUSABLE_MESSAGE)

    # Looked up at call time so tests can patch google.auth.default.
    try:
        adc_creds, _project = google.auth.default(scopes=OAUTH_SCOPES)
    except DefaultCredentialsError as exc:
        raise NotAuthenticatedError(_not_authenticated_message(exc)) from exc
    _last_auth_method = "adc"
    return adc_creds, "adc"


def get_last_auth_method() -> Optional[AuthMethod]:
    """How the most recent successful ``resolve_credentials()`` call authenticated.

    None before any resolution, after a failed one, and after
    ``clear_client_cache()``.
    """
    return _last_auth_method


def _not_authenticated_message(adc_error: DefaultCredentialsError) -> str:
    """The default profile's final error: every way to authenticate."""
    message = (
        "Not authenticated. Run 'ga auth login' (OAuth), "
        "'ga auth login --service-account KEY' or export GA_CLI_SERVICE_ACCOUNT=KEY "
        "(service account), or create gcloud Application Default Credentials "
        "with your own OAuth client or by impersonating a service account:\n"
        f"  {ADC_LOGIN_COMMAND}\n"
        f"  {ADC_IMPERSONATE_COMMAND}"
    )
    # With GOOGLE_APPLICATION_CREDENTIALS set, ADC failed on that file
    # (e.g. a broken Workload Identity Federation config): say why.
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac:
        message += f"\nGOOGLE_APPLICATION_CREDENTIALS ({gac}) could not be used: {adc_error}"
    return message


def _get_credentials() -> Credentials:
    """Get valid credentials for the active profile (see resolve_credentials())."""
    creds, _method = resolve_credentials()
    return creds


def _build(service: str, version: str, **kwargs) -> Resource:
    """Build a client; with an allowlist set, every request goes through the guard.

    Without one, build exactly as 0.6.0 did: passing http= makes googleapiclient skip
    its own transport setup, including the GOOGLE_API_USE_MTLS_ENDPOINT switch (#44).

    Raises AllowlistConfigError if the configured allowlist is malformed, or if it is
    set together with GOOGLE_API_USE_MTLS_ENDPOINT=always, which the guard can't honour.
    """
    creds = _get_credentials()
    allowlist = load_allowlist()
    if not allowlist.enabled:
        return build(service, version, credentials=creds, **kwargs)
    if os.environ.get("GOOGLE_API_USE_MTLS_ENDPOINT") == "always":
        raise AllowlistConfigError(
            "GOOGLE_API_USE_MTLS_ENDPOINT",
            "GOOGLE_API_USE_MTLS_ENDPOINT=always isn't supported while an allowlist is set: "
            "allowlisted requests can only go to the regular endpoint",
        )
    http = AllowlistHttp(creds, http=build_http(), allowlist=allowlist)
    return build(service, version, http=http, **kwargs)


def get_admin_client() -> Resource:
    """Get an authenticated Analytics Admin API client.

    Returns a googleapiclient Resource for analyticsadmin v1beta.
    Uses caching to avoid rebuilding the client on every call.

    Usage:
        admin = get_admin_client()
        result = admin.accounts().list().execute()
    """
    global _cached_admin_client
    if _cached_admin_client is None:
        _cached_admin_client = _build("analyticsadmin", "v1beta")
    return _cached_admin_client


def get_admin_alpha_client() -> Resource:
    """Get an authenticated Analytics Admin API client (v1alpha).

    Returns a googleapiclient Resource for analyticsadmin v1alpha.
    Used for alpha-only resources: audiences, BigQuery links, channel groups,
    calculated metrics, event rules, access bindings, annotations, etc.
    """
    global _cached_admin_alpha_client
    if _cached_admin_alpha_client is None:
        _cached_admin_alpha_client = _build("analyticsadmin", "v1alpha")
    return _cached_admin_alpha_client


def get_data_client() -> Resource:
    """Get an authenticated Analytics Data API client.

    Returns a googleapiclient Resource for analyticsdata v1beta.

    Usage:
        data = get_data_client()
        result = data.properties().runReport(
            property="properties/12345",
            body={...},
        ).execute()
    """
    global _cached_data_client
    if _cached_data_client is None:
        _cached_data_client = _build("analyticsdata", "v1beta")
    return _cached_data_client


def get_data_alpha_client() -> Resource:
    """Get an authenticated Analytics Data API client (v1alpha).

    Returns a googleapiclient Resource for analyticsdata v1alpha.
    Used for alpha-only methods: funnel reports, property quotas snapshot.
    """
    global _cached_data_alpha_client
    if _cached_data_alpha_client is None:
        _cached_data_alpha_client = _build("analyticsdata", "v1alpha", static_discovery=False)
    return _cached_data_alpha_client


def get_allowlist_cache() -> AllowlistCache:
    """The allowlist's property → account cache for the current credentials."""
    return cache_for(_get_credentials(), build_http())


def clear_client_cache() -> None:
    """Clear cached API clients (e.g., after re-authentication).

    Also forgets the allowlist caches, which hold the old credentials (#45).
    """
    global _cached_admin_client, _cached_admin_alpha_client
    global _cached_data_client, _cached_data_alpha_client
    global _last_auth_method
    _cached_admin_client = None
    _cached_admin_alpha_client = None
    _cached_data_client = None
    _cached_data_alpha_client = None
    _last_auth_method = None
    reset_caches()
