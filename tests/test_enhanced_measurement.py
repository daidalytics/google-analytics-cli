"""Tests for enhanced measurement settings commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_ENHANCED = {
    "name": "properties/123/dataStreams/456/enhancedMeasurementSettings",
    "streamEnabled": True,
    "scrollsEnabled": True,
    "outboundClicksEnabled": True,
    "siteSearchEnabled": True,
    "videoEngagementEnabled": True,
    "fileDownloadsEnabled": True,
    "pageChangesEnabled": True,
    "formInteractionsEnabled": False,
    "searchQueryParameter": "q,s,search",
    "uriQueryParameter": "",
}

_PATCH_TARGET = "ga_cli.commands.enhanced_measurement.get_admin_alpha_client"


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with enhanced measurement methods."""
    mock_client = MagicMock()
    ds = mock_client.properties.return_value.dataStreams.return_value
    ds.getEnhancedMeasurementSettings.return_value.execute.return_value = SAMPLE_ENHANCED
    ds.updateEnhancedMeasurementSettings.return_value.execute.return_value = SAMPLE_ENHANCED
    return mock_client


class TestEnhancedMeasurementGet:
    def test_get(self):
        mock_client = _mock_admin_alpha_client()

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = runner.invoke(
                app,
                ["enhanced-measurement", "get", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 0
        ds = mock_client.properties.return_value.dataStreams.return_value
        ds.getEnhancedMeasurementSettings.assert_called_once()

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "enhanced-measurement", "get",
                    "-p", "123", "-s", "456", "-o", "json",
                ],
            )

        assert result.exit_code == 0
        assert '"scrollsEnabled"' in result.output

    def test_get_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = runner.invoke(
                app,
                ["enhanced-measurement", "get", "-s", "456"],
            )

        assert result.exit_code == 0

    def test_missing_stream_id(self):
        result = runner.invoke(
            app,
            ["enhanced-measurement", "get", "-p", "123"],
        )
        assert result.exit_code != 0


class TestEnhancedMeasurementUpdate:
    def test_update_single_boolean(self):
        mock_client = _mock_admin_alpha_client()

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "enhanced-measurement", "update",
                    "-p", "123", "-s", "456",
                    "--no-scrolls",
                ],
            )

        assert result.exit_code == 0
        assert "updated" in result.output.lower()
        ds = mock_client.properties.return_value.dataStreams.return_value
        call_args = ds.updateEnhancedMeasurementSettings.call_args[1]
        assert call_args["body"]["scrollsEnabled"] is False
        assert "scrollsEnabled" in call_args["updateMask"]

    def test_update_multiple_booleans(self):
        mock_client = _mock_admin_alpha_client()

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "enhanced-measurement", "update",
                    "-p", "123", "-s", "456",
                    "--form-interactions",
                    "--no-video-engagement",
                ],
            )

        assert result.exit_code == 0
        ds = mock_client.properties.return_value.dataStreams.return_value
        call_args = ds.updateEnhancedMeasurementSettings.call_args[1]
        assert call_args["body"]["formInteractionsEnabled"] is True
        assert call_args["body"]["videoEngagementEnabled"] is False

    def test_update_search_query_parameter(self):
        mock_client = _mock_admin_alpha_client()

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "enhanced-measurement", "update",
                    "-p", "123", "-s", "456",
                    "--search-query-parameter", "q,search,query",
                ],
            )

        assert result.exit_code == 0
        ds = mock_client.properties.return_value.dataStreams.return_value
        call_args = ds.updateEnhancedMeasurementSettings.call_args[1]
        assert call_args["body"]["searchQueryParameter"] == "q,search,query"

    def test_update_no_flags_errors(self):
        result = runner.invoke(
            app,
            ["enhanced-measurement", "update", "-p", "123", "-s", "456"],
        )
        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ds = mock_client.properties.return_value.dataStreams.return_value
        ds.updateEnhancedMeasurementSettings.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "enhanced-measurement", "update",
                    "-p", "123", "-s", "456",
                    "--no-scrolls",
                ],
            )

        assert result.exit_code == 3

    def test_missing_stream_id(self):
        result = runner.invoke(
            app,
            ["enhanced-measurement", "update", "-p", "123", "--no-scrolls"],
        )
        assert result.exit_code != 0
