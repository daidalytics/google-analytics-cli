"""Tests for ga reports funnel command."""

import json
import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)

SAMPLE_FUNNEL_RESPONSE = {
    "funnelTable": {
        "dimensionHeaders": [{"name": "funnelStepName"}],
        "metricHeaders": [
            {"name": "activeUsers"},
            {"name": "funnelStepCompletionRate"},
            {"name": "funnelStepAbandonmentRate"},
        ],
        "rows": [
            {
                "dimensionValues": [{"value": "First visit"}],
                "metricValues": [
                    {"value": "1000"},
                    {"value": "0.45"},
                    {"value": "0.55"},
                ],
            },
            {
                "dimensionValues": [{"value": "Add to cart"}],
                "metricValues": [
                    {"value": "450"},
                    {"value": "0.67"},
                    {"value": "0.33"},
                ],
            },
        ],
    }
}

FUNNEL_CONFIG = {
    "funnel": {
        "steps": [
            {
                "name": "First visit",
                "filterExpression": {
                    "eventFilter": {"eventName": "first_visit"}
                },
            },
            {
                "name": "Add to cart",
                "filterExpression": {
                    "eventFilter": {"eventName": "add_to_cart"}
                },
            },
        ]
    },
    "dateRanges": [{"startDate": "28daysAgo", "endDate": "yesterday"}],
}


def _write_config(tmp_path, config):
    """Write a config dict to a temp JSON file and return the path."""
    path = tmp_path / "funnel.json"
    path.write_text(json.dumps(config))
    return str(path)


def _mock_funnel_client(response=None):
    """Build a mock Data Alpha client for runFunnelReport."""
    mock_client = MagicMock()
    mock_client.properties.return_value.runFunnelReport.return_value.execute.return_value = (
        response or SAMPLE_FUNNEL_RESPONSE
    )
    return mock_client


class TestFunnelReport:
    def test_funnel_table_output(self, tmp_path):
        mock_client = _mock_funnel_client()
        config_path = _write_config(tmp_path, FUNNEL_CONFIG)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "funnel", "-p", "111", "-c", config_path]
            )

        assert result.exit_code == 0
        assert "First visit" in result.output
        assert "Add to cart" in result.output
        assert "1000" in result.output
        assert "450" in result.output

    def test_funnel_json_output(self, tmp_path):
        mock_client = _mock_funnel_client()
        config_path = _write_config(tmp_path, FUNNEL_CONFIG)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "funnel", "-p", "111", "-c", config_path, "-o", "json"]
            )

        assert result.exit_code == 0
        assert "funnelTable" in result.output

    def test_funnel_config_not_found(self):
        result = runner.invoke(
            app, ["reports", "funnel", "-p", "111", "-c", "/nonexistent/funnel.json"]
        )
        assert result.exit_code != 0
        combined = result.output.lower() + str(result.exception or "").lower()
        assert "not found" in combined

    def test_funnel_config_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json")
        result = runner.invoke(
            app, ["reports", "funnel", "-p", "111", "-c", str(path)]
        )
        assert result.exit_code != 0

    def test_funnel_config_missing_steps(self, tmp_path):
        config_path = _write_config(tmp_path, {"funnel": {}})
        result = runner.invoke(
            app, ["reports", "funnel", "-p", "111", "-c", config_path]
        )
        assert result.exit_code != 0

    def test_funnel_config_missing_funnel_key(self, tmp_path):
        config_path = _write_config(tmp_path, {"dateRanges": []})
        result = runner.invoke(
            app, ["reports", "funnel", "-p", "111", "-c", config_path]
        )
        assert result.exit_code != 0

    def test_funnel_config_empty_steps(self, tmp_path):
        config_path = _write_config(tmp_path, {"funnel": {"steps": []}})
        result = runner.invoke(
            app, ["reports", "funnel", "-p", "111", "-c", config_path]
        )
        assert result.exit_code != 0

    def test_funnel_api_error(self, tmp_path):
        mock_client = MagicMock()
        mock_client.properties.return_value.runFunnelReport.return_value.execute.side_effect = (
            Exception("Funnel API error")
        )
        config_path = _write_config(tmp_path, FUNNEL_CONFIG)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "funnel", "-p", "111", "-c", config_path]
            )

        assert result.exit_code == 1
        assert "Funnel API error" in result.output

    def test_funnel_uses_config_default(self, tmp_path):
        save_config(UserConfig(default_property_id="111"))
        mock_client = _mock_funnel_client()
        config_path = _write_config(tmp_path, FUNNEL_CONFIG)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "funnel", "-c", config_path]
            )

        assert result.exit_code == 0

    def test_funnel_missing_property_id(self, tmp_path):
        config_path = _write_config(tmp_path, FUNNEL_CONFIG)
        result = runner.invoke(
            app, ["reports", "funnel", "-c", config_path]
        )
        assert result.exit_code != 0
        assert "property-id" in _strip_ansi(result.output).lower()

    def test_funnel_passes_full_config_as_body(self, tmp_path):
        mock_client = _mock_funnel_client()
        config_path = _write_config(tmp_path, FUNNEL_CONFIG)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            runner.invoke(
                app, ["reports", "funnel", "-p", "999", "-c", config_path]
            )

        call_args = mock_client.properties.return_value.runFunnelReport.call_args
        assert call_args[1]["property"] == "properties/999"
        assert call_args[1]["body"] == FUNNEL_CONFIG

    def test_funnel_empty_response(self, tmp_path):
        mock_client = _mock_funnel_client(response={"funnelTable": {}})
        config_path = _write_config(tmp_path, FUNNEL_CONFIG)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "funnel", "-p", "111", "-c", config_path]
            )

        assert result.exit_code == 0
        assert "No funnel data" in result.output

    def test_funnel_requires_config(self):
        result = runner.invoke(app, ["reports", "funnel", "-p", "111"])
        assert result.exit_code != 0
