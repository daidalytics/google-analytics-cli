"""Tests for reports commands (run, realtime, build)."""

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


SAMPLE_REPORT_RESPONSE = {
    "dimensionHeaders": [{"name": "date"}],
    "metricHeaders": [{"name": "sessions"}, {"name": "totalUsers"}],
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
        {"apiName": "totalUsers"},
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
        assert "property-id" in _strip_ansi(result.output).lower()

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

        assert result.exit_code == 3
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
        assert "property-id" in _strip_ansi(result.output).lower()


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
                ["sessions", "totalUsers"],  # metrics
                ["date"],  # dimensions
                [],  # additional options
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"
            mock_q.confirm.return_value.ask.return_value = False  # skip filters/sorts

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
                [],  # additional options
            ]
            mock_q.select.return_value.ask.return_value = "30daysAgo"
            mock_q.confirm.return_value.ask.return_value = False

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
                [],  # additional options
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"
            mock_q.confirm.return_value.ask.return_value = False

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
                [],  # additional options
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"
            mock_q.confirm.return_value.ask.return_value = False

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

        assert result.exit_code == 3


class TestTransformReportRows:
    def test_transform_with_dimensions_and_metrics(self):
        from ga_cli.commands.reports import _transform_report_rows

        rows, columns, headers = _transform_report_rows(SAMPLE_REPORT_RESPONSE)

        assert len(rows) == 2
        assert rows[0] == {"date": "20240101", "sessions": "150", "totalUsers": "100"}
        assert rows[1] == {"date": "20240102", "sessions": "200", "totalUsers": "120"}
        assert columns == ["date", "sessions", "totalUsers"]

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


# ---------------------------------------------------------------------------
# New feature tests: filters, order-by, date ranges, misc options
# ---------------------------------------------------------------------------

class TestReportsRunFilters:
    def test_run_with_dim_filter(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "--dim-filter", "country==US"]
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.runReport.call_args
        body = call_args[1]["body"]
        assert "dimensionFilter" in body
        assert body["dimensionFilter"]["filter"]["fieldName"] == "country"

    def test_run_with_multiple_dim_filters(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "run", "-p", "111",
                    "--dim-filter", "country==US",
                    "--dim-filter", "pagePath contains /blog",
                ],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert "andGroup" in body["dimensionFilter"]
        assert len(body["dimensionFilter"]["andGroup"]["expressions"]) == 2

    def test_run_with_metric_filter(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "--metric-filter", "sessions>100"]
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert "metricFilter" in body
        assert body["metricFilter"]["filter"]["numericFilter"]["operation"] == "GREATER_THAN"

    def test_run_with_filter_json_inline(self):
        import json as json_mod

        filter_expr = json_mod.dumps({
            "filter": {
                "fieldName": "country",
                "stringFilter": {"matchType": "EXACT", "value": "US"},
            }
        })
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "--filter-json", filter_expr]
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["dimensionFilter"]["filter"]["fieldName"] == "country"

    def test_run_cannot_combine_dsl_and_json(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "run", "-p", "111",
                    "--dim-filter", "country==US",
                    "--filter-json", '{"filter":{}}',
                ],
            )

        assert result.exit_code != 0

    def test_run_invalid_filter_syntax(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "--dim-filter", "badfilter"]
            )

        assert result.exit_code != 0


class TestReportsRunOrderBy:
    def test_run_with_order_by_metric(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "--order-by", "sessions:desc"]
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["orderBys"] == [{"metric": {"metricName": "sessions"}, "desc": True}]

    def test_run_with_order_by_dimension(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "run", "-p", "111",
                    "-d", "country",
                    "--order-by", "country:asc:alpha",
                ],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["orderBys"][0]["dimension"]["dimensionName"] == "country"
        assert body["orderBys"][0]["dimension"]["orderType"] == "ALPHANUMERIC"

    def test_run_with_multiple_order_bys(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "run", "-p", "111",
                    "--order-by", "sessions:desc",
                    "--order-by", "users:asc",
                ],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert len(body["orderBys"]) == 2


