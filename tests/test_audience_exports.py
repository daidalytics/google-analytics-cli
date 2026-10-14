"""Tests for audience export commands (Data API v1beta)."""

import json
import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

PATCH_CLIENT = "ga_cli.commands.audience_exports.get_data_client"

EXPORT_ACTIVE = {
    "name": "properties/123/audienceExports/789",
    "audience": "properties/123/audiences/456",
    "audienceDisplayName": "Purchasers",
    "dimensions": [{"dimensionName": "deviceId"}, {"dimensionName": "userId"}],
    "state": "ACTIVE",
    "beginCreatingTime": "2026-10-01T12:00:00.123456Z",
    "creationQuotaTokensCharged": 50,
    "rowCount": 2,
    "percentageCompleted": 100,
}

EXPORT_CREATING = {
    "name": "properties/123/audienceExports/790",
    "audience": "properties/123/audiences/457",
    "audienceDisplayName": "Cart Abandoners",
    "dimensions": [{"dimensionName": "deviceId"}],
    "state": "CREATING",
    "beginCreatingTime": "2026-10-02T08:30:00Z",
    "percentageCompleted": 42,
}

EXPORT_FAILED = {
    "name": "properties/123/audienceExports/791",
    "audience": "properties/123/audiences/458",
    "audienceDisplayName": "Churned",
    "dimensions": [{"dimensionName": "deviceId"}],
    "state": "FAILED",
    "beginCreatingTime": "2026-10-03T09:00:00Z",
    "errorMessage": "Quota exhausted for property",
}


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _mock_data_client():
    """Return (client, audienceExports resource mock)."""
    client = MagicMock()
    exports = client.properties.return_value.audienceExports.return_value
    exports.list.return_value.execute.return_value = {
        "audienceExports": [EXPORT_ACTIVE, EXPORT_CREATING],
    }
    exports.get.return_value.execute.return_value = EXPORT_ACTIVE
    return client, exports


def _http_error(status: int, message: str, api_status: str = ""):
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = status
    resp.reason = "Error"
    content = json.dumps(
        {"error": {"code": status, "message": message, "status": api_status}}
    ).encode()
    return HttpError(resp, content)


def _describe():
    result = runner.invoke(app, ["--describe"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["commands"]


class TestExportIdParsing:
    def test_extracts_numeric_id_from_resource_name(self):
        from ga_cli.commands.audience_exports import _export_id

        assert _export_id("properties/123/audienceExports/789") == "789"

    def test_returns_input_when_not_a_resource_name(self):
        from ga_cli.commands.audience_exports import _export_id

        assert _export_id("789") == "789"
        assert _export_id("") == ""


class TestAudienceExportsList:
    def test_list_follows_next_page_token(self):
        client, exports = _mock_data_client()
        exports.list.return_value.execute.side_effect = [
            {"audienceExports": [EXPORT_ACTIVE], "nextPageToken": "page-2"},
            {"audienceExports": [EXPORT_CREATING, EXPORT_FAILED]},
        ]

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app, ["audience-exports", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == [EXPORT_ACTIVE, EXPORT_CREATING, EXPORT_FAILED]
        calls = exports.list.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["parent"] == "properties/123"
        assert "pageToken" not in calls[0].kwargs
        assert calls[1].kwargs["parent"] == "properties/123"
        assert calls[1].kwargs["pageToken"] == "page-2"

    def test_list_json_is_raw_list_of_exports(self):
        client, _ = _mock_data_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app, ["audience-exports", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert json.loads(result.stdout) == [EXPORT_ACTIVE, EXPORT_CREATING]

    def test_list_table_shows_numeric_export_id_and_summary_columns(self):
        client, _ = _mock_data_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app, ["audience-exports", "list", "-p", "123", "-o", "table"]
            )

        out = _strip_ansi(result.output)
        assert result.exit_code == 0, out
        assert "789" in out
        assert "790" in out
        assert "audienceExports/" not in out
        assert "Purchasers" in out
        assert "ACTIVE" in out
        assert "CREATING" in out
        assert "42%" in out
        # Timestamp shortened to seconds (may wrap at the runner's 80 columns).
        assert "2026-10-01" in out
        assert "12:00:00" in out
        assert ".123456Z" not in out
        for header in ("Export ID", "Audience", "State", "Rows", "% Complete", "Created"):
            assert header in out

    def test_list_empty(self):
        client, exports = _mock_data_client()
        exports.list.return_value.execute.return_value = {}

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app, ["audience-exports", "list", "-p", "123", "-o", "table"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["audience-exports", "list"])
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default_property(self):
        save_config(UserConfig(default_property_id="555"))
        client, exports = _mock_data_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, ["audience-exports", "list", "-o", "json"])

        assert result.exit_code == 0
        assert exports.list.call_args.kwargs["parent"] == "properties/555"

    def test_list_api_error_is_classified(self):
        client, exports = _mock_data_client()
        exports.list.return_value.execute.side_effect = _http_error(403, "Forbidden")

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, ["audience-exports", "list", "-p", "123"])

        assert result.exit_code == 2


class TestAudienceExportsGet:
    def test_get_calls_full_resource_name(self):
        client, exports = _mock_data_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app,
                ["audience-exports", "get", "-p", "123", "--export-id", "789", "-o", "json"],
            )

        assert result.exit_code == 0, result.output
        exports.get.assert_called_once_with(name="properties/123/audienceExports/789")

    def test_get_json_is_raw_passthrough(self):
        client, _ = _mock_data_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app,
                ["audience-exports", "get", "-p", "123", "--export-id", "789", "-o", "json"],
            )

        assert json.loads(result.stdout) == EXPORT_ACTIVE

    def test_get_table(self):
        client, _ = _mock_data_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app,
                ["audience-exports", "get", "-p", "123", "--export-id", "789", "-o", "table"],
            )

        assert result.exit_code == 0
        assert "Purchasers" in _strip_ansi(result.output)

    def test_get_requires_export_id(self):
        result = runner.invoke(app, ["audience-exports", "get", "-p", "123"])
        assert result.exit_code != 0
        assert "export-id" in _strip_ansi(result.output)

    def test_get_missing_property_id(self):
        result = runner.invoke(app, ["audience-exports", "get", "--export-id", "789"])
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_get_not_found_exits_3(self):
        client, exports = _mock_data_client()
        exports.get.return_value.execute.side_effect = _http_error(
            404, "Audience export not found", "NOT_FOUND"
        )

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app, ["audience-exports", "get", "-p", "123", "--export-id", "999"]
            )

        assert result.exit_code == 3
        assert "not found" in result.output


class TestAudienceExportsDescribe:
    def test_read_commands_are_not_mutative(self):
        commands = _describe()
        for name in ("ga audience-exports list", "ga audience-exports get"):
            assert name in commands, f"{name} missing from --describe"
            assert commands[name]["mutative"] is False

    def test_export_id_flag_is_long_only(self):
        commands = _describe()
        export_id = commands["ga audience-exports get"]["parameters"]["properties"]["export_id"]
        assert export_id["flag"] == "--export-id"
        assert "aliases" not in export_id
