"""Tests for auth commands (login, logout, status)."""

import importlib
import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


class TestLoginCommand:
    def test_login_oauth_success(self):
        with (
            patch("ga_cli.commands.auth_cmd.get_auth_status") as mock_status,
            patch("ga_cli.commands.auth_cmd.login") as mock_login,
            patch("ga_cli.commands.auth_cmd.clear_client_cache"),
        ):
            mock_status.side_effect = [
                {"authenticated": False},
                {"authenticated": True, "email": "user@example.com"},
            ]
            mock_login.return_value = MagicMock()

            result = runner.invoke(app, ["auth", "login"])

            assert result.exit_code == 0
            assert "Authenticated as user@example.com" in result.output
            mock_login.assert_called_once()

    def test_login_already_authenticated(self):
        with patch("ga_cli.commands.auth_cmd.get_auth_status") as mock_status:
            mock_status.return_value = {
                "authenticated": True,
                "email": "user@example.com",
            }

            result = runner.invoke(app, ["auth", "login"])

            assert result.exit_code == 0
            assert "Already authenticated as user@example.com" in result.output

    def test_login_service_account_success(self):
        with patch("ga_cli.commands.auth_cmd.login_with_service_account") as mock_sa:
            mock_sa.return_value = "sa@project.iam.gserviceaccount.com"

            result = runner.invoke(
                app, ["auth", "login", "--service-account", "/path/to/key.json"]
            )

            assert result.exit_code == 0
            assert "Authenticated as sa@project.iam.gserviceaccount.com" in result.output

    def test_login_service_account_failure(self):
        with patch("ga_cli.commands.auth_cmd.login_with_service_account") as mock_sa:
            mock_sa.side_effect = FileNotFoundError("Key file not found")

            result = runner.invoke(
                app, ["auth", "login", "-s", "/bad/path.json"]
            )

            assert result.exit_code == 1
            assert "Authentication failed" in result.output


class TestLogoutCommand:
    def test_logout_oauth_session(self):
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method") as mock_method,
            patch("ga_cli.commands.auth_cmd.get_auth_status") as mock_status,
            patch("ga_cli.commands.auth_cmd.logout") as mock_logout,
            patch("ga_cli.commands.auth_cmd.clear_client_cache"),
        ):
            mock_method.return_value = None
            mock_status.return_value = {"authenticated": True}

            result = runner.invoke(app, ["auth", "logout"])

            assert result.exit_code == 0
            assert "Logged out from OAuth session" in result.output
            mock_logout.assert_called_once()

    def test_logout_service_account(self):
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method") as mock_method,
            patch("ga_cli.commands.auth_cmd.get_auth_status") as mock_status,
            patch("ga_cli.commands.auth_cmd.clear_auth_method") as mock_clear,
        ):
            mock_method.return_value = {
                "method": "service-account",
                "service_account_email": "sa@project.iam",
            }
            mock_status.return_value = {"authenticated": False}

            result = runner.invoke(app, ["auth", "logout"])

            assert result.exit_code == 0
            assert "Cleared service account configuration" in result.output
            mock_clear.assert_called_once()

    def test_logout_not_authenticated(self):
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method") as mock_method,
            patch("ga_cli.commands.auth_cmd.get_auth_status") as mock_status,
        ):
            mock_method.return_value = None
            mock_status.return_value = {"authenticated": False}

            result = runner.invoke(app, ["auth", "logout"])

            assert result.exit_code == 0
            assert "Not currently authenticated" in result.output


