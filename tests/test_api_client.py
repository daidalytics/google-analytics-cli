"""Tests for ga_cli.api.client."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from typer.testing import CliRunner

from ga_cli.api.client import (
    _get_credentials,
    clear_client_cache,
    get_admin_alpha_client,
    get_admin_client,
    get_data_alpha_client,
    get_data_client,
    resolve_credentials,
)
from ga_cli.config.constants import OAUTH_SCOPES, set_active_profile
from ga_cli.main import app
from ga_cli.utils.errors import (
    NotAuthenticatedError,
    ProfileNotFoundError,
    classify_error,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure client cache is cleared between tests."""
    clear_client_cache()
    yield
    clear_client_cache()


@pytest.fixture(autouse=True)
def no_credential_env(monkeypatch):
    """The dev machine may export credential env vars; tests set their own."""
    monkeypatch.delenv("GA_CLI_SERVICE_ACCOUNT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)


class FakeADC:
    """Stands in for whatever google.auth.default() would return."""


@pytest.fixture(autouse=True)
def adc(monkeypatch):
    """Never let a test reach real gcloud ADC on the dev machine.

    ADC is unavailable unless a test enables it with ``_enable_adc(adc)``.
    """
    mock = MagicMock(side_effect=DefaultCredentialsError("ADC unavailable (test)"))
    monkeypatch.setattr("google.auth.default", mock)
    return mock


def _enable_adc(adc_mock) -> FakeADC:
    creds = FakeADC()
    adc_mock.side_effect = None
    adc_mock.return_value = (creds, "adc-project")
    return creds


class FakeSA:
    """Service account credentials tagged with the key file they came from."""

    def __init__(self, key_path, scopes=None):
        self.key_path = str(key_path)
        self.scopes = scopes
        self.expired = False


@pytest.fixture(autouse=True)
def sa_from_file(monkeypatch):
    """Key files hold fake private keys, so never parse them for real."""
    mock = MagicMock(side_effect=lambda path, scopes=None: FakeSA(path, scopes))
    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_file", mock
    )
    return mock


# ---------------------------------------------------------------------------
# Credential-source builders. Everything lives under the isolated config dir.
# ---------------------------------------------------------------------------

SA_KEY = {
    "type": "service_account",
    "project_id": "proj",
    "private_key_id": "kid",
    "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
    "client_email": "placeholder@proj.iam.gserviceaccount.com",
    "client_id": "123",
    "token_uri": "https://oauth2.googleapis.com/token",
}

NON_SA_KEYS = {
    "external_account": {
        "type": "external_account",
        "audience": (
            "//iam.googleapis.com/projects/1/locations/global"
            "/workloadIdentityPools/p/providers/gh"
        ),
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": {"file": "/tmp/token"},
    },
    "authorized_user": {
        "type": "authorized_user",
        "client_id": "cid",
        "client_secret": "secret",
        "refresh_token": "rt",
    },
}

PROFILE = "x"


def _write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def _sa_key(root: Path, name: str) -> str:
    data = {**SA_KEY, "client_email": f"{name}@proj.iam.gserviceaccount.com"}
    return str(_write_json(root / "keys" / f"{name}.json", data))


def _save_sa(profile_dir: Path, key_path: str) -> None:
    _write_json(
        profile_dir / "auth-method.json",
        {
            "method": "service-account",
            "service_account_path": key_path,
            "service_account_email": f"{Path(key_path).stem}@proj.iam.gserviceaccount.com",
        },
    )


def _save_oauth(profile_dir: Path, token: str, *, expired: bool = False, scopes=None) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # google-auth uses naive UTC
    expiry = now + (timedelta(days=-1) if expired else timedelta(days=365))
    _write_json(
        profile_dir / "credentials.json",
        {
            "token": token,
            "refresh_token": f"{token}-refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "cid",
            "client_secret": "secret",
            "scopes": OAUTH_SCOPES if scopes is None else scopes,
            "expiry": expiry.isoformat(),
        },
    )


