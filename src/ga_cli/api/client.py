"""Google Analytics API client wrappers.

Provides authenticated clients for the Analytics Admin API and Data API.
Uses google-api-python-client (REST-based), consistent with GTM CLI's use
of the googleapis npm package.

Authentication priority:
1. Service account (env var or saved method)
2. OAuth (stored credentials)

Equivalent to GTM CLI's api/client.ts.
"""

from __future__ import annotations

from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from ..auth.credentials import get_valid_credentials
from ..auth.service_account import get_service_account_credentials

# Cached client instances (same pattern as GTM CLI)
_cached_admin_client: Optional[Resource] = None
_cached_admin_alpha_client: Optional[Resource] = None
_cached_data_client: Optional[Resource] = None
_cached_data_alpha_client: Optional[Resource] = None


def _get_credentials() -> Credentials:
    """Get valid credentials (service account or OAuth).

    Priority: service account > OAuth.
    Raises if no authentication is configured.
    """
    # Try service account first
    sa_creds = get_service_account_credentials()
    if sa_creds is not None:
        from google.auth.transport.requests import Request
        if sa_creds.expired:
            sa_creds.refresh(Request())
        return sa_creds

    # Fall back to OAuth
    oauth_creds = get_valid_credentials()
    if oauth_creds is not None:
        return oauth_creds

    raise RuntimeError(
        "Not authenticated. Run 'ga auth login' or configure a service account."
    )


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
        creds = _get_credentials()
        _cached_admin_client = build(
            "analyticsadmin",
            "v1beta",
            credentials=creds,
        )
    return _cached_admin_client


def get_admin_alpha_client() -> Resource:
    """Get an authenticated Analytics Admin API client (v1alpha).

    Returns a googleapiclient Resource for analyticsadmin v1alpha.
    Used for alpha-only resources: audiences, BigQuery links, channel groups,
    calculated metrics, event rules, access bindings, annotations, etc.
    """
    global _cached_admin_alpha_client
    if _cached_admin_alpha_client is None:
        creds = _get_credentials()
        _cached_admin_alpha_client = build(
            "analyticsadmin",
            "v1alpha",
            credentials=creds,
        )
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
        creds = _get_credentials()
        _cached_data_client = build(
            "analyticsdata",
            "v1beta",
            credentials=creds,
        )
    return _cached_data_client


def get_data_alpha_client() -> Resource:
    """Get an authenticated Analytics Data API client (v1alpha).

    Returns a googleapiclient Resource for analyticsdata v1alpha.
    Used for alpha-only methods: funnel reports, property quotas snapshot.
    """
    global _cached_data_alpha_client
    if _cached_data_alpha_client is None:
        creds = _get_credentials()
        _cached_data_alpha_client = build(
            "analyticsdata",
            "v1alpha",
            credentials=creds,
        )
    return _cached_data_alpha_client


def clear_client_cache() -> None:
    """Clear cached API clients (e.g., after re-authentication)."""
    global _cached_admin_client, _cached_admin_alpha_client
    global _cached_data_client, _cached_data_alpha_client
    _cached_admin_client = None
    _cached_admin_alpha_client = None
    _cached_data_client = None
    _cached_data_alpha_client = None
