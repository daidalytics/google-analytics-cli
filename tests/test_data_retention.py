"""Tests for data-retention commands (get, update)."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()

SAMPLE_SETTINGS = {
    "name": "properties/111111/dataRetentionSettings",
    "eventDataRetention": "FOURTEEN_MONTHS",
    "userDataRetention": "FOURTEEN_MONTHS",
    "resetUserDataOnNewActivity": True,
}


def _mock_admin_client(settings=None):
    mock_client = MagicMock()
    get_ret = mock_client.properties.return_value.getDataRetentionSettings
    get_ret.return_value.execute.return_value = settings or SAMPLE_SETTINGS
    upd_ret = mock_client.properties.return_value.updateDataRetentionSettings
    upd_ret.return_value.execute.return_value = settings or SAMPLE_SETTINGS
    return mock_client


class TestDataRetentionGet:
    def test_get_table_output(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["data-retention", "get", "--property-id", "111111"])

        assert result.exit_code == 0
        mock_client.properties.return_value.getDataRetentionSettings.assert_called_once_with(
            name="properties/111111/dataRetentionSettings"
        )

    def test_get_json_output(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["data-retention", "get", "-p", "111111", "-o", "json"])

        assert result.exit_code == 0
        assert "FOURTEEN_MONTHS" in result.output

    def test_get_requires_property_id(self):
        result = runner.invoke(app, ["data-retention", "get"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower() or "missing" in result.output.lower()

    def test_get_api_error(self):
        mock_client = MagicMock()
        get_ret = mock_client.properties.return_value.getDataRetentionSettings
        get_ret.return_value.execute.side_effect = Exception("Not found")

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["data-retention", "get", "-p", "999"])

        assert result.exit_code == 1
        assert "Not found" in result.output


class TestDataRetentionUpdate:
    def test_update_event_retention(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "data-retention",
                    "update",
                    "-p",
                    "111111",
                    "--event-data-retention",
                    "TWO_MONTHS",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.updateDataRetentionSettings.call_args
        assert call_args[1]["updateMask"] == "eventDataRetention"
        assert call_args[1]["body"]["eventDataRetention"] == "TWO_MONTHS"

    def test_update_user_retention(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "data-retention",
                    "update",
                    "-p",
                    "111111",
                    "--user-data-retention",
                    "FOURTEEN_MONTHS",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.updateDataRetentionSettings.call_args
        assert call_args[1]["updateMask"] == "userDataRetention"

    def test_update_reset_flag(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "data-retention",
                    "update",
                    "-p",
                    "111111",
                    "--reset-on-new-activity",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.updateDataRetentionSettings.call_args
        assert call_args[1]["body"]["resetUserDataOnNewActivity"] is True

    def test_update_no_reset_flag(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "data-retention",
                    "update",
                    "-p",
                    "111111",
                    "--no-reset-on-new-activity",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.updateDataRetentionSettings.call_args
        assert call_args[1]["body"]["resetUserDataOnNewActivity"] is False

    def test_update_multiple_fields(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "data-retention",
                    "update",
                    "-p",
                    "111111",
                    "--event-data-retention",
                    "TWO_MONTHS",
                    "--reset-on-new-activity",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.updateDataRetentionSettings.call_args
        mask = call_args[1]["updateMask"]
        assert "eventDataRetention" in mask
        assert "resetUserDataOnNewActivity" in mask

    def test_update_no_fields_fails(self):
        result = runner.invoke(app, ["data-retention", "update", "-p", "111111"])

        assert result.exit_code != 0

    def test_update_invalid_retention_value(self):
        result = runner.invoke(
            app,
            [
                "data-retention",
                "update",
                "-p",
                "111111",
                "--event-data-retention",
                "INVALID_VALUE",
            ],
        )

        assert result.exit_code != 0

    def test_update_requires_property_id(self):
        result = runner.invoke(
            app, ["data-retention", "update", "--event-data-retention", "TWO_MONTHS"]
        )

        assert result.exit_code != 0
        assert "property-id" in result.output.lower() or "missing" in result.output.lower()

    def test_update_api_error(self):
        mock_client = MagicMock()
        upd_ret = mock_client.properties.return_value.updateDataRetentionSettings
        upd_ret.return_value.execute.side_effect = Exception("Permission denied")

        with patch("ga_cli.commands.data_retention.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "data-retention",
                    "update",
                    "-p",
                    "111111",
                    "--event-data-retention",
                    "TWO_MONTHS",
                ],
            )

        assert result.exit_code == 1
        assert "Permission denied" in result.output
