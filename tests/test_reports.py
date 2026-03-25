"""Tests for reports commands (run, realtime, build)."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_REPORT_RESPONSE = {
    "dimensionHeaders": [{"name": "date"}],
    "metricHeaders": [{"name": "sessions"}, {"name": "users"}],
    "rows": [
        {
            "dimensionValues": [{"value": "20240101"}],
            "metricValues": [{"value": "150"}, {"value": "100"}],
        },
        {
            "dimensionValues": [{"value": "20240102"}],
            "metricValues": [{"value": "200"}, {"value": "120"}],
        },
    ],
    "rowCount": 2,
}

SAMPLE_REALTIME_RESPONSE = {
    "metricHeaders": [{"name": "activeUsers"}],
    "rows": [
        {
            "dimensionValues": [],
            "metricValues": [{"value": "42"}],
        },
    ],
    "rowCount": 1,
}

SAMPLE_METADATA = {
    "metrics": [
        {"apiName": "sessions"},
        {"apiName": "users"},
        {"apiName": "screenPageViews"},
    ],
    "dimensions": [
        {"apiName": "date"},
        {"apiName": "country"},
        {"apiName": "city"},
    ],
}


def _mock_data_client(report_response=None, realtime_response=None, metadata=None):
    """Create a mock Data API client."""
    mock_client = MagicMock()

    props = mock_client.properties.return_value

    props.runReport.return_value.execute.return_value = (
        report_response or SAMPLE_REPORT_RESPONSE
    )
    props.runRealtimeReport.return_value.execute.return_value = (
        realtime_response or SAMPLE_REALTIME_RESPONSE
    )
    props.getMetadata.return_value.execute.return_value = (
        metadata or SAMPLE_METADATA
    )

    return mock_client


class TestReportsRun:
    def test_run_default_metrics(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "--property-id", "111"]
            )

        assert result.exit_code == 0
        assert "150" in result.output
        assert "200" in result.output

    def test_run_json_output(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"sessions"' in result.output
        assert '"150"' in result.output

    def test_run_with_dimensions_and_metrics(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports",
                    "run",
                    "-p",
                    "111",
                    "-m",
                    "sessions,users",
                    "-d",
                    "date,country",
                ],
            )

        assert result.exit_code == 0
        # Verify the body was constructed correctly
        call_args = mock_client.properties.return_value.runReport.call_args
        body = call_args[1]["body"]
        assert len(body["metrics"]) == 2
        assert len(body["dimensions"]) == 2

    def test_run_with_date_range(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports",
                    "run",
                    "-p",
                    "111",
                    "--start-date",
                    "30daysAgo",
                    "--end-date",
                    "yesterday",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.runReport.call_args
        body = call_args[1]["body"]
        assert body["dateRanges"][0]["startDate"] == "30daysAgo"
        assert body["dateRanges"][0]["endDate"] == "yesterday"

    def test_run_with_limit(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            runner.invoke(
                app, ["reports", "run", "-p", "111", "--limit", "50"]
            )

        call_args = mock_client.properties.return_value.runReport.call_args
        body = call_args[1]["body"]
        assert body["limit"] == 50

    def test_run_uses_config_default(self):
        save_config(UserConfig(default_property_id="111"))
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(app, ["reports", "run"])

        assert result.exit_code == 0

    def test_run_missing_property_id(self):
        result = runner.invoke(app, ["reports", "run"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_run_empty_results(self):
        empty_response = {
            "dimensionHeaders": [],
            "metricHeaders": [{"name": "sessions"}],
            "rows": [],
            "rowCount": 0,
        }
        mock_client = _mock_data_client(report_response=empty_response)

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_run_api_error(self):
        mock_client = MagicMock()
        mock_client.properties.return_value.runReport.return_value.execute.side_effect = (
            Exception("Quota exceeded")
        )

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111"]
            )

        assert result.exit_code == 1
        assert "Quota exceeded" in result.output

    def test_run_shows_row_count_in_table_mode(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "2 total rows" in result.output


class TestReportsRealtime:
    def test_realtime_single_shot(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "realtime", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "42" in result.output

    def test_realtime_json_output(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "realtime", "-p", "111", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"42"' in result.output

    def test_realtime_with_dimensions(self):
        response = {
            "dimensionHeaders": [{"name": "country"}],
            "metricHeaders": [{"name": "activeUsers"}],
            "rows": [
                {
                    "dimensionValues": [{"value": "US"}],
                    "metricValues": [{"value": "25"}],
                },
            ],
            "rowCount": 1,
        }
        mock_client = _mock_data_client(realtime_response=response)

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                ["reports", "realtime", "-p", "111", "-d", "country"],
            )

        assert result.exit_code == 0
        assert "US" in result.output
        assert "25" in result.output

    def test_realtime_missing_property_id(self):
        result = runner.invoke(app, ["reports", "realtime"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()


class TestReportsBuild:
    def test_build_interactive(self):
        mock_client = _mock_data_client()

        with (
            patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.reports.questionary") as mock_q,
        ):
            mock_q.checkbox.return_value.ask.side_effect = [
                ["sessions", "users"],  # metrics
                ["date"],  # dimensions
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"

            result = runner.invoke(
                app, ["reports", "build", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "150" in result.output

    def test_build_no_metrics_selected(self):
        mock_client = _mock_data_client()

        with (
            patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.reports.questionary") as mock_q,
        ):
            mock_q.checkbox.return_value.ask.return_value = []

            result = runner.invoke(
                app, ["reports", "build", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "No metrics selected" in result.output

    def test_build_no_dimensions(self):
        mock_client = _mock_data_client()

        with (
            patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.reports.questionary") as mock_q,
        ):
            mock_q.checkbox.return_value.ask.side_effect = [
                ["sessions"],  # metrics
                [],  # no dimensions
            ]
            mock_q.select.return_value.ask.return_value = "30daysAgo"

            result = runner.invoke(
                app, ["reports", "build", "-p", "111"]
            )

        assert result.exit_code == 0

    def test_build_fetches_metadata(self):
        mock_client = _mock_data_client()

        with (
            patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.reports.questionary") as mock_q,
        ):
            mock_q.checkbox.return_value.ask.side_effect = [
                ["sessions"],
                [],
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"

            runner.invoke(app, ["reports", "build", "-p", "111"])

        # Verify getMetadata was called
        mock_client.properties.return_value.getMetadata.assert_called_once_with(
            name="properties/111/metadata"
        )

    def test_build_falls_back_on_metadata_error(self):
        mock_client = _mock_data_client()
        mock_client.properties.return_value.getMetadata.return_value.execute.side_effect = (
            Exception("Permission denied")
        )

        with (
            patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.reports.questionary") as mock_q,
        ):
            mock_q.checkbox.return_value.ask.side_effect = [
                ["sessions"],
                [],
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"

            result = runner.invoke(
                app, ["reports", "build", "-p", "111"]
            )

        # Should still succeed using fallback metrics
        assert result.exit_code == 0

    def test_build_missing_property_id(self):
        result = runner.invoke(app, ["reports", "build"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()


class TestCheckCompatibility:
    SAMPLE_COMPAT_RESPONSE = {
        "dimensionCompatibilities": [
            {
                "dimensionMetadata": {"apiName": "date", "uiName": "Date"},
                "compatibility": "COMPATIBLE",
            },
            {
                "dimensionMetadata": {"apiName": "city", "uiName": "City"},
                "compatibility": "INCOMPATIBLE",
            },
        ],
        "metricCompatibilities": [
            {
                "metricMetadata": {"apiName": "sessions", "uiName": "Sessions"},
                "compatibility": "COMPATIBLE",
            },
        ],
    }

    def _mock_compat_client(self, response=None):
        mock_client = MagicMock()
        mock_client.properties.return_value.checkCompatibility.return_value.execute.return_value = (
            response or self.SAMPLE_COMPAT_RESPONSE
        )
        return mock_client

    def test_all_compatible_table(self):
        all_compat = {
            "dimensionCompatibilities": [
                {
                    "dimensionMetadata": {"apiName": "date", "uiName": "Date"},
                    "compatibility": "COMPATIBLE",
                },
            ],
            "metricCompatibilities": [
                {
                    "metricMetadata": {"apiName": "sessions", "uiName": "Sessions"},
                    "compatibility": "COMPATIBLE",
                },
            ],
        }
        mock_client = self._mock_compat_client(response=all_compat)

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "check-compatibility",
                    "-p", "111",
                    "-m", "sessions",
                    "-d", "date",
                ],
            )

        assert result.exit_code == 0
        assert "COMPATIBLE" in result.output

    def test_some_incompatible_table(self):
        mock_client = self._mock_compat_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "check-compatibility",
                    "-p", "111",
                    "-m", "sessions",
                    "-d", "date,city",
                ],
            )

        assert result.exit_code == 0
        assert "INCOMPATIBLE" in result.output
        assert "COMPATIBLE" in result.output

    def test_json_output(self):
        mock_client = self._mock_compat_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "check-compatibility",
                    "-p", "111",
                    "-m", "sessions",
                    "-o", "json",
                ],
            )

        assert result.exit_code == 0
        assert "dimensionCompatibilities" in result.output

    def test_no_metrics_or_dimensions(self):
        result = runner.invoke(
            app,
            ["reports", "check-compatibility", "-p", "111"],
        )

        assert result.exit_code != 0

    def test_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = self._mock_compat_client()
        mock_client.properties.return_value.checkCompatibility.return_value.execute.side_effect = (
            HttpError(
                resp=MagicMock(status=400),
                content=b'{"error": {"message": "Bad request"}}',
            )
        )

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "check-compatibility",
                    "-p", "111",
                    "-m", "sessions",
                ],
            )

        assert result.exit_code == 1


class TestTransformReportRows:
    def test_transform_with_dimensions_and_metrics(self):
        from ga_cli.commands.reports import _transform_report_rows

        rows, columns, headers = _transform_report_rows(SAMPLE_REPORT_RESPONSE)

        assert len(rows) == 2
        assert rows[0] == {"date": "20240101", "sessions": "150", "users": "100"}
        assert rows[1] == {"date": "20240102", "sessions": "200", "users": "120"}
        assert columns == ["date", "sessions", "users"]

    def test_transform_empty_response(self):
        from ga_cli.commands.reports import _transform_report_rows

        empty = {
            "dimensionHeaders": [],
            "metricHeaders": [{"name": "sessions"}],
            "rows": [],
        }
        rows, columns, headers = _transform_report_rows(empty)

        assert rows == []
        assert columns == ["sessions"]

    def test_transform_metrics_only(self):
        from ga_cli.commands.reports import _transform_report_rows

        response = {
            "metricHeaders": [{"name": "activeUsers"}],
            "rows": [
                {
                    "dimensionValues": [],
                    "metricValues": [{"value": "42"}],
                },
            ],
        }
        rows, columns, headers = _transform_report_rows(response)

        assert len(rows) == 1
        assert rows[0] == {"activeUsers": "42"}


SAMPLE_METADATA_FULL = {
    "dimensions": [
        {
            "apiName": "date",
            "uiName": "Date",
            "category": "Time",
            "customDefinition": False,
        },
        {
            "apiName": "pagePath",
            "uiName": "Page path",
            "category": "Page / screen",
            "customDefinition": False,
        },
    ],
    "metrics": [
        {
            "apiName": "sessions",
            "uiName": "Sessions",
            "category": "Session",
            "customDefinition": False,
        },
        {
            "apiName": "pageViews",
            "uiName": "Page views",
            "category": "Page / screen",
            "customDefinition": False,
        },
    ],
}


class TestMetadata:
    def _mock_metadata_client(self, metadata=None):
        mock_client = MagicMock()
        mock_client.properties.return_value.getMetadata.return_value.execute.return_value = (
            metadata or SAMPLE_METADATA_FULL
        )
        return mock_client

    def test_metadata_all(self):
        mock_client = self._mock_metadata_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "metadata", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "date" in result.output
        assert "sessions" in result.output
        assert "pagePath" in result.output
        assert "pageViews" in result.output

    def test_metadata_filter_metrics(self):
        mock_client = self._mock_metadata_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "metadata", "-p", "111", "--type", "metrics"]
            )

        assert result.exit_code == 0
        assert "sessions" in result.output
        assert "date" not in result.output or "dimension" not in result.output

    def test_metadata_filter_dimensions(self):
        mock_client = self._mock_metadata_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "metadata", "-p", "111", "--type", "dimensions"]
            )

        assert result.exit_code == 0
        assert "date" in result.output
        # Should not contain metrics rows
        assert "sessions" not in result.output

    def test_metadata_search(self):
        mock_client = self._mock_metadata_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "metadata", "-p", "111", "--search", "page"]
            )

        assert result.exit_code == 0
        assert "pagePath" in result.output
        assert "pageViews" in result.output
        # "date" and "sessions" should be filtered out
        assert "date" not in result.output

    def test_metadata_json(self):
        mock_client = self._mock_metadata_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "metadata", "-p", "111", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"apiName"' in result.output

    def test_metadata_api_error(self):
        mock_client = MagicMock()
        mock_client.properties.return_value.getMetadata.return_value.execute.side_effect = (
            Exception("Permission denied")
        )

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "metadata", "-p", "111"]
            )

        assert result.exit_code != 0

    def test_metadata_empty_response(self):
        mock_client = self._mock_metadata_client(metadata={"dimensions": [], "metrics": []})

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "metadata", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "No metadata" in result.output
