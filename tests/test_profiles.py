"""Tests for named profiles: selection, path routing, implicit creation.

A profile is a config namespace. The default profile is the config root
itself (zero migration); a named profile lives under ``profiles/<name>/``.
"""

import json
import platform
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ga_cli.config.constants import (
    DEFAULT_PROFILE,
    PROFILE_NAME_RE,
    get_active_profile,
    get_auth_method_path,
    get_chat_sessions_path,
    get_client_secret_path,
    get_config_path,
    get_credentials_path,
    get_profile_dir,
    get_profiles_root,
    get_update_check_path,
    is_named_profile,
    list_profiles,
    profile_exists,
    set_active_profile,
)
from ga_cli.main import app

runner = CliRunner()

INVALID_NAMES = ["..", ".", ".hidden", "a/b", "-x", "_x", "has space", "a\\b", "a\n"]

PER_PROFILE_GETTERS = {
    "credentials.json": get_credentials_path,
    "config.json": get_config_path,
    "auth-method.json": get_auth_method_path,
    "chat-sessions.json": get_chat_sessions_path,
}

GLOBAL_GETTERS = {
    "client_secret.json": get_client_secret_path,
    "update-check.json": get_update_check_path,
}


def _write_config(directory, **values):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(values))


class TestProfileSelection:
    def test_contract_constants(self):
        assert DEFAULT_PROFILE == "default"
        assert PROFILE_NAME_RE.pattern == r"^[A-Za-z0-9][A-Za-z0-9._-]*$"

    def test_default_when_no_flag_or_env(self, isolated_config_dir):
        _write_config(isolated_config_dir, default_property_id="root-prop")

        result = runner.invoke(app, ["config", "get", "default_property_id"])

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "root-prop"
        assert get_active_profile() == DEFAULT_PROFILE

    def test_env_selects_profile(self, isolated_config_dir):
        _write_config(isolated_config_dir, default_property_id="root-prop")
        _write_config(isolated_config_dir / "profiles" / "env-prof", default_property_id="env")

        result = runner.invoke(
            app,
            ["config", "get", "default_property_id"],
            env={"GA_CLI_PROFILE": "env-prof"},
        )

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "env"
        assert get_active_profile() == "env-prof"

    def test_flag_selects_profile(self, isolated_config_dir):
        _write_config(isolated_config_dir / "profiles" / "flag-prof", default_property_id="flag")

        result = runner.invoke(
            app, ["--profile", "flag-prof", "config", "get", "default_property_id"]
        )

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "flag"
        assert get_active_profile() == "flag-prof"

    def test_flag_beats_env(self, isolated_config_dir):
        _write_config(isolated_config_dir / "profiles" / "env-prof", default_property_id="env")
        _write_config(isolated_config_dir / "profiles" / "flag-prof", default_property_id="flag")

        result = runner.invoke(
            app,
            ["--profile", "flag-prof", "config", "get", "default_property_id"],
            env={"GA_CLI_PROFILE": "env-prof"},
        )

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "flag"
        assert get_active_profile() == "flag-prof"

    def test_explicit_default_is_the_root(self, isolated_config_dir):
        _write_config(isolated_config_dir, default_property_id="root-prop")

        result = runner.invoke(
            app,
            ["--profile", "default", "config", "get", "default_property_id"],
            env={"GA_CLI_PROFILE": "env-prof"},
        )

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "root-prop"
        assert not is_named_profile()

    def test_empty_env_var_means_default(self, isolated_config_dir):
        _write_config(isolated_config_dir, default_property_id="root-prop")

        result = runner.invoke(
            app, ["config", "get", "default_property_id"], env={"GA_CLI_PROFILE": ""}
        )

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "root-prop"
        assert get_active_profile() == DEFAULT_PROFILE

    def test_invocation_without_profile_resets_to_default(self, isolated_config_dir):
        """CliRunner shares one process: a later bare call must not inherit a profile."""
        runner.invoke(app, ["--profile", "client-a", "config", "get"])
        assert get_active_profile() == "client-a"

        runner.invoke(app, ["config", "get"])

        assert get_active_profile() == DEFAULT_PROFILE

    @pytest.mark.parametrize("name", INVALID_NAMES)
    def test_invalid_flag_name_rejected(self, name, isolated_config_dir):
        result = runner.invoke(app, ["--profile", name, "config", "get"])

        assert result.exit_code == 1
        assert "Invalid profile name" in result.output
        assert get_active_profile() == DEFAULT_PROFILE
        assert not (isolated_config_dir / "profiles").exists()

    @pytest.mark.parametrize("name", ["..", ".hidden", "a/b", "-x"])
    def test_invalid_env_name_rejected(self, name):
        result = runner.invoke(app, ["config", "get"], env={"GA_CLI_PROFILE": name})

        assert result.exit_code == 1
        assert "Invalid profile name" in result.output

    def test_empty_flag_rejected(self):
        """An explicit empty --profile (e.g. an unset "$CLIENT") must not run as default."""
        result = runner.invoke(app, ["--profile", "", "config", "get"])

        assert result.exit_code == 1
        assert "Profile name cannot be empty" in result.output

    def test_invalid_name_does_not_run_the_command(self):
        with patch("ga_cli.commands.config_cmd.set_config_value") as mock_set:
            result = runner.invoke(
                app, ["--profile", "..", "config", "set", "default_property_id", "1"]
            )

        assert result.exit_code == 1
        mock_set.assert_not_called()


