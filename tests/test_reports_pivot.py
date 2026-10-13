"""Tests for pivot report command."""

from unittest.mock import MagicMock, patch

import pytest
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

    def test_pivot_limit_defaults_to_five_and_is_configurable(self):
        for extra, expected in (([], 5), (["--pivot-limit", "20"], 20)):
            mock_client = _mock_data_client()
            with patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ):
                runner.invoke(
                    app,
                    [
                        "reports", "pivot", "-p", "123", "-m", "sessions",
                        "-d", "country,deviceCategory", "--pivot-field", "country",
                        "--limit", "50", *extra, "-o", "json",
                    ],
                )
            body = mock_client.properties.return_value.runPivotReport.call_args[1]["body"]
            assert body["pivots"] == [
                {"fieldNames": ["country"], "limit": expected},
                {"fieldNames": ["deviceCategory"], "limit": 50},
            ]

    def _invoke_pivot(self, *args):
        mock_client = _mock_data_client()
        with patch("ga_cli.commands.reports.get_data_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["reports", "pivot", "-p", "123", "-m", "sessions",
                 "-d", "country,deviceCategory", "--pivot-field", "deviceCategory", *args],
            )
        return result, mock_client

    @pytest.mark.parametrize("flag", ["--pivot-limit", "--limit"])
    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_limits_must_be_positive(self, flag, value):
        result, mock_client = self._invoke_pivot(flag, value)
        assert result.exit_code == 2
        mock_client.properties.return_value.runPivotReport.assert_not_called()

    def test_limit_product_capped(self):
        result, mock_client = self._invoke_pivot("--pivot-limit", "5000", "--limit", "100")
        assert result.exit_code == 2
        assert "250,000" in result.output
        mock_client.properties.return_value.runPivotReport.assert_not_called()

    def test_limit_product_at_cap_allowed(self):
        result, _ = self._invoke_pivot("--pivot-limit", "2500", "--limit", "100", "-o", "json")
        assert result.exit_code == 0

    def test_start_today_ends_today(self):
        _, mock_client = self._invoke_pivot("--start-date", "today", "-o", "json")
        body = mock_client.properties.return_value.runPivotReport.call_args[1]["body"]
        assert body["dateRanges"] == [{"startDate": "today", "endDate": "today"}]

    def test_compact_output_is_tsv(self):
        result, _ = self._invoke_pivot("-o", "compact")
        assert result.exit_code == 0
        assert result.stdout.splitlines() == [
            "country\tdesktop_sessions\tmobile_sessions",
            "United States\t1000\t500",
            "United Kingdom\t300\t200",
        ]

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


class TestPivotResponseMetadata:
    def _invoke(self, response, fmt="table"):
        mock_client = _mock_data_client(pivot_response=response)

        with patch(
            "ga_cli.commands.reports.get_data_client",
            return_value=mock_client,
        ):
            return runner.invoke(
                app,
                [
                    "reports", "pivot",
                    "-p", "123",
                    "-m", "sessions",
                    "-d", "country,deviceCategory",
                    "--pivot-field", "deviceCategory",
                    "-o", fmt,
                ],
            )

    def test_table_renders_data_notes(self):
        response = {
            **SAMPLE_PIVOT_RESPONSE,
            "metadata": {"subjectToThresholding": True},
        }
        result = self._invoke(response)

        assert result.exit_code == 0
        assert "Data Notes" in result.output
        assert "data thresholds" in result.output

    def test_table_no_metadata_no_data_notes(self):
        result = self._invoke(SAMPLE_PIVOT_RESPONSE)

        assert result.exit_code == 0
        assert "Data Notes" not in result.output

    def test_json_passthrough_keeps_metadata(self):
        import json

        response = {
            **SAMPLE_PIVOT_RESPONSE,
            "metadata": {"subjectToThresholding": True},
        }
        result = self._invoke(response, fmt="json")

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["metadata"] == {"subjectToThresholding": True}