@pytest.fixture
def configure(isolated_config_dir, monkeypatch, adc):
    """Set up credential sources by name, for the default profile and profile ``x``."""
    root = isolated_config_dir
    profile_dir = root / "profiles" / PROFILE

    def _configure(*sources: str) -> None:
        for source in sources:
            if source == "env_sa":
                monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", _sa_key(root, "env-sa"))
            elif source == "gac_sa":
                monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", _sa_key(root, "gac-sa"))
            elif source == "saved_sa":
                _save_sa(root, _sa_key(root, "saved-sa"))
            elif source == "oauth":
                _save_oauth(root, "root-token")
            elif source == "adc":
                _enable_adc(adc)
            elif source == "profile_dir":
                profile_dir.mkdir(parents=True, exist_ok=True)
            elif source == "profile_sa":
                _save_sa(profile_dir, _sa_key(root, "profile-sa"))
            elif source == "profile_oauth":
                _save_oauth(profile_dir, "profile-token")
            else:  # pragma: no cover - guards typos in parametrize tables
                raise AssertionError(f"unknown source {source!r}")

    return _configure


def _identity(creds) -> str:
    if isinstance(creds, FakeSA):
        return f"sa:{Path(creds.key_path).stem}"
    if isinstance(creds, FakeADC):
        return "adc"
    return f"oauth:{creds.token}"


# Every default-profile source at once: a named profile must ignore all of them.
DEFAULT_SOURCES = ("env_sa", "gac_sa", "saved_sa", "oauth", "adc")


class TestGetCredentials:
    @patch("ga_cli.api.client.get_service_account_credentials")
    @patch("ga_cli.api.client.get_valid_credentials")
    def test_prefers_service_account(self, mock_oauth, mock_sa):
        mock_sa_creds = MagicMock()
        mock_sa_creds.expired = False
        mock_sa.return_value = mock_sa_creds
        mock_oauth.return_value = MagicMock()

        result = _get_credentials()
        assert result is mock_sa_creds
        mock_oauth.assert_not_called()

    @patch("ga_cli.api.client.get_service_account_credentials")
    @patch("ga_cli.api.client.get_valid_credentials")
    def test_falls_back_to_oauth(self, mock_oauth, mock_sa):
        mock_sa.return_value = None
        mock_oauth_creds = MagicMock()
        mock_oauth.return_value = mock_oauth_creds

        result = _get_credentials()
        assert result is mock_oauth_creds

    @patch("ga_cli.api.client.get_service_account_credentials")
    @patch("ga_cli.api.client.get_valid_credentials")
    def test_raises_when_no_auth(self, mock_oauth, mock_sa):
        mock_sa.return_value = None
        mock_oauth.return_value = None

        with pytest.raises(RuntimeError, match="Not authenticated"):
            _get_credentials()

    @patch("ga_cli.api.client.get_service_account_credentials")
    def test_refreshes_expired_service_account(self, mock_sa):
        mock_sa_creds = MagicMock()
        mock_sa_creds.expired = True
        mock_sa.return_value = mock_sa_creds

        with patch("google.auth.transport.requests.Request"):
            result = _get_credentials()

        mock_sa_creds.refresh.assert_called_once()
        assert result is mock_sa_creds


class TestGetAdminClient:
    @patch("ga_cli.api.client._get_credentials")
    @patch("ga_cli.api.client.build")
    def test_builds_admin_client(self, mock_build, mock_creds):
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        result = get_admin_client()
        mock_build.assert_called_once_with(
            "analyticsadmin",
            "v1beta",
            credentials=mock_creds.return_value,
        )
        assert result is mock_build.return_value

    @patch("ga_cli.api.client._get_credentials")
    @patch("ga_cli.api.client.build")
    def test_caches_admin_client(self, mock_build, mock_creds):
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        result1 = get_admin_client()
        result2 = get_admin_client()
        assert result1 is result2
        mock_build.assert_called_once()  # Only built once


class TestGetDataClient:
    @patch("ga_cli.api.client._get_credentials")
    @patch("ga_cli.api.client.build")
    def test_builds_data_client(self, mock_build, mock_creds):
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        result = get_data_client()
        mock_build.assert_called_once_with(
            "analyticsdata",
            "v1beta",
            credentials=mock_creds.return_value,
        )
        assert result is mock_build.return_value

    @patch("ga_cli.api.client._get_credentials")
    @patch("ga_cli.api.client.build")
    def test_caches_data_client(self, mock_build, mock_creds):
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        result1 = get_data_client()
        result2 = get_data_client()
        assert result1 is result2
        mock_build.assert_called_once()


