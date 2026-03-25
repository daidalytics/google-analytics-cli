"""Tests for ga_cli.api.client."""

from unittest.mock import MagicMock, patch

import pytest

from ga_cli.api.client import (
    _get_credentials,
    clear_client_cache,
    get_admin_client,
    get_data_client,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure client cache is cleared between tests."""
    clear_client_cache()
    yield
    clear_client_cache()


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
