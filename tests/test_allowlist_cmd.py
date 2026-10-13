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
        (tmp_path / "allowlist-cache.json").write_text(json.dumps({
            "principal": principal_of(FakeCreds()),
            "fetched_at": int(time.time()) - 60,
            "properties": {"1": "10"},
            "names": {"1": "Shop A"},
        }))
        data = json.loads(_show("-o", "json").stdout)
        assert data["effective"]["properties"] == [
            {"id": "1", "account": "10", "displayName": "Shop A"}]
        assert 60 <= data["cache"]["age_seconds"] < 120
        assert api.request_sequence == []

    def test_stale_cache_is_refreshed(self, api, tmp_path, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "10")
        (tmp_path / "allowlist-cache.json").write_text(json.dumps({
            "principal": principal_of(FakeCreds()),
            "fetched_at": int(time.time()) - 7200,
            "properties": {"1": "10"},
        }))
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
        assert json.loads(result.stderr)["category"] == "allowlist_error"

    def test_unreadable_config_exits_5(self, tmp_path):
        (tmp_path / "config.json").write_text('{"allowed_account_ids": ["10"],}')
        result = _show("-o", "json")
        assert result.exit_code == 5
        err = json.loads(result.stderr)
        assert err["category"] == "allowlist_error"
        assert err["resource"] == "config.json"
