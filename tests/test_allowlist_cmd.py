"""Tests for `ga allowlist show`."""

import json
import time

import pytest
from googleapiclient.http import HttpMockSequence
from typer.testing import CliRunner

from ga_cli.api import client as client_mod
from ga_cli.api.allowlist_guard import principal_of, reset_caches
from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app
from ga_cli.utils.errors import ALLOWLIST_CONFIG_HINT

runner = CliRunner()

SUMMARIES = {
    "accountSummaries": [
        {
            "account": "accounts/10",
            "displayName": "Client A",
            "propertySummaries": [
                {"property": "properties/1", "displayName": "Shop A"},
                {"property": "properties/3", "displayName": "Blog A"},
            ],
        },
        {
            "account": "accounts/20",
            "displayName": "Client B",
            "propertySummaries": [{"property": "properties/2", "displayName": "Shop B"}],
        },
    ]
}


class FakeCreds:
    refresh_token = "refresh-token"
    token = "t"

    def before_request(self, request, method, url, headers):
        headers["authorization"] = "Bearer t"


@pytest.fixture
def api(monkeypatch):
    """Serve accountSummaries from a mock http; returns the mock so tests can count calls."""
    inner = HttpMockSequence([({"status": "200"}, json.dumps(SUMMARIES))])
    monkeypatch.setattr(client_mod, "_get_credentials", lambda: FakeCreds())
    monkeypatch.setattr(client_mod, "build_http", lambda: inner)
    reset_caches()
    yield inner
    reset_caches()


def _show(*args):
    return runner.invoke(app, ["allowlist", "show", *args])


class TestShowDisabled:
    def test_disabled_json_and_no_api_call(self, monkeypatch):
        monkeypatch.setattr(
            client_mod, "_get_credentials", lambda: pytest.fail("no API call expected")
        )
        result = _show("-o", "json")
        assert result.exit_code == 0
        assert json.loads(result.stdout) == {"enabled": False}


class TestShowEnabled:
    def test_json_report(self, api, monkeypatch):
        save_config(UserConfig(allowed_account_ids=["10"]))
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "1,2,99")
        result = _show("-o", "json")
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["enabled"] is True
        assert data["sources"] == {
            "config": {"accounts": ["10"], "properties": None},
            "env": {"accounts": None, "properties": ["1", "2", "99"]},
        }
        # Intersection: env lists properties only, so no account-level allow
        assert data["effective"]["accounts"] == []
        # 2 is in account 20 (not allowed by config); 99 isn't visible and not in config
        assert data["effective"]["properties"] == [
            {"id": "1", "account": "10", "displayName": "Shop A"},
        ]
        assert data["cache"]["age_seconds"] >= 0
        assert data["cache"]["fetched_at"].endswith("Z")
        assert len(api.request_sequence) == 1

    def test_listed_but_not_visible_property(self, api, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "1,99")
        data = json.loads(_show("-o", "json").stdout)
        assert data["effective"]["properties"] == [
            {"id": "1", "account": "10", "displayName": "Shop A"},
            {"id": "99", "account": None, "displayName": None},
        ]

    def test_fresh_cache_makes_no_call(self, api, tmp_path, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "10")
        (tmp_path / "allowlist-cache.json").write_text(json.dumps({"entries": {
            principal_of(FakeCreds()): {
                "fetched_at": int(time.time()) - 60,
                "properties": {"1": "10"},
                "names": {"1": "Shop A"},
            },
        }}))
        data = json.loads(_show("-o", "json").stdout)
        assert data["effective"]["properties"] == [
            {"id": "1", "account": "10", "displayName": "Shop A"}]
        assert 60 <= data["cache"]["age_seconds"] < 120
        assert api.request_sequence == []

    def test_stale_cache_is_refreshed(self, api, tmp_path, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "10")
        (tmp_path / "allowlist-cache.json").write_text(json.dumps({"entries": {
            principal_of(FakeCreds()): {
                "fetched_at": int(time.time()) - 7200,
                "properties": {"1": "10"},
            },
        }}))
        data = json.loads(_show("-o", "json").stdout)
        assert [p["id"] for p in data["effective"]["properties"]] == ["1", "3"]
        assert len(api.request_sequence) == 1

    def test_table_output(self, api, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "10")
        result = _show()
        assert result.exit_code == 0, result.output
        assert "10 (Client A)" in result.stdout
        assert "Shop A" in result.stdout and "Blog A" in result.stdout
        assert "Shop B" not in result.stdout

    def test_malformed_allowlist_exits_5(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "x")
        result = _show("-o", "json")
        assert result.exit_code == 5
        err = json.loads(result.stderr)
        assert err["category"] == "allowlist_error"
        # Not ALLOWLIST_HINT: it would send the agent back to this same failing command
        assert err["hint"] == ALLOWLIST_CONFIG_HINT

    def test_unreadable_config_exits_5(self, tmp_path):
        (tmp_path / "config.json").write_text('{"allowed_account_ids": ["10"],}')
        result = _show("-o", "json")
        assert result.exit_code == 5
        err = json.loads(result.stderr)
        assert err["category"] == "allowlist_error"
        assert err["resource"] == "config.json"
        assert err["hint"] == ALLOWLIST_CONFIG_HINT


