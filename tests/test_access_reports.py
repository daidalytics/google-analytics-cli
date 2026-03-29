"""Tests for access-reports commands (run-account, run-property)."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()

SAMPLE_ACCESS_REPORT = {
    "dimensionHeaders": [
        {"dimensionName": "userEmail"},
        {"dimensionName": "epochTimeMicros"},
    ],
    "metricHeaders": [
        {"metricName": "accessCount"},
    ],
    "rows": [
        {
            "dimensionValues": [
                {"value": "admin@example.com"},
                {"value": "1700000000000000"},
            ],
            "metricValues": [{"value": "42"}],
        },
        {
            "dimensionValues": [
                {"value": "analyst@example.com"},
                {"value": "1700001000000000"},
            ],
            "metricValues": [{"value": "7"}],
        },
    ],
    "rowCount": 2,
}


def _mock_admin_client(report_result=None):
    mock_client = MagicMock()
    response = report_result if report_result is not None else SAMPLE_ACCESS_REPORT
    mock_client.accounts.return_value.runAccessReport.return_value.execute.return_value = response
    mock_client.properties.return_value.runAccessReport.return_value.execute.return_value = response
    return mock_client


class TestAccessReportsRunAccount:
    def test_run_table_output(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["access-reports", "run-account", "--account-id", "123456"])

        assert result.exit_code == 0
        assert "admin@example.com" in result.output
        assert "analyst@example.com" in result.output

    def test_run_json_output(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["access-reports", "run-account", "-a", "123456", "-o", "json"]
            )

        assert result.exit_code == 0
        assert "admin@example.com" in result.output

    def test_run_custom_dimensions_metrics(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "access-reports",
                    "run-account",
                    "-a",
                    "123456",
                    "--dimensions",
                    "userEmail",
                    "--metrics",
                    "accessCount",
                    "--start-date",
                    "30daysAgo",
                    "--end-date",
                    "today",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.accounts.return_value.runAccessReport.call_args
        body = call_args[1]["body"]
        assert body["dimensions"] == [{"dimensionName": "userEmail"}]
        assert body["metrics"] == [{"metricName": "accessCount"}]

    def test_run_empty_results(self):
        empty_report = {"dimensionHeaders": [], "metricHeaders": [], "rows": []}
        mock_client = _mock_admin_client(report_result=empty_report)

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["access-reports", "run-account", "-a", "123456"])

        assert result.exit_code == 0
        assert "No access data found" in result.output

    def test_run_requires_account_id(self):
        result = runner.invoke(app, ["access-reports", "run-account"])

        assert result.exit_code != 0
        assert "account-id" in result.output.lower() or "missing" in result.output.lower()

    def test_run_api_error(self):
        mock_client = MagicMock()
        mock_client.accounts.return_value.runAccessReport.return_value.execute.side_effect = (
            Exception("Insufficient permissions")
        )

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["access-reports", "run-account", "-a", "123456"])

        assert result.exit_code == 1
        assert "Insufficient permissions" in result.output

    def test_run_with_include_all_users(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "access-reports",
                    "run-account",
                    "-a",
                    "123456",
                    "--include-all-users",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.accounts.return_value.runAccessReport.call_args
        body = call_args[1]["body"]
        assert body["includeAllUsers"] is True


class TestAccessReportsRunProperty:
    def test_run_table_output(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["access-reports", "run-property", "--property-id", "111111"]
            )

        assert result.exit_code == 0
        assert "admin@example.com" in result.output

    def test_run_json_output(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["access-reports", "run-property", "-p", "111111", "-o", "json"]
            )

        assert result.exit_code == 0
        assert "admin@example.com" in result.output

    def test_run_requires_property_id(self):
        result = runner.invoke(app, ["access-reports", "run-property"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower() or "missing" in result.output.lower()

    def test_run_empty_results(self):
        empty_report = {"dimensionHeaders": [], "metricHeaders": [], "rows": []}
        mock_client = _mock_admin_client(report_result=empty_report)

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["access-reports", "run-property", "-p", "111111"])

        assert result.exit_code == 0
        assert "No access data found" in result.output

    def test_run_api_error(self):
        mock_client = MagicMock()
        mock_client.properties.return_value.runAccessReport.return_value.execute.side_effect = (
            Exception("Not found")
        )

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["access-reports", "run-property", "-p", "999"])

        assert result.exit_code == 1
        assert "Not found" in result.output

    def test_run_with_offset(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.access_reports.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "access-reports",
                    "run-property",
                    "-p",
                    "111111",
                    "--offset",
                    "100",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.runAccessReport.call_args
        body = call_args[1]["body"]
        assert body["offset"] == 100
