"""Cross-slice allowlist tests: profiles, the global fence, the per-profile cache, the
``hint`` field and audience exports, end to end through the CLI.

Each test drives ``ga_cli.main.app``, so ``--profile`` / ``GA_CLI_PROFILE`` select the
profile in ``main``. Credentials resolve from each profile's own stored OAuth token (a
fresh one, so nothing refreshes), and only the HTTP transport (``build_http``) is mocked.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.http import HttpMockSequence
from typer.testing import CliRunner

from ga_cli.api import client as client_mod
from ga_cli.api.allowlist_guard import principal_of
from ga_cli.config.constants import OAUTH_SCOPES
from ga_cli.main import app
from ga_cli.utils.errors import ALLOWLIST_HINT
from tests.test_allowlist_guard import SUMMARIES_RESP, _resp, _sent

runner = CliRunner()

PROFILE = "x"
CACHE = "allowlist-cache.json"
REPORT = ["reports", "run", "-o", "json"]
RUN_REPORT = "beta/properties/{}:runReport"

# How a command selects profile X: the root option, or the env var
SELECT_X = pytest.mark.parametrize(
    "select,env",
    [(["--profile", PROFILE], None), ([], {"GA_CLI_PROFILE": PROFILE})],
    ids=["flag", "env"],
)


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _save_oauth(directory, name):
    """What `ga auth login` stores; the token is fresh, so nothing is refreshed."""
    expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    _write_json(directory / "credentials.json", {
        "token": f"{name}-token",
        "refresh_token": f"{name}-refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "cid",
        "client_secret": "secret",
        "scopes": OAUTH_SCOPES,
        "expiry": expiry.isoformat(),
    })


def _principal(name):
    return principal_of(Credentials(token=None, refresh_token=f"{name}-refresh"))


@pytest.fixture
def root(isolated_config_dir):
    return isolated_config_dir


@pytest.fixture
def profile_dir(isolated_config_dir):
    return isolated_config_dir / "profiles" / PROFILE


@pytest.fixture(autouse=True)
def _logins(root, profile_dir):
    """The default profile and profile X each have their own login (no fallback)."""
    _save_oauth(root, "default")
    _save_oauth(profile_dir, PROFILE)


def _allow(directory, accounts=None, properties=None):
    """Write allowlist keys into ``directory/config.json`` (``config set`` needs a TTY)."""
    keys = {}
    if accounts is not None:
        keys["allowed_account_ids"] = accounts
    if properties is not None:
        keys["allowed_property_ids"] = properties
    _write_json(directory / "config.json", keys)


@pytest.fixture
def invoke(monkeypatch):
    """Run the CLI over a fresh mock HTTP layer; returns (result, inner)."""

    def run(args, responses=(), env=None):
        inner = HttpMockSequence(list(responses))
        monkeypatch.setattr(client_mod, "build_http", lambda: inner)
        return runner.invoke(app, args, env=env), inner

    return run


def _denied(result, resource):
    """Assert an exit-5 JSON error for ``resource``; returns the payload."""
    assert result.exit_code == 5, result.output
    payload = json.loads(result.stderr)
    assert payload["error"] is True
    assert payload["exit_code"] == 5
    assert payload["category"] == "allowlist_error"
    assert payload["resource"] == resource
    assert payload["hint"] == ALLOWLIST_HINT
    assert ALLOWLIST_HINT not in payload["message"]
    return payload


def _auth_header(inner, i=0):
    return inner.request_sequence[i][3]["authorization"]


class TestRootFenceAcrossProfiles:
    """The root config.json allowlist applies to a named profile without its own keys."""

    @SELECT_X
    def test_outside_fence_exits_5_and_sends_nothing(self, root, invoke, select, env):
        _allow(root, properties=["1"])

        result, inner = invoke([*select, *REPORT, "-p", "999"], env=env)

        payload = _denied(result, "properties/999")
        assert payload["message"] == (
            "properties/999 is not on the allowlist (config: properties 1)"
        )
        assert inner.request_sequence == []

    @SELECT_X
    def test_inside_fence_sent_with_profile_credentials(self, root, invoke, select, env):
        _allow(root, properties=["1"])

        result, inner = invoke([*select, *REPORT, "-p", "1"], [_resp()], env=env)

        assert result.exit_code == 0, result.output
        assert _sent(inner) == [("POST", RUN_REPORT.format(1))]
        assert _auth_header(inner) == f"Bearer {PROFILE}-token"


class TestProfileNarrowsFence:
    """A named profile's own keys narrow the fence for that profile only."""

    def test_property_outside_profile_denied(self, root, profile_dir, invoke):
        _allow(root, properties=["1", "2"])
        _allow(profile_dir, properties=["1"])

        result, inner = invoke(["--profile", PROFILE, *REPORT, "-p", "2"])

        payload = _denied(result, "properties/2")
        assert payload["message"] == (
            "properties/2 is not on the allowlist "
            f"(config: properties 1, 2 | profile {PROFILE}: properties 1)"
        )
        assert inner.request_sequence == []

    def test_same_property_allowed_in_default(self, root, profile_dir, invoke):
        _allow(root, properties=["1", "2"])
        _allow(profile_dir, properties=["1"])

        result, inner = invoke([*REPORT, "-p", "2"], [_resp()])

        assert result.exit_code == 0, result.output
        assert _sent(inner) == [("POST", RUN_REPORT.format(2))]
        assert _auth_header(inner) == "Bearer default-token"

    def test_default_client_not_reused_under_profile(self, root, profile_dir, invoke):
        """Both runs share a process: the default profile's cached client must not serve X."""
        _allow(root, properties=["1", "2"])
        _allow(profile_dir, properties=["1"])

        allowed, default_inner = invoke([*REPORT, "-p", "2"], [_resp()])
        denied, profile_inner = invoke(["--profile", PROFILE, *REPORT, "-p", "2"])

        assert allowed.exit_code == 0, allowed.output
        _denied(denied, "properties/2")
        assert _sent(default_inner) == [("POST", RUN_REPORT.format(2))]
        assert profile_inner.request_sequence == []

    def test_account_narrowing_denies_after_lookup(self, root, profile_dir, invoke):
        # Property 2 sits in account 20 (SUMMARIES), which the profile leaves out
        _allow(root, accounts=["10", "20"])
        _allow(profile_dir, accounts=["10"])

        result, inner = invoke(["--profile", PROFILE, *REPORT, "-p", "2"], [SUMMARIES_RESP])

        _denied(result, "properties/2")
        assert _sent(inner) == [("GET", "beta/accountSummaries")]


