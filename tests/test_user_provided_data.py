"""Tests for user-provided-data commands (get)."""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


SAMPLE_SETTINGS = {
    "name": "properties/111111/userProvidedDataSettings",
    "userProvidedDataCollectionEnabled": True,
    "automaticallyDetectedDataCollectionEnabled": False,
}


def _mock_admin_alpha_client(settings=None):
    mock_client = MagicMock()
    get_ret = mock_client.properties.return_value.getUserProvidedDataSettings
    get_ret.return_value.execute.return_value = settings or SAMPLE_SETTINGS
    return mock_client


class TestUserProvidedDataGet:
    def test_get_table_output(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.user_provided_data.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["user-provided-data", "get", "--property-id", "111111"]
            )

        assert result.exit_code == 0
        mock_client.properties.return_value.getUserProvidedDataSettings.assert_called_once_with(
            name="properties/111111/userProvidedDataSettings"
        )

    def test_get_json_output(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.user_provided_data.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["user-provided-data", "get", "-p", "111111", "-o", "json"]
            )

        assert result.exit_code == 0
        assert "userProvidedDataCollectionEnabled" in result.output

    def test_get_requires_property_id(self):
        result = runner.invoke(app, ["user-provided-data", "get"])

        assert result.exit_code != 0
        assert "property-id" in _strip_ansi(result.output).lower()

    def test_get_api_error(self):
        mock_client = MagicMock()
        get_ret = mock_client.properties.return_value.getUserProvidedDataSettings
        get_ret.return_value.execute.side_effect = Exception("Not found")

        with patch(
            "ga_cli.commands.user_provided_data.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["user-provided-data", "get", "-p", "999"]
            )

        assert result.exit_code == 3
        assert "Not found" in result.output
