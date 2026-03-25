"""Tests for data-streams commands (list, get, create, delete)."""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _mock_admin_client(streams=None, stream_detail=None):
    """Create a mock Admin API client with dataStreams methods."""
    mock_client = MagicMock()

    ds = mock_client.properties.return_value.dataStreams.return_value

    ds.list.return_value.execute.return_value = {
        "dataStreams": streams or [],
    }
    ds.get.return_value.execute.return_value = stream_detail or {}
    ds.create.return_value.execute.return_value = stream_detail or {}
    ds.delete.return_value.execute.return_value = {}
    ds.patch.return_value.execute.return_value = stream_detail or {}

    return mock_client


SAMPLE_STREAMS = [
    {
        "name": "properties/111/dataStreams/1001",
        "type": "WEB_DATA_STREAM",
        "displayName": "My Website Stream",
        "createTime": "2023-01-01T00:00:00Z",
        "webStreamData": {"defaultUri": "https://example.com"},
    },
    {
        "name": "properties/111/dataStreams/1002",
        "type": "ANDROID_APP_DATA_STREAM",
        "displayName": "My Android App",
        "createTime": "2023-06-01T00:00:00Z",
        "androidAppStreamData": {"packageName": "com.example.app"},
    },
]


class TestDataStreamsList:
    def test_list_with_flag(self):
        mock_client = _mock_admin_client(streams=SAMPLE_STREAMS)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["data-streams", "list", "--property-id", "111"]
            )

        assert result.exit_code == 0
        assert "My Website Stream" in result.output
        assert "My Android App" in result.output

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="111"))
        mock_client = _mock_admin_client(streams=SAMPLE_STREAMS)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["data-streams", "list"])

        assert result.exit_code == 0
        assert "My Website Stream" in result.output

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["data-streams", "list"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_json_output(self):
        mock_client = _mock_admin_client(streams=SAMPLE_STREAMS)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["data-streams", "list", "-p", "111", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"WEB_DATA_STREAM"' in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client(streams=[])

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["data-streams", "list", "-p", "111"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output


class TestDataStreamsGet:
    def test_get_stream(self):
        detail = SAMPLE_STREAMS[0]
        mock_client = _mock_admin_client(stream_detail=detail)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["data-streams", "get", "-p", "111", "--stream-id", "1001"],
            )

        assert result.exit_code == 0
        assert "My Website Stream" in result.output

    def test_get_requires_stream_id(self):
        result = runner.invoke(
            app, ["data-streams", "get", "-p", "111"]
        )

        assert result.exit_code != 0

    def test_get_requires_property_id(self):
        result = runner.invoke(
            app, ["data-streams", "get", "--stream-id", "1001"]
        )

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()


class TestDataStreamsCreate:
    def test_create_web_stream(self):
        created = {
            "name": "properties/111/dataStreams/2001",
            "type": "WEB_DATA_STREAM",
            "displayName": "New Web Stream",
            "webStreamData": {"defaultUri": "https://new.example.com"},
        }
        mock_client = _mock_admin_client(stream_detail=created)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "data-streams",
                    "create",
                    "-p",
                    "111",
                    "--display-name",
                    "New Web Stream",
                    "--url",
                    "https://new.example.com",
                ],
            )

        assert result.exit_code == 0
        assert "New Web Stream" in result.output

        # Verify the body includes webStreamData
        call_args = (
            mock_client.properties.return_value.dataStreams.return_value.create.call_args
        )
        body = call_args[1]["body"]
        assert body["webStreamData"]["defaultUri"] == "https://new.example.com"

    def test_create_web_stream_missing_url(self):
        result = runner.invoke(
            app,
            [
                "data-streams",
                "create",
                "-p",
                "111",
                "--display-name",
                "No URL",
                "--type",
                "WEB_DATA_STREAM",
            ],
        )

        assert result.exit_code != 0
        assert "url" in result.output.lower()

    def test_create_android_stream(self):
        created = {
            "name": "properties/111/dataStreams/2002",
            "type": "ANDROID_APP_DATA_STREAM",
            "displayName": "Android Stream",
        }
        mock_client = _mock_admin_client(stream_detail=created)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "data-streams",
                    "create",
                    "-p",
                    "111",
                    "--display-name",
                    "Android Stream",
                    "--type",
                    "ANDROID_APP_DATA_STREAM",
                    "--bundle-id",
                    "com.example.app",
                ],
            )

        assert result.exit_code == 0
        call_args = (
            mock_client.properties.return_value.dataStreams.return_value.create.call_args
        )
        body = call_args[1]["body"]
        assert body["androidAppStreamData"]["packageName"] == "com.example.app"

    def test_create_android_stream_missing_bundle_id(self):
        result = runner.invoke(
            app,
            [
                "data-streams",
                "create",
                "-p",
                "111",
                "--display-name",
                "No Bundle",
                "--type",
                "ANDROID_APP_DATA_STREAM",
            ],
        )

        assert result.exit_code != 0
        assert "bundle-id" in _strip_ansi(result.output).lower()

    def test_create_ios_stream(self):
        created = {
            "name": "properties/111/dataStreams/2003",
            "type": "IOS_APP_DATA_STREAM",
            "displayName": "iOS Stream",
        }
        mock_client = _mock_admin_client(stream_detail=created)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "data-streams",
                    "create",
                    "-p",
                    "111",
                    "--display-name",
                    "iOS Stream",
                    "--type",
                    "IOS_APP_DATA_STREAM",
                    "--bundle-id",
                    "com.example.iosapp",
                ],
            )

        assert result.exit_code == 0
        call_args = (
            mock_client.properties.return_value.dataStreams.return_value.create.call_args
        )
        body = call_args[1]["body"]
        assert body["iosAppStreamData"]["bundleId"] == "com.example.iosapp"

    def test_create_missing_property_id(self):
        result = runner.invoke(
            app,
            [
                "data-streams",
                "create",
                "--display-name",
                "Test",
                "--url",
                "https://test.com",
            ],
        )

        assert result.exit_code != 0
        assert "property-id" in _strip_ansi(result.output).lower()


