"""Tests for calculated metrics commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_METRICS = [
    {
        "name": "properties/123/calculatedMetrics/revenuePerUser",
        "calculatedMetricId": "revenuePerUser",
        "displayName": "Revenue Per User",
        "description": "Average revenue per user",
        "formula": "{{totalRevenue}} / {{totalUsers}}",
        "metricUnit": "CURRENCY",
    },
    {
        "name": "properties/123/calculatedMetrics/engagementScore",
        "calculatedMetricId": "engagementScore",
        "displayName": "Engagement Score",
        "description": "",
        "formula": "{{engagedSessions}} / {{sessions}}",
        "metricUnit": "STANDARD",
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with calculatedMetrics methods."""
    mock_client = MagicMock()
    cm = mock_client.properties.return_value.calculatedMetrics.return_value

    cm.list.return_value.execute.return_value = {
        "calculatedMetrics": SAMPLE_METRICS,
    }
    cm.get.return_value.execute.return_value = SAMPLE_METRICS[0]
    cm.create.return_value.execute.return_value = SAMPLE_METRICS[0]
    cm.patch.return_value.execute.return_value = SAMPLE_METRICS[0]
    cm.delete.return_value.execute.return_value = {}

    return mock_client


class TestCalculatedMetricsList:
    def test_list_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["calculated-metrics", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "Revenue Per" in result.output
        assert "Engagement" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.list.return_value.execute.return_value = {"calculatedMetrics": []}

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["calculated-metrics", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["calculated-metrics", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"calculatedMetricId"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["calculated-metrics", "list", "-p", "123"]
            )

        assert result.exit_code == 2

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["calculated-metrics", "list"])
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["calculated-metrics", "list"])

        assert result.exit_code == 0
        assert "Revenue Per" in result.output


class TestCalculatedMetricsGet:
    def test_get_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["calculated-metrics", "get", "-p", "123", "--metric-id", "revenuePerUser"],
            )

        assert result.exit_code == 0
        assert "Revenue Per" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["calculated-metrics", "get", "-p", "123", "-m", "revenuePerUser", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"formula"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["calculated-metrics", "get", "-p", "123", "-m", "missing"],
            )

        assert result.exit_code == 3


class TestCalculatedMetricsCreate:
    def test_create_basic(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "create",
                    "-p", "123",
                    "--calculated-metric-id", "revenuePerUser",
                    "--display-name", "Revenue Per User",
                    "--formula", "{{totalRevenue}} / {{totalUsers}}",
                    "--metric-unit", "CURRENCY",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        call_args = cm.create.call_args
        assert call_args[1]["calculatedMetricId"] == "revenuePerUser"
        body = call_args[1]["body"]
        assert body["displayName"] == "Revenue Per User"
        assert body["formula"] == "{{totalRevenue}} / {{totalUsers}}"
        assert body["metricUnit"] == "CURRENCY"

    def test_create_with_description(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "create",
                    "-p", "123",
                    "--calculated-metric-id", "revenuePerUser",
                    "--display-name", "Revenue Per User",
                    "--formula", "{{totalRevenue}} / {{totalUsers}}",
                    "--metric-unit", "CURRENCY",
                    "--description", "Avg revenue per user",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        body = cm.create.call_args[1]["body"]
        assert body["description"] == "Avg revenue per user"

    def test_create_invalid_metric_unit(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "create",
                    "-p", "123",
                    "--calculated-metric-id", "test",
                    "--display-name", "Test",
                    "--formula", "{{sessions}}",
                    "--metric-unit", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_create_case_insensitive_unit(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "create",
                    "-p", "123",
                    "--calculated-metric-id", "test",
                    "--display-name", "Test",
                    "--formula", "{{sessions}}",
                    "--metric-unit", "standard",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        body = cm.create.call_args[1]["body"]
        assert body["metricUnit"] == "STANDARD"

    def test_create_requires_formula(self):
        result = runner.invoke(
            app,
            [
                "calculated-metrics", "create",
                "-p", "123",
                "--calculated-metric-id", "test",
                "--display-name", "Test",
                "--metric-unit", "STANDARD",
            ],
        )
        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "create",
                    "-p", "123",
                    "--calculated-metric-id", "test",
                    "--display-name", "Test",
                    "--formula", "{{sessions}}",
                    "--metric-unit", "STANDARD",
                ],
            )

        assert result.exit_code == 3


class TestCalculatedMetricsUpdate:
    def test_update_display_name(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "update",
                    "-p", "123",
                    "-m", "revenuePerUser",
                    "--display-name", "New Name",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        call_args = cm.patch.call_args
        assert call_args[1]["updateMask"] == "displayName"
        assert call_args[1]["body"]["displayName"] == "New Name"

    def test_update_formula(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "update",
                    "-p", "123",
                    "-m", "revenuePerUser",
                    "--formula", "{{totalRevenue}} / {{activeUsers}}",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        assert cm.patch.call_args[1]["updateMask"] == "formula"

    def test_update_metric_unit(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "update",
                    "-p", "123",
                    "-m", "revenuePerUser",
                    "--metric-unit", "STANDARD",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        assert cm.patch.call_args[1]["updateMask"] == "metricUnit"

    def test_update_multiple_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "update",
                    "-p", "123",
                    "-m", "revenuePerUser",
                    "--display-name", "New Name",
                    "--formula", "new formula",
                    "--description", "New desc",
                ],
            )

        assert result.exit_code == 0
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        mask = cm.patch.call_args[1]["updateMask"]
        assert "displayName" in mask
        assert "formula" in mask
        assert "description" in mask

    def test_update_no_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["calculated-metrics", "update", "-p", "123", "-m", "revenuePerUser"],
            )

        assert result.exit_code != 0

    def test_update_invalid_metric_unit(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "update",
                    "-p", "123",
                    "-m", "revenuePerUser",
                    "--metric-unit", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "calculated-metrics", "update",
                    "-p", "123",
                    "-m", "revenuePerUser",
                    "--display-name", "Fail",
                ],
            )

        assert result.exit_code == 3


class TestCalculatedMetricsDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["calculated-metrics", "delete", "-p", "123", "-m", "revenuePerUser", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.delete.assert_called_once()

    def test_delete_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.calculated_metrics.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["calculated-metrics", "delete", "-p", "123", "-m", "revenuePerUser"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.calculated_metrics.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["calculated-metrics", "delete", "-p", "123", "-m", "revenuePerUser"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.delete.assert_not_called()

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cm = mock_client.properties.return_value.calculatedMetrics.return_value
        cm.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.calculated_metrics.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["calculated-metrics", "delete", "-p", "123", "-m", "revenuePerUser", "--yes"],
            )

        assert result.exit_code == 3
