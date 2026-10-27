"""gcloud ADC credentials under the allowlist guard (SPEC D3)."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
from google.auth import compute_engine, identity_pool, impersonated_credentials
from google.oauth2 import credentials as oauth2_credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import HttpMockSequence

from ga_cli.api import client as client_mod
from ga_cli.api.allowlist_guard import AllowlistHttp, Route, classify_route, principal_of
from ga_cli.api.client import get_admin_client, get_last_auth_method
from ga_cli.auth.credentials import load_credentials
from ga_cli.config.constants import OAUTH_SCOPES, get_allowlist_cache_path, get_credentials_path
from ga_cli.utils.errors import AllowlistError
from tests.test_allowlist_guard import SUMMARIES_RESP, _al, _resp

SA = "sa@p.iam.gserviceaccount.com"
WIF_SA = "wif@p.iam.gserviceaccount.com"
IAM_URL = "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{}:generateAccessToken"
WIF_AUDIENCE = (
    "//iam.googleapis.com/projects/1/locations/global/workloadIdentityPools/p/providers/gh"
)

IAM_RESP = _resp({"accessToken": "minted", "expireTime": "2099-01-01T00:00:00Z"})
STS_RESP = _resp({
    "access_token": "minted",
    "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
    "token_type": "Bearer",
    "expires_in": 3600,
})
_JSON = {"status": "200", "content-type": "application/json"}
GCE_INFO_RESP = (_JSON, json.dumps({"email": SA, "scopes": OAUTH_SCOPES}))
GCE_TOKEN_RESP = (_JSON, json.dumps({"access_token": "minted", "expires_in": 3600}))
PROPERTY_RESP = _resp({"name": "properties/1"})


def _oauth(refresh_token):
    return "oauth:" + hashlib.sha256(refresh_token.encode()).hexdigest()[:16]


def _impersonated(source=None):
    """What ``gcloud auth application-default login --impersonate-service-account`` yields."""
    return impersonated_credentials.Credentials(
        source_credentials=source or oauth2_credentials.Credentials(token="source-token"),
        target_principal=SA,
        target_scopes=OAUTH_SCOPES,
    )


def _external_account(tmp_path, impersonate):
    """A Workload Identity Federation config reading its subject token from a file."""
    token_file = tmp_path / "subject-token"
    token_file.write_text("subject-jwt")
    info = {
        "type": "external_account",
        "audience": WIF_AUDIENCE,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": {"file": str(token_file)},
    }
    if impersonate:
        info["service_account_impersonation_url"] = IAM_URL.format(WIF_SA)
    return identity_pool.Credentials.from_info(info, scopes=OAUTH_SCOPES)


def _compute_engine(**kwargs):
    # A preset universe domain keeps googleapiclient from asking the real metadata server
    return compute_engine.Credentials(universe_domain="googleapis.com", **kwargs)


def _with_valid_token(creds):
    """Mark ``creds`` as already holding an unexpired token, so nothing refreshes."""
    creds.token = "valid"
    # google-auth compares expiry as naive UTC
    creds.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    return creds


def _guarded(creds, responses, allowlist):
    """A real admin client over AllowlistHttp over HttpMockSequence; returns (client, inner)."""
    inner = HttpMockSequence(responses)
    http = AllowlistHttp(creds, http=inner, allowlist=allowlist)
    return build("analyticsadmin", "v1beta", http=http), inner


@pytest.fixture(autouse=True)
def _no_trust_boundary_lookup(monkeypatch):
    # When enabled, google-auth adds a lookup request to every refresh
    monkeypatch.delenv("GOOGLE_AUTH_TRUST_BOUNDARY_ENABLED", raising=False)


def _enable_adc(no_gcloud_adc, creds):
    no_gcloud_adc.side_effect = None
    no_gcloud_adc.return_value = (creds, "proj")


# ---------------------------------------------------------------------------
# principal_of: one test per SPEC D3 row
# ---------------------------------------------------------------------------
class TestPrincipalOf:
    def test_service_account_key(self):
        # Real class; a stub signer stands in for the RSA key
        creds = service_account.Credentials(
            MagicMock(), SA, "https://oauth2.googleapis.com/token"
        )
        assert principal_of(creds) == SA

    def test_stored_oauth_token(self):
        get_credentials_path().write_text(json.dumps({
            "token": "t", "refresh_token": "stored-refresh", "client_id": "c",
            "client_secret": "s",
        }))
        assert principal_of(load_credentials()) == _oauth("stored-refresh")

    def test_adc_authorized_user(self):
        creds = oauth2_credentials.Credentials.from_authorized_user_info({
            "type": "authorized_user",
            "client_id": "c.apps.googleusercontent.com",
            "client_secret": "s",
            "refresh_token": "gcloud-refresh",
        }, scopes=OAUTH_SCOPES)
        assert principal_of(creds) == _oauth("gcloud-refresh")

    def test_adc_impersonated_is_the_target_not_the_source(self):
        source = oauth2_credentials.Credentials(token="t", refresh_token="user-refresh")
        assert principal_of(_impersonated(source)) == SA

    def test_adc_external_account_with_impersonation(self, tmp_path):
        assert principal_of(_external_account(tmp_path, impersonate=True)) == WIF_SA

    def test_adc_external_account_without_impersonation(self, tmp_path):
        assert principal_of(_external_account(tmp_path, impersonate=False)) is None

    def test_compute_engine_before_refresh(self):
        creds = _compute_engine()
        assert creds.service_account_email == "default"
        assert principal_of(creds) is None

    def test_compute_engine_with_known_email(self):
        assert principal_of(_compute_engine(service_account_email=SA)) == SA


# ---------------------------------------------------------------------------
# ADC credentials reach the guard
# ---------------------------------------------------------------------------
class TestAdcClient:
    def test_admin_client_is_built_on_allowlist_http(self, no_gcloud_adc, monkeypatch):
        creds = _impersonated()
        _enable_adc(no_gcloud_adc, creds)
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "1")  # no allowlist, no guard (#44)
        http = get_admin_client()._http
        assert isinstance(http, AllowlistHttp)
        assert http.credentials is creds
        assert get_last_auth_method() == "adc"
        no_gcloud_adc.assert_called_once_with(scopes=OAUTH_SCOPES)

    def test_adc_request_is_checked_and_its_token_minted(self, no_gcloud_adc, monkeypatch):
        _enable_adc(no_gcloud_adc, _impersonated())
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "1")
        inner = HttpMockSequence([IAM_RESP, PROPERTY_RESP])
        monkeypatch.setattr(client_mod, "build_http", lambda: inner)

        admin = get_admin_client()
        assert admin.properties().get(name="properties/1").execute() == {"name": "properties/1"}
        with pytest.raises(AllowlistError):
            admin.properties().get(name="properties/2").execute()
        assert [(m, u.split("?")[0]) for u, m, _b, _h in inner.request_sequence] == [
            ("POST", IAM_URL.format(SA)),
            ("GET", "https://analyticsadmin.googleapis.com/v1beta/properties/1"),
        ]


# ---------------------------------------------------------------------------
# Token refresh goes through the inner http, never the guard
# ---------------------------------------------------------------------------
REFRESH_CASES = [
    ("impersonated", lambda tmp: _impersonated(), [IAM_RESP]),
    ("external_account", lambda tmp: _external_account(tmp, impersonate=False), [STS_RESP]),
    ("external_account_impersonated",
     lambda tmp: _external_account(tmp, impersonate=True), [STS_RESP, IAM_RESP]),
    ("compute_engine", lambda tmp: _compute_engine(), [GCE_INFO_RESP, GCE_TOKEN_RESP]),
]


class TestTokenRefreshNotGuarded:
    @pytest.mark.parametrize(
        "make,token_responses", [c[1:] for c in REFRESH_CASES], ids=[c[0] for c in REFRESH_CASES]
    )
    def test_token_requests_bypass_the_guard(self, tmp_path, make, token_responses):
        c, inner = _guarded(
            make(tmp_path), token_responses + [PROPERTY_RESP], _al(properties={"1"})
        )
        assert c.properties().get(name="properties/1").execute() == {"name": "properties/1"}

        *token_requests, (api_uri, _m, _b, api_headers) = inner.request_sequence
        assert len(token_requests) == len(token_responses)
        for uri, method, _body, _headers in token_requests:
            # The guard would have denied each of these as an unexpected host
            assert classify_route(method, uri) is Route.UNKNOWN_HOST, uri
        assert urlsplit(api_uri).path == "/v1beta/properties/1"
        assert api_headers["authorization"] == "Bearer minted"

    def test_401_refresh_retry(self):
        creds = _with_valid_token(_impersonated())
        c, inner = _guarded(
            creds, [_resp(status="401"), IAM_RESP, PROPERTY_RESP], _al(properties={"1"})
        )
        assert c.properties().get(name="properties/1").execute() == {"name": "properties/1"}
        sent = [(m, u.split("?")[0], h.get("authorization"))
                for u, m, _b, h in inner.request_sequence]
        api = "https://analyticsadmin.googleapis.com/v1beta/properties/1"
        assert sent == [
            ("GET", api, "Bearer valid"),
            ("POST", IAM_URL.format(SA), "Bearer source-token"),
            ("GET", api, "Bearer minted"),
        ]


# ---------------------------------------------------------------------------
# An unknown principal keeps the map in memory only; the guard still holds
# ---------------------------------------------------------------------------
UNKNOWN_PRINCIPAL_CASES = [
    ("compute_engine_default", lambda tmp: _compute_engine()),
    ("external_account", lambda tmp: _external_account(tmp, impersonate=False)),
]


class TestUnknownPrincipal:
    @pytest.mark.parametrize(
        "make", [c[1] for c in UNKNOWN_PRINCIPAL_CASES], ids=[c[0] for c in UNKNOWN_PRINCIPAL_CASES]
    )
    def test_no_disk_cache_and_still_enforced(self, tmp_path, make):
        creds = _with_valid_token(make(tmp_path))
        c, inner = _guarded(creds, [SUMMARIES_RESP, _resp()], _al(accounts={"10"}))

        c.properties().get(name="properties/1").execute()  # needs the property → account map
        assert list(tmp_path.rglob("*allowlist-cache*")) == []
        assert principal_of(creds) is None

        with pytest.raises(AllowlistError):
            c.properties().get(name="properties/2").execute()  # account 20
        with pytest.raises(AllowlistError) as exc:
            c.properties().get(name="properties/999").execute()
        assert "not visible to these credentials" in str(exc.value)
        assert len(inner.request_sequence) == 2  # one lookup, one allowed call

    def test_known_principal_writes_disk_cache(self):
        # The control for the test above: same flow, an email the metadata server reported
        creds = _with_valid_token(_compute_engine(service_account_email=SA))
        c, _ = _guarded(creds, [SUMMARIES_RESP, _resp()], _al(accounts={"10"}))
        c.properties().get(name="properties/1").execute()
        assert json.loads(get_allowlist_cache_path().read_text())["principal"] == SA