class TestClearClientCache:
    @patch("ga_cli.api.client._get_credentials")
    @patch("ga_cli.api.client.build")
    def test_clears_cache(self, mock_build, mock_creds):
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        get_admin_client()
        get_data_client()
        assert mock_build.call_count == 2

        clear_client_cache()

        get_admin_client()
        get_data_client()
        assert mock_build.call_count == 4  # Rebuilt after cache clear


class TestCredentialResolution:
    """SPEC B4: the credential resolution table, for both profile kinds.

    Each row configures the source it expects to win *plus every source
    below it*, so a row passes only if precedence is right.
    """

    # -- the table ---------------------------------------------------------

    @pytest.mark.parametrize(
        ("sources", "identity", "method"),
        [
            pytest.param(
                DEFAULT_SOURCES, "sa:env-sa", "service-account",
                id="1-GA_CLI_SERVICE_ACCOUNT",
            ),
            pytest.param(
                DEFAULT_SOURCES[1:], "sa:gac-sa", "service-account",
                id="2-GOOGLE_APPLICATION_CREDENTIALS",
            ),
            pytest.param(
                DEFAULT_SOURCES[2:], "sa:saved-sa", "service-account",
                id="3-saved-service-account",
            ),
            pytest.param(DEFAULT_SOURCES[3:], "oauth:root-token", "oauth", id="4-oauth"),
            pytest.param(DEFAULT_SOURCES[4:], "adc", "adc", id="5-adc"),
        ],
    )
    def test_default_profile_table(self, configure, sources, identity, method):
        configure(*sources)

        creds, resolved_method = resolve_credentials()

        assert _identity(creds) == identity
        assert resolved_method == method

    def test_default_profile_step_6_not_authenticated(self, configure, adc):
        configure()  # nothing at all

        with pytest.raises(NotAuthenticatedError) as exc_info:
            resolve_credentials()

        adc.assert_called_once()
        message = str(exc_info.value)
        assert message.startswith("Not authenticated.")
        assert "ga auth login" in message
        assert "--service-account" in message
        assert "GA_CLI_SERVICE_ACCOUNT" in message
        assert (
            "gcloud auth application-default login --scopes="
            "https://www.googleapis.com/auth/analytics.readonly,"
            "https://www.googleapis.com/auth/cloud-platform"
        ) in message
        assert classify_error(exc_info.value) == (2, "auth_error")

    @pytest.mark.parametrize(
        ("sources", "identity", "method"),
        [
            pytest.param(
                (*DEFAULT_SOURCES, "profile_sa", "profile_oauth"),
                "sa:profile-sa",
                "service-account",
                id="1-profile-service-account",
            ),
            pytest.param(
                (*DEFAULT_SOURCES, "profile_oauth"),
                "oauth:profile-token",
                "oauth",
                id="2-profile-oauth",
            ),
        ],
    )
    def test_named_profile_table(self, configure, adc, sources, identity, method):
        configure(*sources)
        set_active_profile(PROFILE)

        creds, resolved_method = resolve_credentials()

        assert _identity(creds) == identity
        assert resolved_method == method
        adc.assert_not_called()

    def test_named_profile_step_3_has_no_credentials(self, configure, adc):
        configure(*DEFAULT_SOURCES, "profile_dir")
        set_active_profile(PROFILE)

        with pytest.raises(NotAuthenticatedError) as exc_info:
            resolve_credentials()

        assert str(exc_info.value) == (
            "Profile 'x' has no credentials. "
            "Run: ga --profile x auth login [--service-account KEY]"
        )
        assert classify_error(exc_info.value) == (2, "auth_error")
        adc.assert_not_called()

    # -- named profile: never falls back -----------------------------------

    @pytest.mark.parametrize(
        "env_vars",
        [
            pytest.param(("env_sa",), id="GA_CLI_SERVICE_ACCOUNT"),
            pytest.param(("gac_sa",), id="GOOGLE_APPLICATION_CREDENTIALS"),
            pytest.param(("env_sa", "gac_sa"), id="both"),
        ],
    )
    def test_named_profile_service_account_beats_exported_keys(
        self, configure, sa_from_file, env_vars
    ):
        """The core safety test: an exported key must never override the
        client the user explicitly chose."""
        configure(*env_vars, "profile_sa")
        set_active_profile(PROFILE)

        creds, method = resolve_credentials()

        assert _identity(creds) == "sa:profile-sa"
        assert method == "service-account"
        used = [Path(call.args[0]).stem for call in sa_from_file.call_args_list]
        assert used == ["profile-sa"]

    def test_named_profile_without_credentials_reads_nothing_outside_profile(
        self, configure, adc, sa_from_file, isolated_config_dir, monkeypatch
    ):
        configure(*DEFAULT_SOURCES, "profile_dir")
        set_active_profile(PROFILE)

        real_read_text = Path.read_text
        reads: list[Path] = []

        def spy(self, *args, **kwargs):
            reads.append(Path(self))
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", spy)

        with pytest.raises(NotAuthenticatedError, match="Profile 'x' has no credentials"):
            resolve_credentials()

        profile_dir = isolated_config_dir / "profiles" / PROFILE
        outside = [p for p in reads if profile_dir not in p.parents]
        assert outside == []
        adc.assert_not_called()
        sa_from_file.assert_not_called()

    def test_named_profile_with_unusable_oauth_does_not_fall_back(
        self, configure, adc, isolated_config_dir
    ):
        configure(*DEFAULT_SOURCES)
        _save_oauth(isolated_config_dir / "profiles" / PROFILE, "stale", expired=True)
        set_active_profile(PROFILE)

        with patch(
            "google.oauth2.credentials.Credentials.refresh",
            side_effect=RefreshError("invalid_grant"),
        ):
            with pytest.raises(NotAuthenticatedError, match="Profile 'x' has no credentials"):
                resolve_credentials()

        adc.assert_not_called()

    def test_named_profile_with_missing_key_file_does_not_fall_back(
        self, configure, adc, isolated_config_dir
    ):
        configure(*DEFAULT_SOURCES, "profile_oauth")
        _save_sa(isolated_config_dir / "profiles" / PROFILE, "/nonexistent/key.json")
        set_active_profile(PROFILE)

        with pytest.raises(FileNotFoundError, match="/nonexistent/key.json"):
            resolve_credentials()

        adc.assert_not_called()

    # -- unknown named profile ---------------------------------------------

    def test_unknown_profile_raises_profile_not_found(self, configure, isolated_config_dir):
        configure(*DEFAULT_SOURCES)
        (isolated_config_dir / "profiles" / "client-b").mkdir(parents=True)
        (isolated_config_dir / "profiles" / "client-a").mkdir(parents=True)
        set_active_profile("clinet-a")

        with (
            patch("ga_cli.api.client.get_service_account_credentials") as mock_sa,
            patch("ga_cli.api.client.get_valid_credentials") as mock_oauth,
            pytest.raises(ProfileNotFoundError) as exc_info,
        ):
            resolve_credentials()

        assert str(exc_info.value) == (
            "Profile 'clinet-a' does not exist. "
            "Known profiles: default, client-a, client-b.\n"
            "Create it with: ga --profile clinet-a auth login"
        )
        assert isinstance(exc_info.value, RuntimeError)
        assert classify_error(exc_info.value) == (2, "auth_error")
        mock_sa.assert_not_called()
        mock_oauth.assert_not_called()

    @pytest.mark.parametrize(
        "getter",
        [get_admin_client, get_admin_alpha_client, get_data_client, get_data_alpha_client],
        ids=lambda f: f.__name__,
    )
    def test_unknown_profile_builds_no_client(self, configure, adc, getter):
        configure(*DEFAULT_SOURCES)
        set_active_profile("typo")

        with patch("ga_cli.api.client.build") as mock_build:
            with pytest.raises(ProfileNotFoundError):
                getter()

        mock_build.assert_not_called()
        adc.assert_not_called()

    def test_unknown_profile_cli_exits_2(self, configure, adc):
        configure(*DEFAULT_SOURCES)

        with patch("ga_cli.api.client.build") as mock_build:
            result = runner.invoke(
                app, ["--profile", "typo", "accounts", "list", "-o", "json"]
            )

        assert result.exit_code == 2, result.output
        payload = json.loads(result.stderr)
        assert payload["category"] == "auth_error"
        assert payload["message"].startswith("Profile 'typo' does not exist.")
        mock_build.assert_not_called()
        adc.assert_not_called()

    def test_named_profile_without_credentials_cli_shows_literal_hint(self, configure):
        """The '[--service-account KEY]' hint must survive Rich markup."""
        configure("profile_dir")

        result = runner.invoke(app, ["--profile", "x", "accounts", "list", "-o", "table"])

        assert result.exit_code == 2, result.output
        stderr = " ".join(result.stderr.split())  # undo Rich's line wrapping
        assert "ga --profile x auth login [--service-account KEY]" in stderr

    # -- default profile: steps 1-4 unchanged, ADC only when they're empty --

    def test_oauth_wins_over_adc(self, configure, adc):
        configure("oauth", "adc")

        creds, method = resolve_credentials()

        assert method == "oauth"
        assert _identity(creds) == "oauth:root-token"
        adc.assert_not_called()

    def test_adc_requested_with_cli_scopes(self, configure, adc):
        configure("adc")

        creds, method = resolve_credentials()

        assert method == "adc"
        adc.assert_called_once_with(scopes=OAUTH_SCOPES)

    def test_unusable_stored_oauth_does_not_fall_back_to_adc(
        self, configure, adc, isolated_config_dir
    ):
        """A configured OAuth still wins: a broken token is an error to fix,
        not a reason to switch to another Google identity."""
        configure("adc")
        _save_oauth(isolated_config_dir, "stale", expired=True)

        with patch(
            "google.oauth2.credentials.Credentials.refresh",
            side_effect=RefreshError("invalid_grant"),
        ):
            with pytest.raises(NotAuthenticatedError) as exc_info:
                resolve_credentials()

        assert str(exc_info.value) == (
            "Not authenticated. Run 'ga auth login' or configure a service account."
        )
        adc.assert_not_called()

    def test_ga_cli_service_account_non_sa_key_still_raises(
        self, configure, isolated_config_dir, monkeypatch
    ):
        configure("adc")
        path = _write_json(
            isolated_config_dir / "keys" / "user.json", NON_SA_KEYS["authorized_user"]
        )
        monkeypatch.setenv("GA_CLI_SERVICE_ACCOUNT", str(path))

        with pytest.raises(ValueError, match="expected type 'service_account'"):
            resolve_credentials()

    def test_google_application_credentials_missing_file_still_raises(
        self, configure, monkeypatch, adc
    ):
        configure("adc")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/gac.json")

        with pytest.raises(FileNotFoundError, match="/nonexistent/gac.json"):
            resolve_credentials()

        adc.assert_not_called()

    def test_google_application_credentials_invalid_json_still_raises(
        self, configure, isolated_config_dir, monkeypatch
    ):
        configure("adc")
        path = isolated_config_dir / "keys" / "broken.json"
        path.parent.mkdir(parents=True)
        path.write_text("not json{{{")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))

        with pytest.raises(ValueError, match="Invalid JSON"):
            resolve_credentials()

    @pytest.mark.parametrize("key_type", sorted(NON_SA_KEYS))
    def test_non_sa_google_application_credentials_defers_to_adc(
        self, configure, adc, sa_from_file, isolated_config_dir, monkeypatch, key_type
    ):
        configure("adc")
        path = _write_json(
            isolated_config_dir / "keys" / f"{key_type}.json", NON_SA_KEYS[key_type]
        )
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))

        creds, method = resolve_credentials()

        assert method == "adc"
        assert isinstance(creds, FakeADC)
        adc.assert_called_once_with(scopes=OAUTH_SCOPES)
        sa_from_file.assert_not_called()

    @pytest.mark.parametrize(
        ("sources", "identity"),
        [
            pytest.param(("saved_sa", "oauth"), "sa:saved-sa", id="saved-service-account"),
            pytest.param(("oauth",), "oauth:root-token", id="oauth"),
        ],
    )
    def test_non_sa_google_application_credentials_skips_only_step_2(
        self, configure, adc, isolated_config_dir, monkeypatch, sources, identity
    ):
        configure(*sources, "adc")
        path = _write_json(
            isolated_config_dir / "keys" / "wif.json", NON_SA_KEYS["external_account"]
        )
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))

        creds, _ = resolve_credentials()

        assert _identity(creds) == identity
        adc.assert_not_called()

    def test_adc_failure_with_google_application_credentials_explains_why(
        self, configure, adc, isolated_config_dir, monkeypatch
    ):
        path = _write_json(
            isolated_config_dir / "keys" / "wif.json", NON_SA_KEYS["external_account"]
        )
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))
        adc.side_effect = DefaultCredentialsError("Failed to load external account file")

        with pytest.raises(NotAuthenticatedError) as exc_info:
            resolve_credentials()

        message = str(exc_info.value)
        assert message.startswith("Not authenticated.")
        assert str(path) in message
        assert "Failed to load external account file" in message
        assert exc_info.value.__cause__ is adc.side_effect

    def test_get_credentials_wraps_resolve_credentials(self, configure):
        configure("oauth")

        creds, _ = resolve_credentials()

        assert _identity(_get_credentials()) == _identity(creds)


