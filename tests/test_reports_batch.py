"""Tests for ga reports batch command."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()

SAMPLE_BATCH_RESPONSE = {
    "reports": [
        {
            "dimensionHeaders": [{"name": "date"}],
            "metricHeaders": [{"name": "sessions"}, {"name": "users"}],
            "rows": [
                {
                    "dimensionValues": [{"value": "20240101"}],
                    "metricValues": [{"value": "150"}, {"value": "100"}],
                },
            ],
            "rowCount": 1,
        },
        {
            "dimensionHeaders": [{"name": "eventName"}],
            "metricHeaders": [{"name": "eventCount"}],
            "rows": [
                {
                    "dimensionValues": [{"value": "page_view"}],
                    "metricValues": [{"value": "500"}],
                },
            ],
            "rowCount": 1,
        },
    ]
}

BATCH_CONFIG = {
    "reports": [
        {
            "metrics": ["sessions", "users"],
            "dimensions": ["date"],
            "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
            "limit": 100,
        },
        {
            "metrics": ["eventCount"],
            "dimensions": ["eventName"],
            "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
            "limit": 50,
        },
    ]
}


def _write_config(tmp_path, config):
    """Write a config dict to a temp JSON file and return the path."""
    path = tmp_path / "batch.json"
    path.write_text(json.dumps(config))
    return str(path)


def _mock_batch_execute(response=None):
    """Build a mock chain for batchRunReports().execute()."""
    mock_execute = MagicMock(return_value=response or SAMPLE_BATCH_RESPONSE)
    mock_batch = MagicMock()
    mock_batch.execute = mock_execute
    return mock_batch, mock_execute


class TestBatchReport:
    @patch("ga_cli.commands.reports.get_data_client")
    @patch("ga_cli.commands.reports.get_effective_value")
    def test_batch_two_reports_table(self, mock_gev, mock_client, tmp_path):
        def _gev(val, key):
            if val:
                return val
            return "12345" if key == "default_property_id" else None

        mock_gev.side_effect = _gev
        mock_batch, _ = _mock_batch_execute()
        mock_props = MagicMock()
        mock_props.batchRunReports.return_value = mock_batch
        mock_client.return_value.properties.return_value = mock_props

        config_path = _write_config(tmp_path, BATCH_CONFIG)
        result = runner.invoke(app, ["reports", "batch", "-p", "12345", "-c", config_path])

        assert result.exit_code == 0
        assert "Report 1" in result.output
        assert "Report 2" in result.output
        assert "sessions" in result.output
        assert "eventCount" in result.output

    @patch("ga_cli.commands.reports.get_data_client")
    @patch("ga_cli.commands.reports.get_effective_value")
    def test_batch_json_output(self, mock_gev, mock_client, tmp_path):
        mock_gev.side_effect = lambda val, key: val if val else "12345"
        mock_batch, _ = _mock_batch_execute()
        mock_props = MagicMock()
        mock_props.batchRunReports.return_value = mock_batch
        mock_client.return_value.properties.return_value = mock_props

        config_path = _write_config(tmp_path, BATCH_CONFIG)
        result = runner.invoke(
            app, ["reports", "batch", "-p", "12345", "-c", config_path, "-o", "json"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["reports"]) == 2

    def test_batch_requires_config_file(self):
        result = runner.invoke(app, ["reports", "batch", "-p", "12345"])
        assert result.exit_code != 0

    def test_batch_config_file_not_found(self):
        result = runner.invoke(
            app, ["reports", "batch", "-p", "12345", "-c", "/nonexistent/batch.json"]
        )
        assert result.exit_code != 0
        combined = result.output.lower() + str(result.exception or "").lower()
        assert "not found" in combined

    def test_batch_config_exceeds_5_reports(self, tmp_path):
        config = {
            "reports": [
                {
                    "metrics": ["sessions"],
                    "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
                }
                for _ in range(6)
            ]
        }
        config_path = _write_config(tmp_path, config)
        result = runner.invoke(app, ["reports", "batch", "-p", "12345", "-c", config_path])

        assert result.exit_code != 0
        assert "5" in result.output or "5" in str(result.exception or "")

    def test_batch_config_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json")
        result = runner.invoke(app, ["reports", "batch", "-p", "12345", "-c", str(path)])

        assert result.exit_code != 0

    @patch("ga_cli.commands.reports.get_data_client")
    @patch("ga_cli.commands.reports.get_effective_value")
    def test_batch_api_error(self, mock_gev, mock_client, tmp_path):
        from unittest.mock import PropertyMock

        from googleapiclient.errors import HttpError

        mock_gev.side_effect = lambda val, key: val if val else "12345"

        resp = MagicMock()
        type(resp).status = PropertyMock(return_value=403)
        resp.reason = "Forbidden"
        http_error = HttpError(resp, b'{"error": {"message": "quota exceeded"}}')

        mock_batch = MagicMock()
        mock_batch.execute.side_effect = http_error
        mock_props = MagicMock()
        mock_props.batchRunReports.return_value = mock_batch
        mock_client.return_value.properties.return_value = mock_props

        config_path = _write_config(tmp_path, BATCH_CONFIG)
        result = runner.invoke(app, ["reports", "batch", "-p", "12345", "-c", config_path])

        assert result.exit_code == 1

    def test_batch_empty_reports_array(self, tmp_path):
        config_path = _write_config(tmp_path, {"reports": []})
        result = runner.invoke(app, ["reports", "batch", "-p", "12345", "-c", config_path])

        assert result.exit_code != 0

    @patch("ga_cli.commands.reports.get_data_client")
    @patch("ga_cli.commands.reports.get_effective_value")
    def test_batch_uses_config_property_id(self, mock_gev, mock_client, tmp_path):
        def _gev(val, key):
            if key == "default_property_id" and not val:
                return "99999"
            return val or "table"

        mock_gev.side_effect = _gev
        mock_batch, _ = _mock_batch_execute()
        mock_props = MagicMock()
        mock_props.batchRunReports.return_value = mock_batch
        mock_client.return_value.properties.return_value = mock_props

        config_path = _write_config(tmp_path, BATCH_CONFIG)
        result = runner.invoke(app, ["reports", "batch", "-c", config_path])

        assert result.exit_code == 0
        mock_props.batchRunReports.assert_called_once()
        call_kwargs = mock_props.batchRunReports.call_args
        assert call_kwargs[1]["property"] == "properties/99999"
