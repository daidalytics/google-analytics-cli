"""Tests for BigQuery link commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_LINKS = [
    {
        "name": "properties/123/bigQueryLinks/abc123",
        "project": "projects/1234",
        "datasetLocation": "US",
        "dailyExportEnabled": True,
        "streamingExportEnabled": False,
        "freshDailyExportEnabled": False,
        "includeAdvertisingId": False,
        "exportStreams": ["properties/123/dataStreams/1001"],
        "excludedEvents": [],
        "createTime": "2024-01-01T00:00:00Z",
    },
    {
        "name": "properties/123/bigQueryLinks/def456",
        "project": "projects/5678",
        "datasetLocation": "EU",
        "dailyExportEnabled": False,
        "streamingExportEnabled": True,
        "freshDailyExportEnabled": True,
        "includeAdvertisingId": True,
        "exportStreams": [],
        "excludedEvents": ["scroll", "click"],
        "createTime": "2024-06-15T12:00:00Z",
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with bigQueryLinks methods."""
    mock_client = MagicMock()
    bq = mock_client.properties.return_value.bigQueryLinks.return_value

    bq.list.return_value.execute.return_value = {
        "bigqueryLinks": SAMPLE_LINKS,
    }
    bq.get.return_value.execute.return_value = SAMPLE_LINKS[0]
    bq.create.return_value.execute.return_value = SAMPLE_LINKS[0]
    bq.patch.return_value.execute.return_value = SAMPLE_LINKS[0]
    bq.delete.return_value.execute.return_value = {}

    return mock_client


class TestBigQueryLinksList:
    def test_list_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["bigquery-links", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "US" in result.output
        assert "EU" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.list.return_value.execute.return_value = {"bigqueryLinks": []}

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["bigquery-links", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["bigquery-links", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"project"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["bigquery-links", "list", "-p", "123"]
            )

        assert result.exit_code == 1

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["bigquery-links", "list"])
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["bigquery-links", "list"])

        assert result.exit_code == 0
        assert "US" in result.output


class TestBigQueryLinksGet:
    def test_get_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["bigquery-links", "get", "-p", "123", "--link-id", "abc123"],
            )

        assert result.exit_code == 0
        assert "projects/1234" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["bigquery-links", "get", "-p", "123", "-l", "abc123", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"datasetLocation"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["bigquery-links", "get", "-p", "123", "-l", "missing"],
            )

        assert result.exit_code == 1


class TestBigQueryLinksCreate:
    def test_create_required_only(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "create",
                    "-p", "123",
                    "--project", "1234",
                    "--dataset-location", "US",
                ],
            )

        assert result.exit_code == 0
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        body = bq.create.call_args[1]["body"]
        assert body["project"] == "projects/1234"
        assert body["datasetLocation"] == "US"
        assert "dailyExportEnabled" not in body

    def test_create_with_all_flags(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "create",
                    "-p", "123",
                    "--project", "projects/1234",
                    "--dataset-location", "EU",
                    "--daily-export",
                    "--streaming-export",
                    "--no-fresh-daily-export",
                    "--include-advertising-id",
                    "--export-streams", "1001,1002",
                    "--excluded-events", "scroll,click",
                ],
            )

        assert result.exit_code == 0
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        body = bq.create.call_args[1]["body"]
        assert body["project"] == "projects/1234"
        assert body["datasetLocation"] == "EU"
        assert body["dailyExportEnabled"] is True
        assert body["streamingExportEnabled"] is True
        assert body["freshDailyExportEnabled"] is False
        assert body["includeAdvertisingId"] is True
        assert body["exportStreams"] == [
            "properties/123/dataStreams/1001",
            "properties/123/dataStreams/1002",
        ]
        assert body["excludedEvents"] == ["scroll", "click"]

    def test_create_normalizes_project(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "create",
                    "-p", "123",
                    "--project", "my-project-id",
                    "--dataset-location", "US",
                ],
            )

        assert result.exit_code == 0
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        body = bq.create.call_args[1]["body"]
        assert body["project"] == "projects/my-project-id"

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "create",
                    "-p", "123",
                    "--project", "1234",
                    "--dataset-location", "US",
                ],
            )

        assert result.exit_code == 1


class TestBigQueryLinksUpdate:
    def test_update_single_boolean(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "update",
                    "-p", "123",
                    "-l", "abc123",
                    "--daily-export",
                ],
            )

        assert result.exit_code == 0
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        call_args = bq.patch.call_args
        assert call_args[1]["updateMask"] == "dailyExportEnabled"
        assert call_args[1]["body"]["dailyExportEnabled"] is True

    def test_update_disable_boolean(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "update",
                    "-p", "123",
                    "-l", "abc123",
                    "--no-streaming-export",
                ],
            )

        assert result.exit_code == 0
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        assert bq.patch.call_args[1]["body"]["streamingExportEnabled"] is False

    def test_update_multiple_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "update",
                    "-p", "123",
                    "-l", "abc123",
                    "--daily-export",
                    "--no-streaming-export",
                    "--excluded-events", "scroll",
                ],
            )

        assert result.exit_code == 0
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        mask = bq.patch.call_args[1]["updateMask"]
        assert "dailyExportEnabled" in mask
        assert "streamingExportEnabled" in mask
        assert "excludedEvents" in mask

    def test_update_export_streams(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "update",
                    "-p", "123",
                    "-l", "abc123",
                    "--export-streams", "1001,1002",
                ],
            )

        assert result.exit_code == 0
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        body = bq.patch.call_args[1]["body"]
        assert body["exportStreams"] == [
            "properties/123/dataStreams/1001",
            "properties/123/dataStreams/1002",
        ]

    def test_update_no_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["bigquery-links", "update", "-p", "123", "-l", "abc123"],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "bigquery-links", "update",
                    "-p", "123",
                    "-l", "abc123",
                    "--daily-export",
                ],
            )

        assert result.exit_code == 1


class TestBigQueryLinksDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["bigquery-links", "delete", "-p", "123", "-l", "abc123", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.delete.assert_called_once()

    def test_delete_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.bigquery_links.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.bigquery_links.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["bigquery-links", "delete", "-p", "123", "-l", "abc123"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.bigquery_links.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.bigquery_links.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["bigquery-links", "delete", "-p", "123", "-l", "abc123"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.delete.assert_not_called()

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        bq = mock_client.properties.return_value.bigQueryLinks.return_value
        bq.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.bigquery_links.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["bigquery-links", "delete", "-p", "123", "-l", "abc123", "--yes"],
            )

        assert result.exit_code == 1
