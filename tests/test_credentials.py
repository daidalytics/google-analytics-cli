"""Tests for ga_cli.auth.credentials."""

import json
from datetime import datetime
from unittest.mock import MagicMock

from ga_cli.auth.credentials import (
    delete_credentials,
    get_valid_credentials,
    has_credentials,
    load_credentials,
    save_credentials,
)


def _make_mock_credentials(**overrides):
    """Create a mock google.oauth2.credentials.Credentials."""
    defaults = {
        "token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "scopes": ["https://www.googleapis.com/auth/analytics.readonly"],
        "expiry": datetime(2026, 12, 31, 23, 59, 59),
    }
    defaults.update(overrides)
    creds = MagicMock()
    for k, v in defaults.items():
        setattr(creds, k, v)
    return creds


class TestSaveAndLoadRoundTrip:
    def test_save_and_load(self, isolated_config_dir):
        mock_creds = _make_mock_credentials()
        save_credentials(mock_creds)

        loaded = load_credentials()
        assert loaded is not None
        assert loaded.token == "test-access-token"
        assert loaded.refresh_token == "test-refresh-token"
        assert loaded.client_id == "test-client-id"

    def test_save_creates_file_with_json(self, isolated_config_dir):
        mock_creds = _make_mock_credentials()
        save_credentials(mock_creds)

        creds_file = isolated_config_dir / "credentials.json"
        assert creds_file.exists()

        data = json.loads(creds_file.read_text())
        assert data["token"] == "test-access-token"
        assert data["refresh_token"] == "test-refresh-token"

    def test_save_preserves_expiry(self, isolated_config_dir):
        mock_creds = _make_mock_credentials()
        save_credentials(mock_creds)

        loaded = load_credentials()
        assert loaded.expiry is not None
        assert loaded.expiry.year == 2026
        assert loaded.expiry.month == 12

    def test_save_handles_none_expiry(self, isolated_config_dir):
        mock_creds = _make_mock_credentials(expiry=None)
        save_credentials(mock_creds)

        loaded = load_credentials()
        assert loaded.expiry is None


class TestLoadCredentials:
    def test_returns_none_when_no_file(self, isolated_config_dir):
        assert load_credentials() is None

    def test_returns_none_on_corrupt_json(self, isolated_config_dir):
        creds_file = isolated_config_dir / "credentials.json"
        creds_file.write_text("not valid json{{{")
        assert load_credentials() is None

    def test_handles_missing_optional_fields(self, isolated_config_dir):
        creds_file = isolated_config_dir / "credentials.json"
        creds_file.write_text(json.dumps({"token": "abc"}))

        loaded = load_credentials()
        assert loaded is not None
        assert loaded.token == "abc"


class TestDeleteCredentials:
    def test_delete_removes_file(self, isolated_config_dir):
        mock_creds = _make_mock_credentials()
        save_credentials(mock_creds)
        assert has_credentials()

        delete_credentials()
        assert not has_credentials()

    def test_delete_noop_when_no_file(self, isolated_config_dir):
        # Should not raise
        delete_credentials()


class TestHasCredentials:
    def test_false_when_no_file(self, isolated_config_dir):
        assert not has_credentials()

    def test_true_after_save(self, isolated_config_dir):
        save_credentials(_make_mock_credentials())
        assert has_credentials()


class TestGetValidCredentials:
    def test_returns_none_when_no_file(self, isolated_config_dir):
        assert get_valid_credentials() is None

    def test_returns_credentials_when_not_expired(self, isolated_config_dir, monkeypatch):
        mock_creds = _make_mock_credentials()
        save_credentials(mock_creds)

        # Patch load_credentials to return a creds object that reports valid
        loaded = load_credentials()
        assert loaded is not None
        # Non-expired creds won't trigger refresh
        assert loaded.refresh_token == "test-refresh-token"


class TestChatScopeConstant:
    """The chat scope must be requested at login so new tokens carry it."""

    def test_chat_scope_is_in_oauth_scopes(self):
        from ga_cli.config.constants import CHAT_SCOPE, OAUTH_SCOPES

        assert CHAT_SCOPE == "https://www.googleapis.com/auth/analytics.chatbot.read"
        assert CHAT_SCOPE in OAUTH_SCOPES

    def test_existing_scopes_are_preserved(self):
        """Adding chat must not drop any scope users already rely on."""
        from ga_cli.config.constants import OAUTH_SCOPES

        for scope in (
            "openid",
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/analytics.edit",
            "https://www.googleapis.com/auth/analytics.manage.users",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ):
            assert scope in OAUTH_SCOPES


class TestHasScope:
    """has_scope() answers: do the credentials we would use carry this scope?

    It returns False only when stored OAuth credentials *demonstrably* lack
    the scope. Anything undeterminable returns True so that the caller's own
    authentication error surfaces instead of a misleading re-auth message.
    """

    def test_returns_true_when_stored_credentials_have_the_scope(self, isolated_config_dir):
        from ga_cli.auth.credentials import has_scope
        from ga_cli.config.constants import CHAT_SCOPE

        save_credentials(_make_mock_credentials(
            scopes=["https://www.googleapis.com/auth/analytics.readonly", CHAT_SCOPE]
        ))

        assert has_scope(CHAT_SCOPE) is True

    def test_returns_false_when_stored_credentials_lack_the_scope(self, isolated_config_dir):
        """The pre-0.3.0 upgrade case: a token granted before chat existed."""
        from ga_cli.auth.credentials import has_scope
        from ga_cli.config.constants import CHAT_SCOPE

        save_credentials(_make_mock_credentials(scopes=[
            "openid",
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/analytics.edit",
            "https://www.googleapis.com/auth/analytics.manage.users",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ]))

        assert has_scope(CHAT_SCOPE) is False

    def test_returns_true_when_no_credentials_are_stored(self, isolated_config_dir):
        """Undeterminable — let the real 'Not authenticated' error surface."""
        from ga_cli.auth.credentials import has_scope
        from ga_cli.config.constants import CHAT_SCOPE

        assert has_scope(CHAT_SCOPE) is True

    def test_returns_true_when_credentials_file_is_corrupt(self, isolated_config_dir):
        from ga_cli.auth.credentials import has_scope
        from ga_cli.config.constants import CHAT_SCOPE, get_credentials_path

        get_credentials_path().write_text("{not valid json")

        assert has_scope(CHAT_SCOPE) is True

    def test_returns_true_when_scopes_key_is_absent(self, isolated_config_dir):
        """A legacy file without a scopes list tells us nothing."""
        from ga_cli.auth.credentials import has_scope
        from ga_cli.config.constants import CHAT_SCOPE, get_credentials_path

        get_credentials_path().write_text(json.dumps({"token": "abc"}))

        assert has_scope(CHAT_SCOPE) is True

    def test_returns_true_for_service_accounts_lacking_stored_oauth_scope(
        self, isolated_config_dir, monkeypatch
    ):
        """Service account creds are built with OAUTH_SCOPES, so they always
        carry the scope — never tell an SA user to run 'ga auth login'."""
        from ga_cli.auth import service_account
        from ga_cli.auth.credentials import has_scope
        from ga_cli.config.constants import CHAT_SCOPE

        save_credentials(_make_mock_credentials(scopes=["openid"]))
        monkeypatch.setattr(
            service_account, "get_service_account_credentials", lambda: MagicMock()
        )

        assert has_scope(CHAT_SCOPE) is True
