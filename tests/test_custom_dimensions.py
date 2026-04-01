"""Tests for custom dimensions commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_DIMENSIONS = [
    {
        "name": "properties/123/customDimensions/1",
        "parameterName": "page_type",
        "displayName": "Page Type",
        "scope": "EVENT",
        "description": "Type of page",
        "disallowAdsPersonalization": False,
    },
    {
        "name": "properties/123/customDimensions/2",
        "parameterName": "user_tier",
        "displayName": "User Tier",
        "scope": "USER",
        "description": "Subscription tier",
        "disallowAdsPersonalization": True,
    },
    {
        "name": "properties/123/customDimensions/3",
        "parameterName": "item_brand",
        "displayName": "Item Brand",
        "scope": "ITEM",
        "description": "",
        "disallowAdsPersonalization": False,
    },
]


def _mock_admin_client():
    """Create a mock Admin API client with customDimensions methods."""
    mock_client = MagicMock()
    cd = mock_client.properties.return_value.customDimensions.return_value

    cd.list.return_value.execute.return_value = {
        "customDimensions": SAMPLE_DIMENSIONS,
    }
    cd.get.return_value.execute.return_value = SAMPLE_DIMENSIONS[0]
    cd.create.return_value.execute.return_value = SAMPLE_DIMENSIONS[0]
    cd.patch.return_value.execute.return_value = SAMPLE_DIMENSIONS[0]
    cd.archive.return_value.execute.return_value = {}

    return mock_client


class TestCustomDimensionsList:
    def test_list_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-dimensions", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "Page Type" in result.output
        assert "User Tier" in result.output
        assert "Item Brand" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client()
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.list.return_value.execute.return_value = {"customDimensions": []}

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-dimensions", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-dimensions", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"parameterName"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["custom-dimensions", "list", "-p", "123"]
            )

        assert result.exit_code == 2

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["custom-dimensions", "list"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["custom-dimensions", "list"])

        assert result.exit_code == 0
        assert "Page Type" in result.output


class TestCustomDimensionsGet:
    def test_get_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-dimensions", "get", "-p", "123", "--dimension-id", "1"],
            )

        assert result.exit_code == 0
        assert "Page Type" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-dimensions", "get", "-p", "123", "-d", "1", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"parameterName"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-dimensions", "get", "-p", "123", "-d", "999"],
            )

        assert result.exit_code == 3


class TestCustomDimensionsCreate:
    def test_create_event_scope(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "create",
                    "-p", "123",
                    "--parameter-name", "page_type",
                    "--display-name", "Page Type",
                    "--scope", "EVENT",
                ],
            )

        assert result.exit_code == 0
        cd = mock_client.properties.return_value.customDimensions.return_value
        call_args = cd.create.call_args
        body = call_args[1]["body"]
        assert body["scope"] == "EVENT"
        assert body["parameterName"] == "page_type"

    def test_create_user_scope(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "create",
                    "-p", "123",
                    "--parameter-name", "user_tier",
                    "--display-name", "User Tier",
                    "--scope", "USER",
                ],
            )

        assert result.exit_code == 0
        cd = mock_client.properties.return_value.customDimensions.return_value
        body = cd.create.call_args[1]["body"]
        assert body["scope"] == "USER"

    def test_create_item_scope(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "create",
                    "-p", "123",
                    "--parameter-name", "item_brand",
                    "--display-name", "Item Brand",
                    "--scope", "ITEM",
                ],
            )

        assert result.exit_code == 0
        cd = mock_client.properties.return_value.customDimensions.return_value
        body = cd.create.call_args[1]["body"]
        assert body["scope"] == "ITEM"

    def test_create_invalid_scope(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "create",
                    "-p", "123",
                    "--parameter-name", "test",
                    "--display-name", "Test",
                    "--scope", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_create_requires_parameter_name(self):
        result = runner.invoke(
            app,
            [
                "custom-dimensions", "create",
                "-p", "123",
                "--display-name", "Test",
                "--scope", "EVENT",
            ],
        )

        assert result.exit_code != 0

    def test_create_requires_display_name(self):
        result = runner.invoke(
            app,
            [
                "custom-dimensions", "create",
                "-p", "123",
                "--parameter-name", "test",
                "--scope", "EVENT",
            ],
        )

        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "create",
                    "-p", "123",
                    "--parameter-name", "test",
                    "--display-name", "Test",
                    "--scope", "EVENT",
                ],
            )

        assert result.exit_code == 3


class TestCustomDimensionsUpdate:
    def test_update_display_name(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "update",
                    "-p", "123",
                    "-d", "1",
                    "--display-name", "New Name",
                ],
            )

        assert result.exit_code == 0
        cd = mock_client.properties.return_value.customDimensions.return_value
        call_args = cd.patch.call_args
        assert call_args[1]["updateMask"] == "displayName"
        assert call_args[1]["body"]["displayName"] == "New Name"

    def test_update_description(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "update",
                    "-p", "123",
                    "-d", "1",
                    "--description", "New desc",
                ],
            )

        assert result.exit_code == 0
        cd = mock_client.properties.return_value.customDimensions.return_value
        call_args = cd.patch.call_args
        assert call_args[1]["updateMask"] == "description"

    def test_update_both_fields(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "update",
                    "-p", "123",
                    "-d", "1",
                    "--display-name", "New Name",
                    "--description", "New desc",
                ],
            )

        assert result.exit_code == 0
        cd = mock_client.properties.return_value.customDimensions.return_value
        mask = cd.patch.call_args[1]["updateMask"]
        assert "displayName" in mask
        assert "description" in mask

    def test_update_no_fields(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-dimensions", "update", "-p", "123", "-d", "1"],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "custom-dimensions", "update",
                    "-p", "123",
                    "-d", "1",
                    "--display-name", "Fail",
                ],
            )

        assert result.exit_code == 3


class TestCustomDimensionsArchive:
    def test_archive_with_yes(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-dimensions", "archive", "-p", "123", "-d", "1", "--yes"],
            )

        assert result.exit_code == 0
        assert "archived" in result.output.lower()
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.archive.assert_called_once()

    def test_archive_prompts_without_yes(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.custom_dimensions.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.custom_dimensions.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["custom-dimensions", "archive", "-p", "123", "-d", "1"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_archive_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.custom_dimensions.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.custom_dimensions.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["custom-dimensions", "archive", "-p", "123", "-d", "1"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.archive.assert_not_called()

    def test_archive_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        cd = mock_client.properties.return_value.customDimensions.return_value
        cd.archive.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.custom_dimensions.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["custom-dimensions", "archive", "-p", "123", "-d", "1", "--yes"],
            )

        assert result.exit_code == 3
