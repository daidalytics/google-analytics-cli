"""Tests for reporting data annotations commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_ANNOTATIONS = [
    {
        "name": "properties/123/reportingDataAnnotations/1",
        "title": "Site Redesign Launch",
        "annotationDate": "2025-03-15",
        "description": "Launched the new site redesign",
        "color": "BLUE",
    },
    {
        "name": "properties/123/reportingDataAnnotations/2",
        "title": "Campaign Start",
        "annotationDate": "2025-04-01",
        "description": "Spring marketing campaign",
        "color": "GREEN",
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with reportingDataAnnotations methods."""
    mock_client = MagicMock()
    ann = mock_client.properties.return_value.reportingDataAnnotations.return_value

    ann.list.return_value.execute.return_value = {
        "reportingDataAnnotations": SAMPLE_ANNOTATIONS,
    }
    ann.get.return_value.execute.return_value = SAMPLE_ANNOTATIONS[0]
    ann.create.return_value.execute.return_value = SAMPLE_ANNOTATIONS[0]
    ann.patch.return_value.execute.return_value = SAMPLE_ANNOTATIONS[0]
    ann.delete.return_value.execute.return_value = {}

    return mock_client


class TestAnnotationsList:
    def test_list_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["annotations", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "Site Redesign" in result.output
        assert "Campaign Start" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.list.return_value.execute.return_value = {"reportingDataAnnotations": []}

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["annotations", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["annotations", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"title"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["annotations", "list", "-p", "123"]
            )

        assert result.exit_code == 1

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["annotations", "list"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["annotations", "list"])

        assert result.exit_code == 0
        assert "Site Redesign" in result.output


class TestAnnotationsGet:
    def test_get_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["annotations", "get", "-p", "123", "--annotation-id", "1"],
            )

        assert result.exit_code == 0
        assert "Site Redesign" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["annotations", "get", "-p", "123", "-a", "1", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"title"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["annotations", "get", "-p", "123", "-a", "999"],
            )

        assert result.exit_code == 1


class TestAnnotationsCreate:
    def test_create_basic(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "create",
                    "-p", "123",
                    "--title", "Site Redesign Launch",
                    "--annotation-date", "2025-03-15",
                ],
            )

        assert result.exit_code == 0
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        call_args = ann.create.call_args
        body = call_args[1]["body"]
        assert body["title"] == "Site Redesign Launch"
        assert body["annotationDate"] == "2025-03-15"

    def test_create_with_all_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "create",
                    "-p", "123",
                    "--title", "Campaign Start",
                    "--annotation-date", "2025-04-01",
                    "--description", "Spring campaign",
                    "--color", "GREEN",
                ],
            )

        assert result.exit_code == 0
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        body = ann.create.call_args[1]["body"]
        assert body["description"] == "Spring campaign"
        assert body["color"] == "GREEN"

    def test_create_requires_title(self):
        result = runner.invoke(
            app,
            [
                "annotations", "create",
                "-p", "123",
                "--annotation-date", "2025-03-15",
            ],
        )

        assert result.exit_code != 0

    def test_create_requires_date(self):
        result = runner.invoke(
            app,
            [
                "annotations", "create",
                "-p", "123",
                "--title", "Test",
            ],
        )

        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "create",
                    "-p", "123",
                    "--title", "Test",
                    "--annotation-date", "2025-03-15",
                ],
            )

        assert result.exit_code == 1


class TestAnnotationsUpdate:
    def test_update_title(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "update",
                    "-p", "123",
                    "-a", "1",
                    "--title", "New Title",
                ],
            )

        assert result.exit_code == 0
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        call_args = ann.patch.call_args
        assert call_args[1]["updateMask"] == "title"
        assert call_args[1]["body"]["title"] == "New Title"

    def test_update_description(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "update",
                    "-p", "123",
                    "-a", "1",
                    "--description", "Updated desc",
                ],
            )

        assert result.exit_code == 0
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        assert ann.patch.call_args[1]["updateMask"] == "description"

    def test_update_color(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "update",
                    "-p", "123",
                    "-a", "1",
                    "--color", "RED",
                ],
            )

        assert result.exit_code == 0
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        assert ann.patch.call_args[1]["updateMask"] == "color"

    def test_update_multiple_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "update",
                    "-p", "123",
                    "-a", "1",
                    "--title", "New Title",
                    "--description", "New desc",
                    "--color", "RED",
                ],
            )

        assert result.exit_code == 0
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        mask = ann.patch.call_args[1]["updateMask"]
        assert "title" in mask
        assert "description" in mask
        assert "color" in mask

    def test_update_no_fields(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["annotations", "update", "-p", "123", "-a", "1"],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "annotations", "update",
                    "-p", "123",
                    "-a", "1",
                    "--title", "Fail",
                ],
            )

        assert result.exit_code == 1


class TestAnnotationsDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["annotations", "delete", "-p", "123", "-a", "1", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.delete.assert_called_once()

    def test_delete_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.annotations.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.annotations.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["annotations", "delete", "-p", "123", "-a", "1"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.annotations.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.annotations.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["annotations", "delete", "-p", "123", "-a", "1"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.delete.assert_not_called()

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ann = mock_client.properties.return_value.reportingDataAnnotations.return_value
        ann.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.annotations.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["annotations", "delete", "-p", "123", "-a", "1", "--yes"],
            )

        assert result.exit_code == 1