def _write_profile_config(root, profile, data):
    path = root / "profiles" / profile / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def _show_in(profile, *args):
    return runner.invoke(app, ["--profile", profile, "allowlist", "show", *args])


class TestShowProfiles:
    """The root config.json is the fence for every profile; a profile narrows it."""

    def test_default_profile_has_no_profile_source(self, api):
        save_config(UserConfig(allowed_account_ids=["10"]))
        data = json.loads(_show("-o", "json").stdout)
        assert list(data) == ["enabled", "profile", "sources", "effective", "cache"]
        assert data["profile"] == "default"
        assert data["sources"] == {
            "config": {"accounts": ["10"], "properties": None},
            "env": None,
        }

    def test_named_profile_json(self, api, tmp_path):
        save_config(UserConfig(allowed_account_ids=["10", "20"]))
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["10"]})
        result = _show_in("client-a", "-o", "json")
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["enabled"] is True
        assert data["profile"] == "client-a"
        assert data["sources"] == {
            "config": {"accounts": ["10", "20"], "properties": None},
            "profile": {"accounts": ["10"], "properties": None},
            "env": None,
        }
        assert list(data["sources"]) == ["config", "profile", "env"]
        assert data["effective"]["accounts"] == ["10"]
        assert [p["id"] for p in data["effective"]["properties"]] == ["1", "3"]

    def test_named_profile_without_own_keys(self, api, tmp_path):
        save_config(UserConfig(allowed_account_ids=["20"]))
        _write_profile_config(tmp_path, "client-a", {"default_property_id": "2"})
        result = _show_in("client-a", "-o", "json")
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["sources"]["profile"] is None
        assert data["effective"]["accounts"] == ["20"]
        assert [p["id"] for p in data["effective"]["properties"]] == ["2"]

    def test_named_profile_guard_off(self, tmp_path, monkeypatch):
        (tmp_path / "profiles" / "client-a").mkdir(parents=True)
        monkeypatch.setattr(
            client_mod, "_get_credentials", lambda: pytest.fail("no API call expected")
        )
        result = _show_in("client-a", "-o", "json")
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {"enabled": False}

    def test_named_profile_table(self, api, tmp_path):
        save_config(UserConfig(allowed_account_ids=["10", "20"]))
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["10"]})
        result = _show_in("client-a")
        assert result.exit_code == 0, result.output
        text = " ".join(result.stdout.split())
        assert "client-a" in text
        assert "accounts 10, 20" in text
        assert "Profile File" in text  # key/value tables title-case the keys
        assert "Shop A" in text and "Shop B" not in text

    def test_default_profile_table_has_no_profile_file_row(self, api):
        save_config(UserConfig(allowed_account_ids=["10"]))
        result = _show()
        assert result.exit_code == 0, result.output
        assert "Profile File" not in result.stdout


class TestShowUnknownProfile:
    """A typo in --profile exits 2 before any credential or network access."""

    @pytest.fixture(autouse=True)
    def no_network(self, monkeypatch):
        monkeypatch.setattr(
            client_mod, "_get_credentials", lambda: pytest.fail("no credentials expected")
        )
        monkeypatch.setattr(client_mod, "build_http", lambda: pytest.fail("no http expected"))

    def _assert_not_found(self, result, tmp_path):
        assert result.exit_code == 2
        assert "Profile 'clinet-a' does not exist" in result.output
        assert not (tmp_path / "profiles" / "clinet-a").exists()

    def test_guard_on(self, tmp_path):
        save_config(UserConfig(allowed_account_ids=["10"]))
        self._assert_not_found(_show_in("clinet-a"), tmp_path)

    def test_guard_off(self, tmp_path):
        self._assert_not_found(_show_in("clinet-a"), tmp_path)

    def test_json_error(self, tmp_path):
        result = _show_in("clinet-a", "-o", "json")
        self._assert_not_found(result, tmp_path)
        assert json.loads(result.stderr)["category"] == "auth_error"

    def test_unreadable_root_still_exits_2(self, tmp_path):
        (tmp_path / "config.json").write_text("{oops")
        self._assert_not_found(_show_in("clinet-a", "-o", "json"), tmp_path)

    def test_via_env_var(self, tmp_path, monkeypatch):
        save_config(UserConfig(allowed_account_ids=["10"]))
        monkeypatch.setenv("GA_CLI_PROFILE", "clinet-a")
        self._assert_not_found(_show(), tmp_path)


class TestShowUnreadableProfileConfig:
    def test_unreadable_profile_file_exits_5(self, tmp_path):
        _write_profile_config(tmp_path, "client-a", "{oops")
        result = _show_in("client-a", "-o", "json")
        assert result.exit_code == 5
        assert json.loads(result.stderr)["resource"] == "profiles/client-a/config.json"

    def test_unreadable_root_exits_5_in_named_profile(self, tmp_path):
        (tmp_path / "config.json").write_text("{oops")
        _write_profile_config(tmp_path, "client-a", {})
        result = _show_in("client-a", "-o", "json")
        assert result.exit_code == 5
        assert json.loads(result.stderr)["resource"] == "config.json"