class TestSetActiveProfile:
    @pytest.mark.parametrize("name", [None, "", "default"])
    def test_none_empty_and_default_select_default(self, name):
        set_active_profile("client-a")

        set_active_profile(name)

        assert get_active_profile() == DEFAULT_PROFILE
        assert not is_named_profile()

    @pytest.mark.parametrize("name", ["client-a", "a", "A1", "client_b", "c.d", "9to5"])
    def test_valid_names(self, name):
        set_active_profile(name)

        assert get_active_profile() == name
        assert is_named_profile()

    @pytest.mark.parametrize("name", INVALID_NAMES)
    def test_invalid_names_raise_and_keep_previous(self, name):
        set_active_profile("client-a")

        with pytest.raises(ValueError, match="Invalid profile name"):
            set_active_profile(name)

        assert get_active_profile() == "client-a"


class TestProfilePaths:
    def test_default_profile_resolves_to_root(self, isolated_config_dir):
        """Regression guard: the default profile is today's layout (zero migration)."""
        assert get_profile_dir() == isolated_config_dir
        for filename, getter in PER_PROFILE_GETTERS.items():
            assert getter() == isolated_config_dir / filename

    def test_profiles_root(self, isolated_config_dir):
        assert get_profiles_root() == isolated_config_dir / "profiles"
        set_active_profile("client-a")
        assert get_profiles_root() == isolated_config_dir / "profiles"

    def test_named_profile_resolves_under_profiles(self, isolated_config_dir):
        set_active_profile("client-a")

        profile_dir = isolated_config_dir / "profiles" / "client-a"
        assert get_profile_dir() == profile_dir
        for filename, getter in PER_PROFILE_GETTERS.items():
            assert getter() == profile_dir / filename

    @pytest.mark.parametrize("profile", ["default", "client-a"])
    def test_global_files_stay_at_root(self, profile, isolated_config_dir):
        set_active_profile(profile)

        for filename, getter in GLOBAL_GETTERS.items():
            assert getter() == isolated_config_dir / filename

    def test_getters_do_not_create_directories(self, isolated_config_dir):
        set_active_profile("client-a")
        for getter in PER_PROFILE_GETTERS.values():
            getter()

        assert not (isolated_config_dir / "profiles").exists()


class TestImplicitCreation:
    def test_config_set_creates_profile(self, isolated_config_dir):
        result = runner.invoke(
            app, ["--profile", "x", "config", "set", "default_property_id", "1"]
        )

        assert result.exit_code == 0, result.output
        config_file = isolated_config_dir / "profiles" / "x" / "config.json"
        assert config_file.exists()
        assert json.loads(config_file.read_text())["default_property_id"] == "1"
        assert not (isolated_config_dir / "config.json").exists()

    def test_named_value_not_visible_to_default(self, isolated_config_dir):
        runner.invoke(app, ["--profile", "x", "config", "set", "default_property_id", "1"])

        result = runner.invoke(app, ["config", "get", "default_property_id"])

        assert result.exit_code == 1
        assert "not set" in result.output

        result = runner.invoke(app, ["config", "get"])
        assert result.exit_code == 0
        assert json.loads(result.output)["default_property_id"] is None

    def test_default_value_not_visible_to_named(self, isolated_config_dir):
        runner.invoke(app, ["config", "set", "default_property_id", "root-prop"])
        # Prime the in-memory cache under the default profile.
        assert runner.invoke(app, ["config", "get", "default_property_id"]).exit_code == 0

        result = runner.invoke(app, ["--profile", "x", "config", "get", "default_property_id"])

        assert result.exit_code == 1
        assert "not set" in result.output

    @pytest.mark.skipif(platform.system() == "Windows", reason="POSIX permissions")
    def test_save_credentials_creates_profile_with_0600(self, isolated_config_dir):
        from ga_cli.auth.credentials import save_credentials

        set_active_profile("x")
        creds = MagicMock(
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="cid",
            client_secret="secret",
            scopes=["openid"],
            expiry=None,
        )

        save_credentials(creds)

        creds_file = isolated_config_dir / "profiles" / "x" / "credentials.json"
        assert creds_file.exists()
        assert creds_file.stat().st_mode & 0o777 == 0o600
        assert json.loads(creds_file.read_text())["token"] == "tok"
        assert not (isolated_config_dir / "credentials.json").exists()

    def test_save_auth_method_creates_profile(self, isolated_config_dir):
        from ga_cli.auth.service_account import _save_auth_method

        set_active_profile("x")
        _save_auth_method({"method": "service-account"})

        assert (isolated_config_dir / "profiles" / "x" / "auth-method.json").exists()
        assert not (isolated_config_dir / "auth-method.json").exists()

    def test_chat_session_creates_profile(self, isolated_config_dir):
        from ga_cli.config.chat_session import load_session, save_session

        set_active_profile("x")
        save_session("123", "sess-1")

        assert (isolated_config_dir / "profiles" / "x" / "chat-sessions.json").exists()
        assert load_session("123") == "sess-1"

        set_active_profile(None)
        assert load_session("123") is None

    def test_auth_login_service_account_creates_profile(self, isolated_config_dir):
        key_file = isolated_config_dir / "keys" / "sa.json"
        key_file.parent.mkdir()
        key_file.write_text(
            json.dumps(
                {
                    "type": "service_account",
                    "private_key": "fake",
                    "client_email": "sa@proj.iam.gserviceaccount.com",
                }
            )
        )

        with patch(
            "ga_cli.auth.service_account.service_account.Credentials"
            ".from_service_account_file"
        ) as mock_from_file:
            mock_from_file.return_value = MagicMock()
            result = runner.invoke(
                app,
                ["--profile", "x", "auth", "login", "--service-account", str(key_file)],
            )

        assert result.exit_code == 0, result.output
        auth_file = isolated_config_dir / "profiles" / "x" / "auth-method.json"
        assert auth_file.exists()
        saved = json.loads(auth_file.read_text())
        assert saved["service_account_email"] == "sa@proj.iam.gserviceaccount.com"
        assert not (isolated_config_dir / "auth-method.json").exists()
        # The key file is referenced by path, never copied into the profile.
        assert key_file.exists()
        assert not (isolated_config_dir / "profiles" / "x" / "sa.json").exists()