class TestHasScopeFollowsResolution:
    """has_scope() checks the credentials resolve_credentials() would use.

    Only demonstrably-missing OAuth scopes return False. A service account,
    ADC, nothing at all, or a missing profile is undeterminable -> True.
    """

    SCOPE = "https://www.googleapis.com/auth/analytics.chatbot.read"
    WITHOUT = ["openid", "https://www.googleapis.com/auth/analytics.readonly"]
    WITH = [*WITHOUT, SCOPE]

    def _has_scope(self):
        from ga_cli.auth.credentials import has_scope

        return has_scope(self.SCOPE)

    def test_named_profile_service_account_is_true(self, configure, isolated_config_dir):
        configure("profile_sa")
        _save_oauth(isolated_config_dir / "profiles" / PROFILE, "p", scopes=self.WITHOUT)
        set_active_profile(PROFILE)

        assert self._has_scope() is True

    def test_named_profile_checks_its_own_oauth_scopes_despite_exported_keys(
        self, configure, isolated_config_dir
    ):
        """Exported SA keys are ignored by a named profile, so they can't
        mask the profile's own missing scope."""
        configure("env_sa", "gac_sa", "adc")
        _save_oauth(isolated_config_dir, "root", scopes=self.WITH)
        _save_oauth(isolated_config_dir / "profiles" / PROFILE, "p", scopes=self.WITHOUT)
        set_active_profile(PROFILE)

        assert self._has_scope() is False

    def test_named_profile_with_scope_ignores_root_oauth(self, configure, isolated_config_dir):
        _save_oauth(isolated_config_dir, "root", scopes=self.WITHOUT)
        _save_oauth(isolated_config_dir / "profiles" / PROFILE, "p", scopes=self.WITH)
        set_active_profile(PROFILE)

        assert self._has_scope() is True

    def test_named_profile_without_credentials_is_true(self, configure, isolated_config_dir):
        configure("profile_dir")
        _save_oauth(isolated_config_dir, "root", scopes=self.WITHOUT)
        set_active_profile(PROFILE)

        assert self._has_scope() is True

    def test_missing_profile_is_true_and_does_not_raise(self, configure, isolated_config_dir):
        _save_oauth(isolated_config_dir, "root", scopes=self.WITHOUT)
        set_active_profile("typo")

        assert self._has_scope() is True

    def test_default_service_account_is_true(self, configure, isolated_config_dir):
        configure("env_sa")
        _save_oauth(isolated_config_dir, "root", scopes=self.WITHOUT)

        assert self._has_scope() is True

    def test_default_oauth_scope_is_checked(self, configure, isolated_config_dir):
        _save_oauth(isolated_config_dir, "root", scopes=self.WITHOUT)

        assert self._has_scope() is False

    def test_default_adc_is_true_without_calling_adc(self, configure, adc):
        configure("adc")

        assert self._has_scope() is True
        adc.assert_not_called()

    def test_non_sa_google_application_credentials_checks_oauth(
        self, configure, isolated_config_dir, monkeypatch
    ):
        """Previously raised ValueError; now step 2 is skipped like in resolution."""
        path = _write_json(
            isolated_config_dir / "keys" / "wif.json", NON_SA_KEYS["external_account"]
        )
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))
        _save_oauth(isolated_config_dir, "root", scopes=self.WITHOUT)

        assert self._has_scope() is False
