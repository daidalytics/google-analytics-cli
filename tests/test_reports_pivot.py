"""Tests for pivot report command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_PIVOT_RESPONSE = {
    "pivotHeaders": [
        {
            "pivotDimensionHeaders": [
                {"dimensionValues": [{"value": "desktop"}]},
                {"dimensionValues": [{"value": "mobile"}]},
            ]
        }
    ],
    "dimensionHeaders": [
        {"name": "country"},
        {"name": "deviceCategory"},
    ],
    "metricHeaders": [
        {"name": "sessions"},
    ],
    "rows": [
        {
            "dimensionValues": [
                {"value": "United States"},
                {"value": "desktop"},
            ],
            "metricValues": [
                {"value": "1000"},
                {"value": "500"},
            ],
        },
        {
            "dimensionValues": [
                {"value": "United Kingdom"},
                {"value": "desktop"},
            ],
            "metricValues": [
                {"value": "300"},
                {"value": "200"},
            ],
        },
    ],
}


def _mock_data_client(pivot_response=None):
    mock_client = MagicMock()
    mock_client.properties.return_value.runPivotReport.return_value.execute.return_value = (
        pivot_response or SAMPLE_PIVOT_RESPONSE
    )
    return mock_client


class TestPivotReport:
    def test_pivot_basic_table(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "pivot",
                    "-p", "123",
                    "--metrics", "sessions",
                    "--dimensions", "country,deviceCategory",
                    "--pivot-field", "deviceCategory",
                ],
            )

        assert result.exit_code == 0
        assert "United States" in result.output

    def test_pivot_json_output(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "pivot",
                    "-p", "123",
                    "-m", "sessions",
                    "-d", "country,deviceCategory",
                    "--pivot-field", "deviceCategory",
                    "-o", "json",
                ],
            )

        assert result.exit_code == 0
        assert "pivotHeaders" in result.output

    def test_pivot_requires_metrics(self):
        result = runner.invoke(
            app,
            [
                "reports", "pivot",
                "-p", "123",
                "--dimensions", "country",
                "--pivot-field", "country",
            ],
        )

        assert result.exit_code != 0

    def test_pivot_requires_pivot_field(self):
        result = runner.invoke(
            app,
            [
                "reports", "pivot",
                "-p", "123",
                "--metrics", "sessions",
                "--dimensions", "country",
            ],
        )

        assert result.exit_code != 0

    def test_pivot_field_must_be_in_dimensions(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "pivot",
                    "-p", "123",
                    "-m", "sessions",
                    "-d", "country,browser",
                    "--pivot-field", "deviceCategory",
                ],
            )

        assert result.exit_code != 0

    def test_pivot_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_data_client()
        mock_client.properties.return_value.runPivotReport.return_value.execute.side_effect = (
            HttpError(
                resp=MagicMock(status=400),
                content=b'{"error": {"message": "Bad request"}}',
            )
        )

        with patch(
            "ga_cli.commands.reports.get_data_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "pivot",
                    "-p", "123",
                    "-m", "sessions",
                    "-d", "country,deviceCategory",
                    "--pivot-field", "deviceCategory",
                ],
            )

        assert result.exit_code == 3

    def test_pivot_empty_response(self):
        empty_response = {
            "pivotHeaders": [],
            "dimensionHeaders": [],
            "metricHeaders": [],
            "rows": [],
        }
        mock_client = _mock_data_client(pivot_response=empty_response)

        with patch(
            "ga_cli.commands.reports.get_data_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "pivot",
                    "-p", "123",
                    "-m", "sessions",
                    "-d", "country,deviceCategory",
                    "--pivot-field", "deviceCategory",
                ],
            )

        assert result.exit_code == 0
        assert "No data" in result.output

    def test_pivot_uses_config_property_id(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "pivot",
                    "-m", "sessions",
                    "-d", "country,deviceCategory",
                    "--pivot-field", "deviceCategory",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.runPivotReport.call_args
        assert call_args[1]["property"] == "properties/123"