class TestClientCacheIsolation:
    def _prime_admin_client(self):
        from ga_cli.api import client

        with (
            patch("ga_cli.api.client._get_credentials", return_value=MagicMock()),
            patch("ga_cli.api.client.build", return_value=MagicMock()),
        ):
            built = client.get_admin_client()
        assert client._cached_admin_client is built
        return built

    def test_switching_profile_clears_client_cache(self):
        from ga_cli.api import client

        self._prime_admin_client()

        result = runner.invoke(app, ["--profile", "x", "config", "get"])

        assert result.exit_code == 0, result.output
        assert client._cached_admin_client is None

    def test_switching_back_to_default_clears_client_cache(self):
        from ga_cli.api import client

        runner.invoke(app, ["--profile", "x", "config", "get"])
        self._prime_admin_client()

        runner.invoke(app, ["config", "get"])

        assert client._cached_admin_client is None

    def test_same_profile_keeps_client_cache(self):
        from ga_cli.api import client

        built = self._prime_admin_client()

        result = runner.invoke(app, ["config", "get"])

        assert result.exit_code == 0, result.output
        assert client._cached_admin_client is built


class TestListProfiles:
    def test_only_default_when_no_profiles_dir(self, isolated_config_dir):
        assert list_profiles() == ["default"]

    def test_default_first_then_sorted(self, isolated_config_dir):
        root = isolated_config_dir / "profiles"
        for name in ["zeta", "client-a", "Alpha", "b.2"]:
            (root / name).mkdir(parents=True)

        assert list_profiles() == ["default", "Alpha", "b.2", "client-a", "zeta"]

    def test_invalid_names_files_and_default_dir_ignored(self, isolated_config_dir):
        root = isolated_config_dir / "profiles"
        for name in ["good", ".hidden", "-dash", "_under", "has space", "default"]:
            (root / name).mkdir(parents=True)
        (root / "stray-file").write_text("not a profile")

        assert list_profiles() == ["default", "good"]

    def test_independent_of_active_profile(self, isolated_config_dir):
        (isolated_config_dir / "profiles" / "client-a").mkdir(parents=True)
        set_active_profile("client-a")

        assert list_profiles() == ["default", "client-a"]

    def test_profile_exists(self, isolated_config_dir):
        assert profile_exists("default")
        assert not profile_exists("client-a")

        (isolated_config_dir / "profiles" / "client-a").mkdir(parents=True)

        assert profile_exists("client-a")

    def test_profile_exists_requires_a_directory(self, isolated_config_dir):
        root = isolated_config_dir / "profiles"
        root.mkdir()
        (root / "stray-file").write_text("not a profile")

        assert not profile_exists("stray-file")

    @pytest.mark.parametrize("name", ["..", ".", "", "a/b", ".hidden"])
    def test_profile_exists_false_for_invalid_names(self, name, isolated_config_dir):
        # ``profiles/..`` is a real directory; the name check must stop traversal.
        (isolated_config_dir / "profiles" / ".hidden").mkdir(parents=True)
        (isolated_config_dir / "profiles" / "a" / "b").mkdir(parents=True)

        assert not profile_exists(name)