class TestReportsRunDateRanges:
    def test_run_with_single_date_range_flag(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                ["reports", "run", "-p", "111", "--date-range", "30daysAgo,today"],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["dateRanges"] == [{"startDate": "30daysAgo", "endDate": "today"}]

    def test_run_with_multiple_date_ranges(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "run", "-p", "111",
                    "--date-range", "7daysAgo,today",
                    "--date-range", "30daysAgo,8daysAgo",
                ],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert len(body["dateRanges"]) == 2

    def test_date_range_overrides_start_end(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "run", "-p", "111",
                    "--start-date", "90daysAgo",
                    "--end-date", "yesterday",
                    "--date-range", "7daysAgo,today",
                ],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        # --date-range should take precedence
        assert body["dateRanges"] == [{"startDate": "7daysAgo", "endDate": "today"}]


class TestReportsRunMiscOptions:
    def test_run_with_offset(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            runner.invoke(
                app, ["reports", "run", "-p", "111", "--offset", "50"]
            )

        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["offset"] == 50

    def test_run_with_currency_code(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            runner.invoke(
                app, ["reports", "run", "-p", "111", "--currency-code", "EUR"]
            )

        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["currencyCode"] == "EUR"

    def test_run_with_keep_empty_rows(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            runner.invoke(
                app, ["reports", "run", "-p", "111", "--keep-empty-rows"]
            )

        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["keepEmptyRows"] is True

    def test_run_with_return_property_quota(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            runner.invoke(
                app, ["reports", "run", "-p", "111", "--return-property-quota"]
            )

        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["returnPropertyQuota"] is True

    def test_run_with_metric_aggregations(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                [
                    "reports", "run", "-p", "111",
                    "--metric-aggregation", "TOTAL",
                    "--metric-aggregation", "MAXIMUM",
                ],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runReport.call_args[1]["body"]
        assert body["metricAggregations"] == ["TOTAL", "MAXIMUM"]


class TestRealtimeFilters:
    def test_realtime_with_dim_filter(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                ["reports", "realtime", "-p", "111", "--dim-filter", "country==US"],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runRealtimeReport.call_args[1]["body"]
        assert "dimensionFilter" in body

    def test_realtime_with_order_by(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                ["reports", "realtime", "-p", "111", "--order-by", "activeUsers:desc"],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runRealtimeReport.call_args[1]["body"]
        assert "orderBys" in body

    def test_realtime_with_minute_range(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                ["reports", "realtime", "-p", "111", "--minute-range", "0,4"],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runRealtimeReport.call_args[1]["body"]
        assert body["minuteRanges"] == [{"startMinutesAgo": 0, "endMinutesAgo": 4}]

    def test_realtime_with_metric_aggregation(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app,
                ["reports", "realtime", "-p", "111", "--metric-aggregation", "TOTAL"],
            )

        assert result.exit_code == 0
        body = mock_client.properties.return_value.runRealtimeReport.call_args[1]["body"]
        assert body["metricAggregations"] == ["TOTAL"]


class TestHumanizeTruncationType:
    def test_strips_prefix_and_title_cases(self):
        from ga_cli.commands.reports import _humanize_truncation_type

        assert _humanize_truncation_type("DATA_TRUNCATION_TYPE_GOOGLE_ADS") == "Google Ads"

    def test_preserves_words_containing_digits(self):
        from ga_cli.commands.reports import _humanize_truncation_type

        assert _humanize_truncation_type("DATA_TRUNCATION_TYPE_DV360") == "DV360"


def _run_with_metadata(metadata: dict, fmt: str = "table", base: dict | None = None):
    """Invoke `reports run` with a mocked response carrying the given metadata."""
    response = {**(base or SAMPLE_REPORT_RESPONSE), "metadata": metadata}
    mock_client = _mock_data_client(report_response=response)

    with patch("ga_cli.commands.reports.get_data_client", return_value=mock_client):
        return runner.invoke(app, ["reports", "run", "-p", "111", "-o", fmt])


class TestResponseMetadataDisplay:
    def test_truncation_reasons_render_one_line_each(self):
        result = _run_with_metadata({
            "dataTruncationReasons": [
                {
                    "dataTruncationType": "DATA_TRUNCATION_TYPE_GOOGLE_ADS",
                    "dataTruncationMessage": "Ads retention limit.",
                    "dataTruncationDate": "2023-09-01",
                },
                {
                    "dataTruncationType": "DATA_TRUNCATION_TYPE_DATE_RANGE",
                    "dataTruncationMessage": "Range not fully served.",
                },
            ]
        })

        output = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "Data Notes" in output
        assert "Truncated (Google Ads): Ads retention limit." in output
        assert "Truncated (Date Range): Range not fully served." in output

    def test_truncation_date_appended_only_when_present(self):
        result = _run_with_metadata({
            "dataTruncationReasons": [
                {
                    "dataTruncationType": "DATA_TRUNCATION_TYPE_GOOGLE_ADS",
                    "dataTruncationMessage": "Ads retention limit.",
                    "dataTruncationDate": "2023-09-01",
                },
                {
                    "dataTruncationType": "DATA_TRUNCATION_TYPE_DATE_RANGE",
                    "dataTruncationMessage": "Range not fully served.",
                },
            ]
        })

        output = _strip_ansi(result.output)
        assert "(before 2023-09-01)" in output
        assert output.count("(before") == 1

    def test_truncation_date_ranges_render_without_message(self):
        # Observed live 2026-09-18: DATE_RANGE truncations arrive with only
        # dataTruncationDateRanges — no message, no dataTruncationDate.
        result = _run_with_metadata({
            "dataTruncationReasons": [
                {
                    "dataTruncationType": "DATA_TRUNCATION_TYPE_DATE_RANGE",
                    "dataTruncationDateRanges": [
                        {"startDate": "2015-08-14", "endDate": "2016-12-31"}
                    ],
                }
            ]
        })

        output = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "Truncated (Date Range): affected: 2015-08-14–2016-12-31" in output

    def test_truncation_with_no_detail_renders_type_without_colon(self):
        result = _run_with_metadata({
            "dataTruncationReasons": [
                {"dataTruncationType": "DATA_TRUNCATION_TYPE_PROPERTY"}
            ]
        })

        output = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "Truncated (Property)" in output
        assert "Truncated (Property):" not in output

    def test_thresholding_true_renders_note(self):
        result = _run_with_metadata({"subjectToThresholding": True})

        output = _strip_ansi(result.output)
        assert "Data Notes" in output
        assert "data thresholds" in output

    def test_thresholding_false_renders_nothing(self):
        result = _run_with_metadata({"subjectToThresholding": False})

        assert result.exit_code == 0
        assert "Data Notes" not in _strip_ansi(result.output)

    def test_sampling_percentage_one_decimal(self):
        result = _run_with_metadata({
            "samplingMetadatas": [
                {"samplingSpaceSize": "1204500", "samplesReadCount": "42103"}
            ]
        })

        output = _strip_ansi(result.output)
        assert "Sampled: 42,103 of 1,204,500 events" in output
        assert "(3.5%)" in output

    def test_sampling_zero_space_size_does_not_crash(self):
        result = _run_with_metadata({
            "samplingMetadatas": [
                {"samplingSpaceSize": "0", "samplesReadCount": "0"}
            ]
        })

        assert result.exit_code == 0
        assert "(?)" in _strip_ansi(result.output)

    def test_metric_restrictions_render(self):
        result = _run_with_metadata({
            "schemaRestrictionResponse": {
                "activeMetricRestrictions": [
                    {
                        "metricName": "purchaseRevenue",
                        "restrictedMetricTypes": ["REVENUE_DATA"],
                    }
                ]
            }
        })

        output = _strip_ansi(result.output)
        assert "purchaseRevenue" in output
        assert "REVENUE_DATA" in output

    def test_empty_reason_rendered(self):
        empty_report = {
            "dimensionHeaders": [{"name": "date"}],
            "metricHeaders": [{"name": "sessions"}],
            "rowCount": 0,
        }
        result = _run_with_metadata(
            {"emptyReason": "DATA_RETENTION_EXPIRED"}, base=empty_report
        )

        output = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "DATA_RETENTION_EXPIRED" in output

    def test_no_metadata_key_renders_no_data_notes(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "-o", "table"]
            )

        assert result.exit_code == 0
        assert "Data Notes" not in _strip_ansi(result.output)

    def test_empty_metadata_object_renders_no_data_notes(self):
        result = _run_with_metadata({})

        assert result.exit_code == 0
        assert "Data Notes" not in _strip_ansi(result.output)

    def test_currency_and_timezone_only_render_no_data_notes(self):
        # The live API populates these two fields on every response
        # (verified 2026-09-18); they must not trigger the notes section.
        result = _run_with_metadata(
            {"currencyCode": "USD", "timeZone": "Europe/Copenhagen"}
        )

        assert result.exit_code == 0
        assert "Data Notes" not in _strip_ansi(result.output)

    def test_api_text_with_rich_markup_renders_literally(self):
        result = _run_with_metadata({
            "dataTruncationReasons": [
                {
                    "dataTruncationType": "DATA_TRUNCATION_TYPE_DATE_RANGE",
                    "dataTruncationMessage": "See [bold]docs[/bold] now.",
                }
            ]
        })

        assert "[bold]docs[/bold]" in _strip_ansi(result.output)


class TestBuildMetadataDisplay:
    def _invoke_build(self, report_response, fmt="table"):
        mock_client = _mock_data_client(report_response=report_response)

        with (
            patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.reports.questionary") as mock_q,
        ):
            mock_q.checkbox.return_value.ask.side_effect = [
                ["sessions", "totalUsers"],  # metrics
                ["date"],  # dimensions
                [],  # additional options
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"
            mock_q.confirm.return_value.ask.return_value = False  # skip filters/sorts

            return runner.invoke(app, ["reports", "build", "-p", "111", "-o", fmt])

    def test_build_table_renders_data_notes(self):
        response = {
            **SAMPLE_REPORT_RESPONSE,
            "metadata": {"subjectToThresholding": True},
        }
        result = self._invoke_build(response)

        output = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "Data Notes" in output
        assert "data thresholds" in output

    def test_build_table_no_metadata_no_data_notes(self):
        result = self._invoke_build(SAMPLE_REPORT_RESPONSE)

        assert result.exit_code == 0
        assert "Data Notes" not in _strip_ansi(result.output)


class TestReportsJsonEnvelope:
    def test_run_json_is_rows_metadata_envelope(self):
        mock_client = _mock_data_client()

        with patch(
            "ga_cli.commands.reports.get_data_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["reports", "run", "-p", "111", "-o", "json"]
            )

        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert sorted(parsed) == ["metadata", "rows"]
        assert parsed["metadata"] == {}
        assert parsed["rows"] == [
            {"date": "20240101", "sessions": "150", "totalUsers": "100"},
            {"date": "20240102", "sessions": "200", "totalUsers": "120"},
        ]

    def test_run_json_metadata_passthrough_verbatim(self):
        metadata = {
            "subjectToThresholding": True,
            "dataTruncationReasons": [
                {
                    "dataTruncationType": "DATA_TRUNCATION_TYPE_DATE_RANGE",
                    "dataTruncationMessage": "Range not fully served.",
                }
            ],
        }
        result = _run_with_metadata(metadata, fmt="json")

        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["metadata"] == metadata

    def test_build_json_is_rows_metadata_envelope(self):
        mock_client = _mock_data_client()

        with (
            patch(
                "ga_cli.commands.reports.get_data_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.reports.questionary") as mock_q,
        ):
            mock_q.checkbox.return_value.ask.side_effect = [
                ["sessions", "totalUsers"],  # metrics
                ["date"],  # dimensions
                [],  # additional options
            ]
            mock_q.select.return_value.ask.return_value = "7daysAgo"
            mock_q.confirm.return_value.ask.return_value = False  # skip filters/sorts

            result = runner.invoke(
                app, ["reports", "build", "-p", "111", "-o", "json"]
            )

        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert sorted(parsed) == ["metadata", "rows"]
        assert parsed["rows"][0]["sessions"] == "150"


class TestResponseMetadataCompact:
    def test_notes_go_to_stderr_stdout_stays_row_only(self):
        result = _run_with_metadata(
            {
                "dataTruncationReasons": [
                    {
                        "dataTruncationType": "DATA_TRUNCATION_TYPE_GOOGLE_ADS",
                        "dataTruncationMessage": "Ads retention limit.",
                    }
                ]
            },
            fmt="compact",
        )

        assert result.exit_code == 0
        # click 8.3: result.output merges stdout+stderr; result.stdout is stdout only.
        assert "Truncated" not in _strip_ansi(result.stdout)
        assert "Truncated (Google Ads)" in _strip_ansi(result.output)