class TestStatusCommand:
    def test_status_oauth(self):
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method") as mock_method,
            patch("ga_cli.commands.auth_cmd.get_auth_status") as mock_status,
            patch.dict("os.environ", {}, clear=False),
        ):
            mock_method.return_value = None
            mock_status.return_value = {
                "authenticated": True,
                "email": "user@example.com",
            }

            result = runner.invoke(app, ["auth", "status", "--output", "json"])

            assert result.exit_code == 0
            assert "oauth" in result.output
            assert "user@example.com" in result.output

    def test_status_service_account_env_var(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", "/path/to/key.json")

        result = runner.invoke(app, ["auth", "status", "--output", "json"])

        assert result.exit_code == 0
        assert "service-account" in result.output
        assert "environment variable" in result.output

    def test_status_service_account_saved(self, monkeypatch):
        monkeypatch.delenv("GA_CLI_SERVICE_ACCOUNT", raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

        with patch("ga_cli.commands.auth_cmd.load_auth_method") as mock_method:
            mock_method.return_value = {
                "method": "service-account",
                "service_account_email": "sa@test.iam",
                "service_account_path": "/path/key.json",
            }

            result = runner.invoke(app, ["auth", "status", "--output", "json"])

            assert result.exit_code == 0
            assert "sa@test.iam" in result.output
            assert "service-account" in result.output

    def _status(self, monkeypatch, *args, tty):
        monkeypatch.setattr(
            importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: tty
        )
        monkeypatch.delenv("GA_CLI_SERVICE_ACCOUNT", raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method", return_value=None),
            patch(
                "ga_cli.commands.auth_cmd.get_auth_status",
                return_value={"authenticated": True, "email": "user@example.com"},
            ),
        ):
            return runner.invoke(app, ["auth", "status", *args])

    def test_status_piped_defaults_to_json(self, monkeypatch):
        """`ga auth status | jq .authenticated` must get JSON."""
        result = self._status(monkeypatch, tty=False)

        assert result.exit_code == 0
        assert json.loads(result.stdout)["authenticated"] is True

    def test_status_terminal_defaults_to_table(self, monkeypatch):
        result = self._status(monkeypatch, tty=True)

        assert result.exit_code == 0
        assert "user@example.com" in result.stdout
        assert not result.stdout.lstrip().startswith("{")

    def test_status_piped_explicit_table_wins(self, monkeypatch):
        result = self._status(monkeypatch, "-o", "table", tty=False)

        assert result.exit_code == 0
        assert not result.stdout.lstrip().startswith("{")


class TestAllowlistIntegration:
    def _status_json(self, monkeypatch):
        monkeypatch.delenv("GA_CLI_SERVICE_ACCOUNT", raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method", return_value=None),
            patch(
                "ga_cli.commands.auth_cmd.get_auth_status",
                return_value={"authenticated": True, "email": "user@example.com"},
            ),
        ):
            result = runner.invoke(app, ["auth", "status", "-o", "json"])
        assert result.exit_code == 0
        return json.loads(result.stdout)

    def test_status_allowlist_disabled(self, monkeypatch):
        assert self._status_json(monkeypatch)["allowlist"] == {"enabled": False}

    def test_status_allowlist_enabled_from_env_without_network(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "1")
        with patch("ga_cli.api.client._get_credentials") as creds:
            assert self._status_json(monkeypatch)["allowlist"] == {"enabled": True}
        creds.assert_not_called()

    def test_status_service_account_env_has_allowlist(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", "/path/to/key.json")
        result = runner.invoke(app, ["auth", "status", "-o", "json"])
        assert json.loads(result.stdout)["allowlist"] == {"enabled": False}

    def test_login_clears_allowlist_cache(self, tmp_path):
        cache = tmp_path / "allowlist-cache.json"
        cache.write_text("{}")
        with (
            patch("ga_cli.commands.auth_cmd.get_auth_status") as mock_status,
            patch("ga_cli.commands.auth_cmd.login"),
            patch("ga_cli.commands.auth_cmd.clear_client_cache"),
        ):
            mock_status.side_effect = [
                {"authenticated": False},
                {"authenticated": True, "email": "user@example.com"},
            ]
            result = runner.invoke(app, ["auth", "login"])
        assert result.exit_code == 0
        assert not cache.exists()

    def test_service_account_login_clears_allowlist_cache(self, tmp_path):
        cache = tmp_path / "allowlist-cache.json"
        cache.write_text("{}")
        with patch(
            "ga_cli.commands.auth_cmd.login_with_service_account", return_value="sa@x.iam"
        ):
            result = runner.invoke(app, ["auth", "login", "-s", "/k.json"])
        assert result.exit_code == 0
        assert not cache.exists()

    def test_logout_clears_allowlist_cache(self, tmp_path):
        cache = tmp_path / "allowlist-cache.json"
        cache.write_text("{}")
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method", return_value=None),
            patch("ga_cli.commands.auth_cmd.get_auth_status",
                  return_value={"authenticated": True}),
            patch("ga_cli.commands.auth_cmd.logout"),
            patch("ga_cli.commands.auth_cmd.clear_client_cache"),
        ):
            result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0
        assert not cache.exists()

    def test_logout_without_cache_file_is_fine(self):
        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method", return_value=None),
            patch("ga_cli.commands.auth_cmd.get_auth_status",
                  return_value={"authenticated": False}),
        ):
            result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0