class TestCachePerProfile:
    """A property → account lookup is cached in the active profile's directory."""

    def test_lookup_under_profile_writes_profile_cache_only(self, root, profile_dir, invoke):
        _allow(root, accounts=["10"])

        result, inner = invoke(
            ["--profile", PROFILE, *REPORT, "-p", "1"], [SUMMARIES_RESP, _resp()]
        )

        assert result.exit_code == 0, result.output
        assert _sent(inner) == [("GET", "beta/accountSummaries"), ("POST", RUN_REPORT.format(1))]
        data = json.loads((profile_dir / CACHE).read_text())["entries"]
        assert list(data) == [_principal(PROFILE)]
        assert data[_principal(PROFILE)]["properties"] == {"1": "10", "3": "10", "2": "20"}
        assert not (root / CACHE).exists()

    def test_default_profile_keeps_its_own_cache(self, root, profile_dir, invoke):
        """In one process, default refetches with its own login and leaves X's file alone."""
        _allow(root, accounts=["10"])
        first, _ = invoke(["--profile", PROFILE, *REPORT, "-p", "1"], [SUMMARIES_RESP, _resp()])
        assert first.exit_code == 0, first.output
        profile_cache = (profile_dir / CACHE).read_text()

        result, inner = invoke([*REPORT, "-p", "1"], [SUMMARIES_RESP, _resp()])

        assert result.exit_code == 0, result.output
        assert _sent(inner) == [("GET", "beta/accountSummaries"), ("POST", RUN_REPORT.format(1))]
        assert _auth_header(inner) == "Bearer default-token"
        assert list(json.loads((root / CACHE).read_text())["entries"]) == [_principal("default")]
        assert (profile_dir / CACHE).read_text() == profile_cache


CREATE = ["audience-exports", "create", "--dimensions", "deviceId", "-o", "json"]


class TestAudienceExportsUnderProfile:
    @pytest.mark.parametrize("root_ids,profile_ids", [
        (["1"], None),
        (["1", "2"], ["1"]),
    ], ids=["fence", "profile-narrows"])
    @pytest.mark.parametrize("args", [
        ["-p", "2", "--audience-id", "5"],
        ["-p", "1", "--audience-id", "properties/2/audiences/5"],
    ], ids=["parent", "body-audience"])
    def test_blocked_create_exits_5_and_sends_nothing(
        self, root, profile_dir, invoke, root_ids, profile_ids, args
    ):
        _allow(root, properties=root_ids)
        if profile_ids is not None:
            _allow(profile_dir, properties=profile_ids)

        result, inner = invoke(["--profile", PROFILE, *CREATE, *args])

        _denied(result, "properties/2")
        assert inner.request_sequence == []

    def test_allowed_create_is_sent(self, root, invoke):
        _allow(root, properties=["1"])
        operation = {"name": "operations/op1",
                     "response": {"name": "properties/1/audienceExports/7"}}

        result, inner = invoke(
            ["--profile", PROFILE, *CREATE, "-p", "1", "--audience-id", "5"], [_resp(operation)]
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["exportId"] == "7"
        assert _sent(inner) == [("POST", "beta/properties/1/audienceExports")]
        assert _auth_header(inner) == f"Bearer {PROFILE}-token"
