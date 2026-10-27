"""Tests for auth commands (login, logout, status)."""

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import google.auth
import pytest
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from typer.testing import CliRunner

from ga_cli.config.constants import OAUTH_SCOPES
from ga_cli.main import app
from ga_cli.utils.errors import ADC_LOGIN_COMMAND

runner = CliRunner()

SA_EMAIL = "client-a@proj.iam.gserviceaccount.com"
ENV_SA_EMAIL = "env@other.iam.gserviceaccount.com"
USER_EMAIL = "user@example.com"


def _write_sa_key(path: Path, email: str = SA_EMAIL) -> Path:
    """A service account key file with a fake private key (never parsed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "type": "service_account",
        "project_id": "proj",
        "client_email": email,
        "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
    }))
    return path


def _save_service_account(profile_dir: Path, key_path: Path, email: str = SA_EMAIL) -> None:
    """What `ga auth login --service-account` stores in a profile."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "auth-method.json").write_text(json.dumps({
        "method": "service-account",
        "service_account_path": str(key_path),
        "service_account_email": email,
    }))


def _save_oauth(profile_dir: Path, *, expired: bool = False) -> None:
    """What `ga auth login` stores in a profile."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    expiry = datetime.now(timezone.utc) + timedelta(hours=-1 if expired else 1)
    (profile_dir / "credentials.json").write_text(json.dumps({
        "token": "access-token",
        "refresh_token": "refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scopes": OAUTH_SCOPES,
        "expiry": expiry.isoformat(),
    }))


@pytest.fixture
def fake_sa_construction(monkeypatch):
    """Build service account credentials without parsing the fake private key.

    The credentials carry the key file's client_email, like the real ones.
    """
    def from_file(key_path, scopes=None):
        creds = MagicMock(name=f"sa-creds:{key_path}")
        creds.expired = False
        creds.service_account_email = json.loads(Path(key_path).read_text())["client_email"]
        return creds

    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_file",
        from_file,
    )


@pytest.fixture
def user_info():
    """Stand in for the userinfo endpoint `auth status` calls for OAuth."""
    with patch(
        "ga_cli.auth.oauth._fetch_user_info",
        return_value={"email": USER_EMAIL, "name": "Test User"},
    ) as mock:
        yield mock


def _status_json(*args: str) -> dict:
    result = runner.invoke(app, [*args, "auth", "status", "--output", "json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_conftest_blocks_real_adc():
    """No test may reach the dev machine's gcloud ADC unless it patches it."""
    with pytest.raises(DefaultCredentialsError):
        google.auth.default()


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
            # Status now resolves credentials for real (B4); stand in for a
            # stored OAuth login, which this test only mocks via get_auth_status.
            patch(
                "ga_cli.commands.auth_cmd.resolve_credentials",
                return_value=(MagicMock(), "oauth"),
            ),
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

    def test_status_service_account_env_var(self, monkeypatch, tmp_path, fake_sa_construction):
        # Status now validates the key it reports (B4), so it must exist.
        key = _write_sa_key(tmp_path / "keys" / "env.json", ENV_SA_EMAIL)
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", str(key))

        result = runner.invoke(app, ["auth", "status", "--output", "json"])

        assert result.exit_code == 0
        assert "service-account" in result.output
        assert "environment variable" in result.output

    def test_status_service_account_saved(self, monkeypatch):
        monkeypatch.delenv("GA_CLI_SERVICE_ACCOUNT", raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

        with (
            patch("ga_cli.commands.auth_cmd.load_auth_method") as mock_method,
            # Status now resolves credentials for real (B4); stand in for the
            # saved key, which this test only mocks via load_auth_method.
            patch(
                "ga_cli.commands.auth_cmd.resolve_credentials",
                return_value=(
                    MagicMock(service_account_email="sa@test.iam"),
                    "service-account",
                ),
            ),
        ):
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
            # Status resolves credentials for real; stand in for a stored
            # OAuth login, which this helper only mocks via get_auth_status.
            patch(
                "ga_cli.commands.auth_cmd.resolve_credentials",
                return_value=(MagicMock(), "oauth"),
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


class TestAllowlistStatusAcrossProfiles:
    """The root config.json's allowlist applies to every profile (SPEC D1)."""

    def test_named_profile_enabled_by_root_allowlist(self, isolated_config_dir):
        (isolated_config_dir / "config.json").write_text(json.dumps({"allowed_account_ids": ["1"]}))
        (isolated_config_dir / "profiles" / "client-a").mkdir(parents=True)

        data = _status_json("--profile", "client-a")

        assert data["profile"] == "client-a"
        assert data["allowlist"] == {"enabled": True}

    def test_named_profile_own_allowlist_only_there(self, isolated_config_dir):
        profile_dir = isolated_config_dir / "profiles" / "client-a"
        profile_dir.mkdir(parents=True)
        (profile_dir / "config.json").write_text(json.dumps({"allowed_property_ids": ["1"]}))

        assert _status_json("--profile", "client-a")["allowlist"] == {"enabled": True}
        assert _status_json()["allowlist"] == {"enabled": False}

    def test_named_profile_unreadable_root_counts_as_enabled(self, isolated_config_dir):
        (isolated_config_dir / "config.json").write_text("{oops")
        (isolated_config_dir / "profiles" / "client-a").mkdir(parents=True)

        assert _status_json("--profile", "client-a")["allowlist"] == {"enabled": True}


class FakeADCCredentials:
    """Stands in for what google.auth.default() returns (gcloud user ADC)."""

    quota_project_id = "quota-proj"
    expired = False


def _enable_adc(adc_mock, creds=None):
    """Make the conftest ADC guard return credentials, as real gcloud ADC would."""
    creds = creds or FakeADCCredentials()
    adc_mock.side_effect = None
    adc_mock.return_value = (creds, "adc-project")
    return creds


class TestStatusProfileAndMethod:
    """`auth status` reports what resolve_credentials() would actually use."""

    def test_default_profile_oauth(self, isolated_config_dir, user_info, no_gcloud_adc):
        _save_oauth(isolated_config_dir)

        data = _status_json()

        assert data["profile"] == "default"
        assert data["authenticated"] is True
        assert data["method"] == "oauth"
        assert data["email"] == USER_EMAIL
        assert data["token_valid"] is True
        no_gcloud_adc.assert_not_called()

    def test_named_profile_service_account(
        self, isolated_config_dir, tmp_path, fake_sa_construction
    ):
        key = _write_sa_key(tmp_path / "keys" / "client-a.json", SA_EMAIL)
        _save_service_account(isolated_config_dir / "profiles" / "client-a", key)

        data = _status_json("--profile", "client-a")

        assert data == {
            "profile": "client-a",
            "authenticated": True,
            "method": "service-account",
            "email": SA_EMAIL,
            "key_path": str(key),
            "allowlist": {"enabled": False},
        }

    def test_profile_from_env_var(
        self, isolated_config_dir, tmp_path, monkeypatch, fake_sa_construction
    ):
        key = _write_sa_key(tmp_path / "keys" / "client-a.json", SA_EMAIL)
        _save_service_account(isolated_config_dir / "profiles" / "client-a", key)
        monkeypatch.setenv("GA_CLI_PROFILE", "client-a")

        data = _status_json()

        assert data["profile"] == "client-a"
        assert data["email"] == SA_EMAIL

    def test_named_profile_ignores_credential_env_vars(
        self, isolated_config_dir, tmp_path, monkeypatch, fake_sa_construction
    ):
        """Regression: status used to report any exported key as the method."""
        key = _write_sa_key(tmp_path / "keys" / "client-a.json", SA_EMAIL)
        _save_service_account(isolated_config_dir / "profiles" / "client-a", key)
        env_key = _write_sa_key(tmp_path / "keys" / "env.json", ENV_SA_EMAIL)
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", str(env_key))
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(env_key))

        data = _status_json("--profile", "client-a")

        assert data["method"] == "service-account"
        assert data["email"] == SA_EMAIL
        assert data["key_path"] == str(key)
        assert "source" not in data
        assert ENV_SA_EMAIL not in json.dumps(data)

    def test_named_profile_oauth_ignores_credential_env_vars(
        self, isolated_config_dir, tmp_path, monkeypatch, user_info, fake_sa_construction
    ):
        _save_oauth(isolated_config_dir / "profiles" / "client-a")
        env_key = _write_sa_key(tmp_path / "keys" / "env.json", ENV_SA_EMAIL)
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", str(env_key))

        data = _status_json("--profile", "client-a")

        assert data["profile"] == "client-a"
        assert data["method"] == "oauth"
        assert data["email"] == USER_EMAIL

    def test_named_profile_without_credentials_ignores_env_vars(
        self, isolated_config_dir, tmp_path, monkeypatch, fake_sa_construction, no_gcloud_adc
    ):
        (isolated_config_dir / "profiles" / "client-a").mkdir(parents=True)
        env_key = _write_sa_key(tmp_path / "keys" / "env.json", ENV_SA_EMAIL)
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", str(env_key))
        _enable_adc(no_gcloud_adc)

        data = _status_json("--profile", "client-a")

        assert data["profile"] == "client-a"
        assert data["authenticated"] is False
        assert data["method"] == "none"
        assert "Profile 'client-a' has no credentials" in data["message"]
        no_gcloud_adc.assert_not_called()

    def test_default_profile_env_service_account(
        self, tmp_path, monkeypatch, fake_sa_construction
    ):
        key = _write_sa_key(tmp_path / "keys" / "env.json", ENV_SA_EMAIL)
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))

        data = _status_json()

        assert data == {
            "profile": "default",
            "authenticated": True,
            "method": "service-account",
            "source": "environment variable",
            "email": ENV_SA_EMAIL,
            "key_path": str(key),
            "allowlist": {"enabled": False},
        }

    def test_non_sa_google_application_credentials_is_adc(
        self, tmp_path, monkeypatch, no_gcloud_adc
    ):
        """Regression: an external_account file used to be reported as a service account."""
        wif = tmp_path / "wif.json"
        wif.write_text(json.dumps({"type": "external_account", "audience": "//iam/x"}))
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(wif))
        _enable_adc(no_gcloud_adc)

        data = _status_json()

        assert data["method"] == "adc"
        assert data["authenticated"] is True

    def test_non_sa_gac_falls_through_to_saved_service_account(
        self, isolated_config_dir, tmp_path, monkeypatch, fake_sa_construction
    ):
        """A skipped non-SA GOOGLE_APPLICATION_CREDENTIALS is not the SA's source."""
        wif = tmp_path / "wif.json"
        wif.write_text(json.dumps({"type": "external_account"}))
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(wif))
        key = _write_sa_key(tmp_path / "keys" / "saved.json", SA_EMAIL)
        _save_service_account(isolated_config_dir, key)

        data = _status_json()

        assert data["method"] == "service-account"
        assert "source" not in data
        assert data["key_path"] == str(key)
        assert data["email"] == SA_EMAIL

    def test_adc(self, no_gcloud_adc):
        _enable_adc(no_gcloud_adc)

        data = _status_json()

        assert data == {
            "profile": "default",
            "authenticated": True,
            "method": "adc",
            "quota_project": "quota-proj",
            "allowlist": {"enabled": False},
        }
        # google.auth.default may probe the GCE metadata server: once per run.
        assert no_gcloud_adc.call_count == 1

    def test_adc_service_account_identity(self, no_gcloud_adc):
        creds = FakeADCCredentials()
        creds.quota_project_id = None
        creds.service_account_email = "adc-sa@proj.iam.gserviceaccount.com"
        _enable_adc(no_gcloud_adc, creds)

        data = _status_json()

        assert data["method"] == "adc"
        assert data["email"] == "adc-sa@proj.iam.gserviceaccount.com"
        assert "quota_project" not in data

    def test_adc_ignores_placeholder_identity(self, no_gcloud_adc):
        """GCE credentials report 'default' until refreshed; that is not an email."""
        creds = FakeADCCredentials()
        creds.service_account_email = "default"
        _enable_adc(no_gcloud_adc, creds)

        data = _status_json()

        assert "email" not in data

    def test_oauth_wins_over_adc(self, isolated_config_dir, user_info, no_gcloud_adc):
        _save_oauth(isolated_config_dir)
        _enable_adc(no_gcloud_adc)

        data = _status_json()

        assert data["method"] == "oauth"
        no_gcloud_adc.assert_not_called()

    def test_adc_table(self, no_gcloud_adc):
        _enable_adc(no_gcloud_adc)

        result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0, result.output
        assert "adc" in result.stdout
        assert "Profile" in result.stdout
        assert "default" in result.stdout

    def test_named_profile_table_shows_profile(
        self, isolated_config_dir, tmp_path, fake_sa_construction
    ):
        key = _write_sa_key(tmp_path / "keys" / "client-a.json", SA_EMAIL)
        _save_service_account(isolated_config_dir / "profiles" / "client-a", key)

        result = runner.invoke(app, ["--profile", "client-a", "auth", "status"])

        assert result.exit_code == 0, result.output
        assert "Profile" in result.stdout
        assert "client-a" in result.stdout
        assert "service-account" in result.stdout


