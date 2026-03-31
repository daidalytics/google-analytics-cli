"""Tests for property settings commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_ATTRIBUTION = {
    "name": "properties/123/attributionSettings",
    "acquisitionConversionEventLookbackWindow": "ACQUISITION_CONVERSION_EVENT_LOOKBACK_WINDOW_30_DAYS",
    "otherConversionEventLookbackWindow": "OTHER_CONVERSION_EVENT_LOOKBACK_WINDOW_90_DAYS",
    "reportingAttributionModel": "PAID_AND_ORGANIC_CHANNELS_DATA_DRIVEN",
    "adsWebConversionDataExportScope": "PAID_AND_ORGANIC_CHANNELS",
}

SAMPLE_SIGNALS = {
    "name": "properties/123/googleSignalsSettings",
    "state": "GOOGLE_SIGNALS_ENABLED",
    "consent": "GOOGLE_SIGNALS_CONSENT_CONSENTED",
}

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


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with settings methods."""
    mock_client = MagicMock()
    props = mock_client.properties.return_value

    # Attribution
    props.getAttributionSettings.return_value.execute.return_value = SAMPLE_ATTRIBUTION
    props.updateAttributionSettings.return_value.execute.return_value = SAMPLE_ATTRIBUTION

    # Google Signals
    props.getGoogleSignalsSettings.return_value.execute.return_value = SAMPLE_SIGNALS
    props.updateGoogleSignalsSettings.return_value.execute.return_value = SAMPLE_SIGNALS

    # Enhanced Measurement (nested under dataStreams)
    ds = props.dataStreams.return_value
    ds.getEnhancedMeasurementSettings.return_value.execute.return_value = SAMPLE_ENHANCED
    ds.updateEnhancedMeasurementSettings.return_value.execute.return_value = SAMPLE_ENHANCED

    return mock_client


# --- Attribution Settings ---


class TestAttributionSettings:
    def test_get(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "attribution", "-p", "123"],
            )

        assert result.exit_code == 0
        mock_client.properties.return_value.getAttributionSettings.assert_called_once()

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "attribution", "-p", "123", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"reportingAttributionModel"' in result.output

    def test_get_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "attribution"],
            )

        assert result.exit_code == 0

    def test_update_attribution_model(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "attribution", "-p", "123",
                    "--attribution-model", "PAID_AND_ORGANIC_CHANNELS_LAST_CLICK",
                ],
            )

        assert result.exit_code == 0
        assert "updated" in result.output.lower()
        props = mock_client.properties.return_value
        call_args = props.updateAttributionSettings.call_args[1]
        assert call_args["body"]["reportingAttributionModel"] == "PAID_AND_ORGANIC_CHANNELS_LAST_CLICK"
        assert "reportingAttributionModel" in call_args["updateMask"]

    def test_update_multiple_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "attribution", "-p", "123",
                    "--acquisition-lookback", "ACQUISITION_CONVERSION_EVENT_LOOKBACK_WINDOW_7_DAYS",
                    "--other-lookback", "OTHER_CONVERSION_EVENT_LOOKBACK_WINDOW_60_DAYS",
                ],
            )

        assert result.exit_code == 0
        props = mock_client.properties.return_value
        call_args = props.updateAttributionSettings.call_args[1]
        assert "acquisitionConversionEventLookbackWindow" in call_args["updateMask"]
        assert "otherConversionEventLookbackWindow" in call_args["updateMask"]

    def test_update_invalid_model(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "attribution", "-p", "123",
                    "--attribution-model", "INVALID_MODEL",
                ],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        props = mock_client.properties.return_value
        props.updateAttributionSettings.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "attribution", "-p", "123",
                    "--attribution-model", "PAID_AND_ORGANIC_CHANNELS_DATA_DRIVEN",
                ],
            )

        assert result.exit_code == 1

    def test_missing_property_id(self):
        result = runner.invoke(
            app, ["property-settings", "attribution"]
        )
        assert result.exit_code != 0


# --- Google Signals Settings ---


class TestGoogleSignalsSettings:
    def test_get(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "google-signals", "-p", "123"],
            )

        assert result.exit_code == 0
        mock_client.properties.return_value.getGoogleSignalsSettings.assert_called_once()

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "google-signals", "-p", "123", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"consent"' in result.output

    def test_update_state(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "google-signals", "-p", "123",
                    "--state", "GOOGLE_SIGNALS_DISABLED",
                ],
            )

        assert result.exit_code == 0
        assert "updated" in result.output.lower()
        props = mock_client.properties.return_value
        call_args = props.updateGoogleSignalsSettings.call_args[1]
        assert call_args["body"]["state"] == "GOOGLE_SIGNALS_DISABLED"
        assert call_args["updateMask"] == "state"

    def test_update_invalid_state(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "google-signals", "-p", "123",
                    "--state", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        props = mock_client.properties.return_value
        props.updateGoogleSignalsSettings.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "google-signals", "-p", "123",
                    "--state", "GOOGLE_SIGNALS_ENABLED",
                ],
            )

        assert result.exit_code == 1


# --- Enhanced Measurement Settings ---


class TestEnhancedMeasurementSettings:
    def test_get(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "enhanced-measurement", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 0
        ds = mock_client.properties.return_value.dataStreams.return_value
        ds.getEnhancedMeasurementSettings.assert_called_once()

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "enhanced-measurement", "-p", "123", "-s", "456", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"scrollsEnabled"' in result.output

    def test_update_single_boolean(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "enhanced-measurement",
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

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "enhanced-measurement",
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

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "enhanced-measurement",
                    "-p", "123", "-s", "456",
                    "--search-query-parameter", "q,search,query",
                ],
            )

        assert result.exit_code == 0
        ds = mock_client.properties.return_value.dataStreams.return_value
        call_args = ds.updateEnhancedMeasurementSettings.call_args[1]
        assert call_args["body"]["searchQueryParameter"] == "q,search,query"

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ds = mock_client.properties.return_value.dataStreams.return_value
        ds.updateEnhancedMeasurementSettings.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "property-settings", "enhanced-measurement",
                    "-p", "123", "-s", "456",
                    "--no-scrolls",
                ],
            )

        assert result.exit_code == 1

    def test_missing_stream_id(self):
        result = runner.invoke(
            app,
            ["property-settings", "enhanced-measurement", "-p", "123"],
        )
        assert result.exit_code != 0

    def test_get_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.property_settings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["property-settings", "enhanced-measurement", "-s", "456"],
            )

        assert result.exit_code == 0
