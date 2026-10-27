"""The allowlist's property → account cache is per profile (SPEC D2)."""

import json
import time
from unittest.mock import patch

from googleapiclient.http import HttpMockSequence
from typer.testing import CliRunner

from ga_cli.api import allowlist_guard
from ga_cli.api import client as client_mod
from ga_cli.api.allowlist_guard import cache_for, principal_of
from ga_cli.config.constants import get_allowlist_cache_path, set_active_profile
from ga_cli.main import app
from tests.test_allowlist_guard import SUMMARIES_RESP, FakeCreds, _al, _resp, guarded

runner = CliRunner()

CACHE = "allowlist-cache.json"


def _seed_cache(directory, marker):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CACHE
    path.write_text(json.dumps({"marker": marker}))
    return path


class TestCachePath:
    def test_default_profile_uses_root(self, isolated_config_dir):
        assert get_allowlist_cache_path() == isolated_config_dir / CACHE

    def test_named_profile_uses_profile_dir(self, isolated_config_dir):
        set_active_profile("x")
        assert get_allowlist_cache_path() == isolated_config_dir / "profiles" / "x" / CACHE

    def test_getter_does_not_create_directories(self, isolated_config_dir):
        set_active_profile("x")
        get_allowlist_cache_path()
        assert not (isolated_config_dir / "profiles").exists()


class TestAuthClearsOnlyActiveProfile:
    def _logout(self, *args):
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method", return_value=None),
            patch("ga_cli.commands.auth_cmd.get_auth_status",
                  return_value={"authenticated": False}),
        ):
            return runner.invoke(app, [*args, "auth", "logout"])

    def test_named_logout_keeps_root_cache(self, isolated_config_dir):
        root = _seed_cache(isolated_config_dir, "root")
        named = _seed_cache(isolated_config_dir / "profiles" / "x", "x")

        result = self._logout("--profile", "x")

        assert result.exit_code == 0, result.output
        assert not named.exists()
        assert json.loads(root.read_text()) == {"marker": "root"}

    def test_default_logout_keeps_named_cache(self, isolated_config_dir):
        root = _seed_cache(isolated_config_dir, "root")
        named = _seed_cache(isolated_config_dir / "profiles" / "x", "x")

        result = self._logout()

        assert result.exit_code == 0, result.output
        assert not root.exists()
        assert json.loads(named.read_text()) == {"marker": "x"}

    def test_named_service_account_login_keeps_root_cache(self, isolated_config_dir):
        root = _seed_cache(isolated_config_dir, "root")
        named = _seed_cache(isolated_config_dir / "profiles" / "x", "x")

        with patch(
            "ga_cli.commands.auth_cmd.login_with_service_account", return_value="sa@x.iam"
        ):
            result = runner.invoke(app, ["--profile", "x", "auth", "login", "-s", "/k.json"])

        assert result.exit_code == 0, result.output
        assert not named.exists()
        assert root.exists()


class TestInProcessCaches:
    def test_same_principal_two_profiles_get_separate_caches(self, isolated_config_dir):
        http = HttpMockSequence([])
        set_active_profile("a")
        cache_a = cache_for(FakeCreds(), http)
        set_active_profile("b")
        cache_b = cache_for(FakeCreds(), http)

        assert cache_a is not cache_b
        assert cache_a.principal == cache_b.principal
        assert cache_a.path == isolated_config_dir / "profiles" / "a" / CACHE
        assert cache_b.path == isolated_config_dir / "profiles" / "b" / CACHE

    def test_same_profile_reuses_cache(self):
        http = HttpMockSequence([])
        assert cache_for(FakeCreds(), http) is cache_for(FakeCreds(), http)

    def test_cache_path_is_frozen_at_creation(self, isolated_config_dir):
        set_active_profile("a")
        cache = cache_for(FakeCreds(), HttpMockSequence([]))
        set_active_profile("b")

        assert cache.path == isolated_config_dir / "profiles" / "a" / CACHE

    def test_switching_profile_resets_caches(self):
        cache_for(FakeCreds(), HttpMockSequence([]))

        result = runner.invoke(app, ["--profile", "x", "config", "path"])

        assert result.exit_code == 0, result.output
        assert allowlist_guard._caches == {}

    def test_same_profile_keeps_caches(self):
        cache = cache_for(FakeCreds(), HttpMockSequence([]))

        result = runner.invoke(app, ["config", "path"])

        assert result.exit_code == 0, result.output
        assert cache_for(FakeCreds(), HttpMockSequence([])) is cache


class TestPersistence:
    def test_fetched_map_written_to_profile_dir(self, isolated_config_dir):
        set_active_profile("x")
        c, inner = guarded(_al(accounts={"10"}), [SUMMARIES_RESP, _resp()])

        c.properties().get(name="properties/3").execute()

        data = json.loads((isolated_config_dir / "profiles" / "x" / CACHE).read_text())
        assert data["entries"][principal_of(FakeCreds())]["properties"] == {
            "1": "10", "3": "10", "2": "20"}
        assert not (isolated_config_dir / CACHE).exists()


class TestProfilesInOneProcess:
    """Several invocations share a process under CliRunner, as in the tests."""

    def _api(self, monkeypatch, responses):
        inner = HttpMockSequence(responses)
        monkeypatch.setattr(client_mod, "_get_credentials", lambda: FakeCreds())
        monkeypatch.setattr(client_mod, "build_http", lambda: inner)
        return inner

    def _show(self, profile):
        result = runner.invoke(app, ["--profile", profile, "allowlist", "show", "-o", "json"])
        assert result.exit_code == 0, result.output
        return json.loads(result.stdout)

    def test_second_profile_refetches(self, isolated_config_dir, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "10")
        for name in ("a", "b"):
            (isolated_config_dir / "profiles" / name).mkdir(parents=True)
        inner = self._api(monkeypatch, [SUMMARIES_RESP, SUMMARIES_RESP])

        self._show("a")
        self._show("b")

        assert len(inner.request_sequence) == 2
        for name in ("a", "b"):
            assert (isolated_config_dir / "profiles" / name / CACHE).exists()
        assert not (isolated_config_dir / CACHE).exists()

    def test_second_profile_loads_its_own_file(self, isolated_config_dir, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "10")
        (isolated_config_dir / "profiles" / "a").mkdir(parents=True)
        b_cache = isolated_config_dir / "profiles" / "b" / CACHE
        b_cache.parent.mkdir(parents=True)
        b_cache.write_text(json.dumps({"entries": {
            principal_of(FakeCreds()): {
                "fetched_at": int(time.time()),
                "properties": {"7": "10"},
                "names": {"7": "Only in b"},
            },
        }}))
        inner = self._api(monkeypatch, [SUMMARIES_RESP])

        a = self._show("a")
        b = self._show("b")

        assert len(inner.request_sequence) == 1  # a fetched; b read its own file
        assert {p["id"] for p in a["effective"]["properties"]} == {"1", "3"}
        assert b["effective"]["properties"] == [
            {"id": "7", "account": "10", "displayName": "Only in b"}]
