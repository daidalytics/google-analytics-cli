"""Tests for custom metrics commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_METRICS = [
    {
        "name": "properties/123/customMetrics/1",
        "parameterName": "revenue_per_user",
        "displayName": "Revenue Per User",
        "scope": "EVENT",
        "measurementUnit": "CURRENCY",
        "description": "Revenue per user",
    },
    {
        "name": "properties/123/customMetrics/2",
        "parameterName": "distance_walked",
        "displayName": "Distance Walked",
        "scope": "EVENT",
        "measurementUnit": "KILOMETERS",
        "description": "",
    },
    {
        "name": "properties/123/customMetrics/3",
        "parameterName": "load_time",
        "displayName": "Load Time",
        "scope": "EVENT",
        "measurementUnit": "MILLISECONDS",
        "description": "Page load time",
    },
]


def _mock_admin_client():
    """Create a mock Admin API client with customMetrics methods."""
    mock_client = MagicMock()
    cm = mock_client.properties.return_value.customMetrics.return_value

    cm.list.return_value.execute.return_value = {
        "customMetrics": SAMPLE_METRICS,
    }
    cm.get.return_value.execute.return_value = SAMPLE_METRICS[0]
    cm.create.return_value.execute.return_value = SAMPLE_METRICS[0]
    cm.patch.return_value.execute.return_value = SAMPLE_METRICS[0]
    cm.archive.return_value.execute.return_value = {}

    return mock_client


class TestCustomMetricsList:
    def test_list_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-metrics", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "CURRENCY" in result.output
        assert "KILOMETERS" in result.output
        assert "MILLISECONDS" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client()
        cm = mock_client.properties.return_value.customMetrics.return_value
        cm.list.return_value.execute.return_value = {"customMetrics": []}

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-metrics", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-metrics", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"parameterName"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cm = mock_client.properties.return_value.customMetrics.return_value
        cm.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-metrics", "list", "-p", "123"]
            )

        assert result.exit_code == 1

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["custom-metrics", "list"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["custom-metrics", "list"])

        assert result.exit_code == 0
        assert "CURRENCY" in result.output


class TestCustomMetricsGet:
    def test_get_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-metrics", "get", "-p", "123", "--metric-id", "1"],
            )

        assert result.exit_code == 0
        assert "CURRENCY" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-metrics", "get", "-p", "123", "-m", "1", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"measurementUnit"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cm = mock_client.properties.return_value.customMetrics.return_value
        cm.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-metrics", "get", "-p", "123", "-m", "999"],
            )

        assert result.exit_code == 1


class TestCustomMetricsCreate:
    def test_create_standard_unit(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "create",
                    "-p", "123",
                    "--parameter-name", "click_count",
                    "--display-name", "Click Count",
                    "--scope", "EVENT",
                    "--measurement-unit", "STANDARD",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.customMetrics.return_value
        body = cm.create.call_args[1]["body"]
        assert body["measurementUnit"] == "STANDARD"
        assert body["scope"] == "EVENT"

    def test_create_with_currency_unit(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "create",
                    "-p", "123",
                    "--parameter-name", "revenue",
                    "--display-name", "Revenue",
                    "--scope", "EVENT",
                    "--measurement-unit", "CURRENCY",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.customMetrics.return_value
        body = cm.create.call_args[1]["body"]
        assert body["measurementUnit"] == "CURRENCY"

    def test_create_invalid_scope(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "create",
                    "-p", "123",
                    "--parameter-name", "test",
                    "--display-name", "Test",
                    "--scope", "USER",
                    "--measurement-unit", "STANDARD",
                ],
            )

        assert result.exit_code != 0

    def test_create_invalid_measurement_unit(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "create",
                    "-p", "123",
                    "--parameter-name", "test",
                    "--display-name", "Test",
                    "--scope", "EVENT",
                    "--measurement-unit", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_create_requires_parameter_name(self):
        result = runner.invoke(
            app,
            [
                "custom-metrics", "create",
                "-p", "123",
                "--display-name", "Test",
                "--scope", "EVENT",
                "--measurement-unit", "STANDARD",
            ],
        )

        assert result.exit_code != 0

    def test_create_requires_display_name(self):
        result = runner.invoke(
            app,
            [
                "custom-metrics", "create",
                "-p", "123",
                "--parameter-name", "test",
                "--scope", "EVENT",
                "--measurement-unit", "STANDARD",
            ],
        )

        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cm = mock_client.properties.return_value.customMetrics.return_value
        cm.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "create",
                    "-p", "123",
                    "--parameter-name", "test",
                    "--display-name", "Test",
                    "--scope", "EVENT",
                    "--measurement-unit", "STANDARD",
                ],
            )

        assert result.exit_code == 1


class TestCustomMetricsUpdate:
    def test_update_display_name(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "update",
                    "-p", "123",
                    "-m", "1",
                    "--display-name", "New Name",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.customMetrics.return_value
        call_args = cm.patch.call_args
        assert call_args[1]["updateMask"] == "displayName"

    def test_update_measurement_unit(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "update",
                    "-p", "123",
                    "-m", "1",
                    "--measurement-unit", "METERS",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.customMetrics.return_value
        call_args = cm.patch.call_args
        assert call_args[1]["updateMask"] == "measurementUnit"
        assert call_args[1]["body"]["measurementUnit"] == "METERS"

    def test_update_invalid_measurement_unit(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "update",
                    "-p", "123",
                    "-m", "1",
                    "--measurement-unit", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_update_no_fields(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-metrics", "update", "-p", "123", "-m", "1"],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cm = mock_client.properties.return_value.customMetrics.return_value
        cm.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-metrics", "update",
                    "-p", "123",
                    "-m", "1",
                    "--display-name", "Fail",
                ],
            )

        assert result.exit_code == 1


class TestCustomMetricsArchive:
    def test_archive_with_yes(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-metrics", "archive", "-p", "123", "-m", "1", "--yes"],
            )

        assert result.exit_code == 0
        assert "archived" in result.output.lower()

    def test_archive_prompts_without_yes(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.custom_metrics.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.custom_metrics.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["custom-metrics", "archive", "-p", "123", "-m", "1"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_archive_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.custom_metrics.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.custom_metrics.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["custom-metrics", "archive", "-p", "123", "-m", "1"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_archive_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cm = mock_client.properties.return_value.customMetrics.return_value
        cm.archive.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.custom_metrics.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-metrics", "archive", "-p", "123", "-m", "1", "--yes"],
            )

        assert result.exit_code == 1