class TestDataStreamsDelete:
    def test_delete_with_confirmation(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.data_streams.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.data_streams.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True

            result = runner.invoke(
                app,
                ["data-streams", "delete", "-p", "111", "--stream-id", "1001"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.data_streams.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.data_streams.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False

            result = runner.invoke(
                app,
                ["data-streams", "delete", "-p", "111", "--stream-id", "1001"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        mock_client.properties.return_value.dataStreams.return_value.delete.assert_not_called()

    def test_delete_skip_confirmation(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "data-streams",
                    "delete",
                    "-p",
                    "111",
                    "-s",
                    "1001",
                    "--yes",
                ],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_missing_stream_id(self):
        result = runner.invoke(
            app, ["data-streams", "delete", "-p", "111"]
        )

        assert result.exit_code != 0


class TestDataStreamsUpdate:
    def test_update_display_name(self):
        updated = {
            "name": "properties/111/dataStreams/1001",
            "type": "WEB_DATA_STREAM",
            "displayName": "Renamed Stream",
        }
        mock_client = _mock_admin_client(stream_detail=updated)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "data-streams", "update",
                    "-p", "111",
                    "-s", "1001",
                    "--display-name", "Renamed Stream",
                ],
            )

        assert result.exit_code == 0
        assert "Renamed Stream" in result.output
        call_args = (
            mock_client.properties.return_value.dataStreams.return_value.patch.call_args
        )
        assert call_args[1]["updateMask"] == "displayName"
        assert call_args[1]["body"]["displayName"] == "Renamed Stream"

    def test_update_no_fields(self):
        result = runner.invoke(
            app, ["data-streams", "update", "-p", "111", "-s", "1001"]
        )

        assert result.exit_code != 0

    def test_update_json_output(self):
        updated = {
            "name": "properties/111/dataStreams/1001",
            "displayName": "Updated",
        }
        mock_client = _mock_admin_client(stream_detail=updated)

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "data-streams", "update",
                    "-p", "111", "-s", "1001",
                    "--display-name", "Updated",
                    "-o", "json",
                ],
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_update_api_error(self):
        mock_client = MagicMock()
        ds = mock_client.properties.return_value.dataStreams.return_value
        ds.patch.return_value.execute.side_effect = Exception("API error")

        with patch(
            "ga_cli.commands.data_streams.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "data-streams", "update",
                    "-p", "111", "-s", "1001",
                    "--display-name", "Fail",
                ],
            )

        assert result.exit_code != 0