class TestStatusNotAuthenticated:
    """Unauthenticated keeps its contract: exit 0, `"authenticated": false`."""

    def test_nothing_configured(self, isolated_config_dir):
        data = _status_json()

        assert data["profile"] == "default"
        assert data["authenticated"] is False
        assert data["method"] == "none"
        assert "ga auth login" in data["message"]
        assert ADC_LOGIN_COMMAND in data["message"]

    def test_unknown_profile(self, isolated_config_dir, no_gcloud_adc):
        (isolated_config_dir / "profiles" / "client-a").mkdir(parents=True)
        _enable_adc(no_gcloud_adc)

        data = _status_json("--profile", "clinet-a")

        assert data == {
            "profile": "clinet-a",
            "authenticated": False,
            "method": "none",
            "message": (
                "Profile 'clinet-a' does not exist. Known profiles: default, client-a.\n"
                "Create it with: ga --profile clinet-a auth login"
            ),
            "allowlist": {"enabled": False},
        }
        no_gcloud_adc.assert_not_called()
        # Status is read-only: it never creates the profile.
        assert not (isolated_config_dir / "profiles" / "clinet-a").exists()

    def test_unknown_profile_table(self, isolated_config_dir):
        result = runner.invoke(app, ["--profile", "typo", "auth", "status"])

        assert result.exit_code == 0, result.output
        assert "typo" in result.stdout
        assert "does not exist" in result.stdout

    def test_stored_oauth_that_cannot_refresh(self, isolated_config_dir, no_gcloud_adc):
        """A broken OAuth login is reported as such, not replaced by ADC."""
        _save_oauth(isolated_config_dir, expired=True)
        _enable_adc(no_gcloud_adc)

        with patch(
            "google.oauth2.credentials.Credentials.refresh",
            side_effect=RefreshError("invalid_grant"),
        ):
            data = _status_json()

        assert data["authenticated"] is False
        assert data["method"] == "oauth"
        assert "ga auth login" in data["message"]
        no_gcloud_adc.assert_not_called()

    def test_missing_service_account_key(self, monkeypatch, tmp_path):
        missing = tmp_path / "nope.json"
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", str(missing))

        data = _status_json()

        assert data["authenticated"] is False
        assert data["method"] == "service-account"
        assert str(missing) in data["message"]

    def test_invalid_service_account_key(self, isolated_config_dir, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        _save_service_account(isolated_config_dir / "profiles" / "client-a", bad)

        data = _status_json("--profile", "client-a")

        assert data["profile"] == "client-a"
        assert data["authenticated"] is False
        assert data["method"] == "service-account"
        assert "Invalid JSON" in data["message"]


class TestLoginLogoutActiveProfile:
    """login/logout write and clear only the active profile's files (B1 paths)."""

    @pytest.fixture
    def no_network(self):
        with (
            patch("ga_cli.auth.oauth.requests.post") as revoke,
            patch("ga_cli.auth.oauth._fetch_user_info", return_value=None),
        ):
            yield revoke

    @staticmethod
    def _seed(root: Path, tmp_path: Path) -> dict:
        """Both the root (default) profile and client-a hold SA + OAuth files."""
        files = {}
        for name, directory in (
            ("default", root),
            ("client-a", root / "profiles" / "client-a"),
        ):
            key = _write_sa_key(tmp_path / "keys" / f"{name}.json")
            _save_service_account(directory, key)
            _save_oauth(directory)
            files[name] = {
                "creds": directory / "credentials.json",
                "auth": directory / "auth-method.json",
                "key": key,
            }
        return files

    def test_named_logout_leaves_root_intact(self, isolated_config_dir, tmp_path, no_network):
        files = self._seed(isolated_config_dir, tmp_path)
        root_creds = files["default"]["creds"].read_text()
        root_auth = files["default"]["auth"].read_text()

        result = runner.invoke(app, ["--profile", "client-a", "auth", "logout"])

        assert result.exit_code == 0, result.output
        assert not files["client-a"]["creds"].exists()
        assert not files["client-a"]["auth"].exists()
        assert files["client-a"]["key"].exists()  # the key file itself is never deleted
        assert files["default"]["creds"].read_text() == root_creds
        assert files["default"]["auth"].read_text() == root_auth

    def test_default_logout_leaves_named_profile_intact(
        self, isolated_config_dir, tmp_path, no_network
    ):
        files = self._seed(isolated_config_dir, tmp_path)

        result = runner.invoke(app, ["auth", "logout"])

        assert result.exit_code == 0, result.output
        assert not files["default"]["creds"].exists()
        assert not files["default"]["auth"].exists()
        assert files["client-a"]["creds"].exists()
        assert files["client-a"]["auth"].exists()

    def test_named_service_account_login_writes_only_the_profile(
        self, isolated_config_dir, tmp_path, fake_sa_construction
    ):
        key = _write_sa_key(tmp_path / "keys" / "client-a.json", SA_EMAIL)
        before = {p for p in isolated_config_dir.rglob("*") if p.is_file()}

        result = runner.invoke(
            app, ["--profile", "client-a", "auth", "login", "--service-account", str(key)]
        )

        assert result.exit_code == 0, result.output
        assert SA_EMAIL in result.output
        written = {p for p in isolated_config_dir.rglob("*") if p.is_file()} - before
        profile_dir = isolated_config_dir / "profiles" / "client-a"
        assert written == {profile_dir / "auth-method.json"}
        saved = json.loads((profile_dir / "auth-method.json").read_text())
        assert saved["service_account_email"] == SA_EMAIL
        assert saved["service_account_path"] == str(key.resolve())
        assert not (isolated_config_dir / "auth-method.json").exists()
        assert not (isolated_config_dir / "credentials.json").exists()


def _scope_insufficient_error():
    """A realistic 403 for an access token that lacks the Analytics scopes."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = 403
    resp.reason = "Forbidden"
    body = {
        "error": {
            "code": 403,
            "message": "Request had insufficient authentication scopes.",
            "status": "PERMISSION_DENIED",
            "details": [{
                "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                "reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
                "domain": "googleapis.com",
                "metadata": {
                    "service": "analyticsadmin.googleapis.com",
                    "method": "google.analytics.admin.v1beta.AnalyticsAdminService.ListAccounts",
                },
            }],
        }
    }
    return HttpError(resp, json.dumps(body).encode())


class TestAdcScopeHintEndToEnd:
    """A 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT on ADC credentials points at gcloud."""

    @staticmethod
    def _run_accounts_list(*args: str):
        client = MagicMock()
        client.accounts.return_value.list.return_value.execute.side_effect = (
            _scope_insufficient_error()
        )
        with patch("ga_cli.api.client.build", return_value=client):
            return runner.invoke(app, ["accounts", "list", *args])

    def test_adc_json_gets_hint_field(self, no_gcloud_adc):
        _enable_adc(no_gcloud_adc)

        result = self._run_accounts_list("-o", "json")

        assert result.exit_code == 2
        payload = json.loads(result.stderr)
        assert payload["message"] == "Request had insufficient authentication scopes."
        assert ADC_LOGIN_COMMAND in payload["hint"]

    def test_adc_table_appends_hint(self, no_gcloud_adc):
        _enable_adc(no_gcloud_adc)

        result = self._run_accounts_list("-o", "table")

        assert result.exit_code == 2
        stderr = " ".join(result.stderr.split())
        assert "insufficient authentication scopes" in stderr
        assert "Application Default Credentials" in stderr
        assert "gcloud auth application-default login" in stderr

    def test_oauth_gets_no_hint(self, isolated_config_dir):
        _save_oauth(isolated_config_dir)

        result = self._run_accounts_list("-o", "json")

        assert result.exit_code == 2
        payload = json.loads(result.stderr)
        assert "hint" not in payload
