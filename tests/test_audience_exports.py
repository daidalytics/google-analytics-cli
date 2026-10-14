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


def _flat(text: str) -> str:
    """Strip ANSI and undo Rich's word-wrapping at the runner's 80 columns."""
    return " ".join(_strip_ansi(text).split())


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


QUERY_RESPONSE = {
    "audienceExport": {
        **EXPORT_ACTIVE,
        # Deliberately not alphabetical: columns must follow this order.
        "dimensions": [{"dimensionName": "userId"}, {"dimensionName": "deviceId"}],
    },
    "audienceRows": [
        {"dimensionValues": [{"value": "user-a"}, {"value": "1000276123.1681742376"}]},
        {"dimensionValues": [{"value": "user-b"}, {"value": "1000374452.1668627377"}]},
    ],
    "rowCount": 2,
}


def _query_args(*extra):
    return ["audience-exports", "query", "-p", "123", "--export-id", "789", *extra]


class TestAudienceExportsQuery:
    def _client(self, response=None):
        client, exports = _mock_data_client()
        exports.query.return_value.execute.return_value = (
            QUERY_RESPONSE if response is None else response
        )
        return client, exports

    def test_query_calls_full_resource_name_with_empty_body_by_default(self):
        client, exports = self._client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "json"))

        assert result.exit_code == 0, result.output
        exports.query.assert_called_once_with(
            name="properties/123/audienceExports/789", body={}
        )

    def test_query_sends_limit_and_offset_as_strings(self):
        client, exports = self._client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app, _query_args("--limit", "10000", "--offset", "0", "-o", "json")
            )

        assert result.exit_code == 0, result.output
        assert exports.query.call_args.kwargs["body"] == {"limit": "10000", "offset": "0"}

    def test_query_sends_only_the_provided_paging_field(self):
        client, exports = self._client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("--limit", "50", "-o", "json"))

        assert result.exit_code == 0
        assert exports.query.call_args.kwargs["body"] == {"limit": "50"}

    def test_query_rejects_non_positive_limit(self):
        result = runner.invoke(app, _query_args("--limit", "0"))
        assert result.exit_code != 0
        assert "--limit" in _strip_ansi(result.output)

    def test_query_json_is_raw_response(self):
        client, _ = self._client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "json"))

        assert json.loads(result.stdout) == QUERY_RESPONSE

    def test_query_table_has_one_column_per_dimension_in_export_order(self):
        client, _ = self._client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        out = _strip_ansi(result.stdout)
        assert result.exit_code == 0, out
        header = next(line for line in out.splitlines() if "userId" in line)
        assert "deviceId" in header
        assert header.index("userId") < header.index("deviceId")
        assert "user-a" in out
        assert "user-b" in out
        assert "1000276123.1681742376" in out

    def test_query_empty_rows_renders_standard_empty_output(self):
        client, _ = self._client(
            {"audienceExport": QUERY_RESPONSE["audienceExport"], "rowCount": 0}
        )

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_query_table_hints_at_next_offset_when_more_rows_exist(self):
        client, _ = self._client({**QUERY_RESPONSE, "rowCount": 5})

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("--offset", "2", "-o", "table"))

        assert result.exit_code == 0
        err = _strip_ansi(result.stderr)
        assert "of 5" in err
        assert "--offset 4" in err

    def test_query_missing_property_id(self):
        result = runner.invoke(app, ["audience-exports", "query", "--export-id", "789"])
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()


class TestAudienceExportsQueryNotActive:
    RAW_API_MESSAGE = "Audience export is not ready for query. raw-api-detail"

    def _client(self, export_state=None, get_error=None, status=400):
        client, exports = _mock_data_client()
        exports.query.return_value.execute.side_effect = _http_error(
            status, self.RAW_API_MESSAGE, "FAILED_PRECONDITION"
        )
        if get_error is not None:
            exports.get.return_value.execute.side_effect = get_error
        elif export_state is not None:
            exports.get.return_value.execute.return_value = export_state
        return client, exports

    def test_creating_export_gives_friendly_message(self):
        client, exports = self._client({**EXPORT_CREATING, "name": EXPORT_ACTIVE["name"]})

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        out = _flat(result.output)
        assert result.exit_code == 3
        assert "export 789 is still CREATING (42%) — try again later" in out
        assert "raw-api-detail" not in out
        exports.get.assert_called_once_with(name="properties/123/audienceExports/789")

    def test_failed_export_includes_error_message(self):
        client, _ = self._client({**EXPORT_FAILED, "name": EXPORT_ACTIVE["name"]})

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        out = _flat(result.output)
        assert result.exit_code == 3
        assert "export 789 FAILED: Quota exhausted for property" in out
        assert "raw-api-detail" not in out

    def test_friendly_error_is_structured_in_json_mode(self):
        client, _ = self._client({**EXPORT_CREATING, "name": EXPORT_ACTIVE["name"]})

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "json"))

        assert result.exit_code == 3
        assert result.stdout == ""
        payload = json.loads(_strip_ansi(result.stderr).strip())
        assert payload["error"] is True
        assert payload["exit_code"] == 3
        assert payload["category"] == "api_error"
        assert "still CREATING (42%)" in payload["message"]

    def test_active_export_surfaces_original_error(self):
        client, _ = self._client(EXPORT_ACTIVE)

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        assert result.exit_code == 3
        assert "raw-api-detail" in _strip_ansi(result.output)

    def test_get_failure_surfaces_original_error(self):
        client, _ = self._client(get_error=_http_error(404, "not found", "NOT_FOUND"))

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        assert result.exit_code == 3
        assert "raw-api-detail" in _strip_ansi(result.output)

    def test_auth_error_keeps_its_exit_code_when_state_is_active(self):
        client, _ = self._client(EXPORT_ACTIVE, status=403)

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        assert result.exit_code == 2

    def test_server_error_does_not_look_up_state(self):
        client, exports = self._client(EXPORT_CREATING, status=503)

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _query_args("-o", "table"))

        assert result.exit_code == 3
        assert "raw-api-detail" in _strip_ansi(result.output)
        exports.get.assert_not_called()


NEW_EXPORT_NAME = "properties/123/audienceExports/789"

# Shape documented in the Data API "audience export basics" guide.
OPERATION_WITH_RESPONSE = {
    "name": "properties/123/operations/op-1",
    "response": {
        "@type": "type.googleapis.com/google.analytics.data.v1beta.AudienceExport",
        "name": NEW_EXPORT_NAME,
        "audience": "properties/123/audiences/456",
        "dimensions": [{"dimensionName": "deviceId"}],
        "state": "CREATING",
        "beginCreatingTime": "2026-10-14T10:00:00Z",
    },
}

OPERATION_WITH_METADATA = {
    "name": "properties/123/operations/op-2",
    "done": False,
    "metadata": {
        "@type": "type.googleapis.com/google.analytics.data.v1beta.AudienceExportMetadata",
        "target": {"resources": ["properties/123/audiences/456", NEW_EXPORT_NAME]},
    },
}

OPERATION_WITHOUT_NAME = {"name": "properties/123/operations/op-3", "done": False}


def _create_args(*extra, audience_id="456", dimensions="deviceId"):
    return [
        "audience-exports", "create", "-p", "123",
        "--audience-id", audience_id, "--dimensions", dimensions, *extra,
    ]


def _create_client(operation=None):
    client, exports = _mock_data_client()
    exports.create.return_value.execute.return_value = (
        OPERATION_WITH_RESPONSE if operation is None else operation
    )
    return client, exports


class FakeClock:
    """Stands in for time.monotonic/time.sleep: sleeping advances the clock."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class TestAudienceExportsCreate:
    def test_dry_run_prints_exact_payload_and_builds_no_client(self):
        with patch(PATCH_CLIENT) as get_client:
            result = runner.invoke(
                app, _create_args("--dry-run", dimensions=" deviceId , userId ")
            )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {
            "dry_run": True,
            "action": "create",
            "method": "POST",
            "resource": "properties/123/audienceExports",
            "idempotent": False,
            "body": {
                "audience": "properties/123/audiences/456",
                "dimensions": [{"dimensionName": "deviceId"}, {"dimensionName": "userId"}],
            },
        }
        get_client.assert_not_called()

    def test_dry_run_with_wait_does_not_poll(self):
        with patch(PATCH_CLIENT) as get_client:
            result = runner.invoke(app, _create_args("--dry-run", "--wait"))

        assert result.exit_code == 0
        assert json.loads(result.stdout)["dry_run"] is True
        get_client.assert_not_called()

    def test_numeric_audience_id_expands_to_resource_name(self):
        client, exports = _create_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _create_args("-o", "json"))

        assert result.exit_code == 0, result.output
        exports.create.assert_called_once_with(
            parent="properties/123",
            body={
                "audience": "properties/123/audiences/456",
                "dimensions": [{"dimensionName": "deviceId"}],
            },
        )

    def test_full_audience_name_is_used_as_is(self):
        client, exports = _create_client()

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(
                app, _create_args("-o", "json", audience_id="properties/999/audiences/456")
            )

        assert result.exit_code == 0, result.output
        body = exports.create.call_args.kwargs["body"]
        assert body["audience"] == "properties/999/audiences/456"

    def test_invalid_audience_id_is_rejected_before_any_api_call(self):
        with patch(PATCH_CLIENT) as get_client:
            result = runner.invoke(app, _create_args(audience_id="purchasers"))

        assert result.exit_code != 0
        assert "--audience-id" in _strip_ansi(result.output)
        get_client.assert_not_called()

    def test_dimensions_are_required(self):
        result = runner.invoke(
            app, ["audience-exports", "create", "-p", "123", "--audience-id", "456"]
        )
        assert result.exit_code != 0
        assert "--dimensions" in _strip_ansi(result.output)

    def test_blank_dimensions_are_rejected(self):
        with patch(PATCH_CLIENT) as get_client:
            result = runner.invoke(app, _create_args(dimensions=" , "))

        assert result.exit_code != 0
        assert "--dimensions" in _strip_ansi(result.output)
        get_client.assert_not_called()

    def test_create_missing_property_id(self):
        result = runner.invoke(
            app,
            ["audience-exports", "create", "--audience-id", "456", "--dimensions", "deviceId"],
        )
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_create_api_error_exits_3(self):
        client, exports = _create_client()
        exports.create.return_value.execute.side_effect = _http_error(
            400, "Dimension 'bogus' is not valid", "INVALID_ARGUMENT"
        )

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _create_args(dimensions="bogus"))

        assert result.exit_code == 3
        assert "bogus" in _strip_ansi(result.output)


class TestCreateExportNameExtraction:
    def test_name_from_operation_response(self):
        client, exports = _create_client(OPERATION_WITH_RESPONSE)

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _create_args("-o", "json"))

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {
            "exportName": NEW_EXPORT_NAME,
            "exportId": "789",
            "operation": OPERATION_WITH_RESPONSE,
        }
        exports.list.assert_not_called()

    def test_name_from_operation_metadata(self):
        client, exports = _create_client(OPERATION_WITH_METADATA)

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _create_args("-o", "json"))

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["exportName"] == NEW_EXPORT_NAME
        assert payload["exportId"] == "789"
        assert payload["operation"] == OPERATION_WITH_METADATA
        exports.list.assert_not_called()

    def test_name_from_list_fallback_picks_newest_export_for_the_audience(self):
        client, exports = _create_client(OPERATION_WITHOUT_NAME)
        audience = "properties/123/audiences/456"
        exports.list.return_value.execute.side_effect = [
            {
                "audienceExports": [
                    {"name": "properties/123/audienceExports/1", "audience": audience,
                     "beginCreatingTime": "2026-10-13T10:00:00Z"},
                    # Newest overall, but a different audience.
                    {"name": "properties/123/audienceExports/2",
                     "audience": "properties/123/audiences/999",
                     "beginCreatingTime": "2026-10-14T11:00:00Z"},
                ],
                "nextPageToken": "p2",
            },
            {
                "audienceExports": [
                    # Same second as /3 but later; a plain string compare gets this wrong.
                    {"name": "properties/123/audienceExports/4", "audience": audience,
                     "beginCreatingTime": "2026-10-14T10:00:00.5Z"},
                    {"name": "properties/123/audienceExports/3", "audience": audience,
                     "beginCreatingTime": "2026-10-14T10:00:00Z"},
                ],
            },
        ]

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _create_args("-o", "json"))

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["exportName"] == "properties/123/audienceExports/4"
        assert payload["exportId"] == "4"
        assert payload["operation"] == OPERATION_WITHOUT_NAME
        assert exports.list.call_args_list[0].kwargs["parent"] == "properties/123"
        assert exports.list.call_args_list[1].kwargs["pageToken"] == "p2"

    def test_unknown_name_still_outputs_operation_and_warns(self):
        client, exports = _create_client(OPERATION_WITHOUT_NAME)
        exports.list.return_value.execute.return_value = {"audienceExports": []}

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _create_args("-o", "json"))

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["exportName"] is None
        assert payload["exportId"] is None
        assert payload["operation"] == OPERATION_WITHOUT_NAME
        assert "ga audience-exports list -p 123" in _flat(result.stderr)

    def test_fallback_list_failure_does_not_fail_a_successful_create(self):
        client, exports = _create_client(OPERATION_WITHOUT_NAME)
        exports.list.return_value.execute.side_effect = _http_error(503, "Backend unavailable")

        with patch(PATCH_CLIENT, return_value=client):
            result = runner.invoke(app, _create_args("-o", "json"))

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["exportName"] is None
        assert "Backend unavailable" in _flat(result.stderr)


class TestCreateWait:
    def _run(self, get_side_effect, *extra, operation=None):
        client, exports = _create_client(operation)
        exports.get.return_value.execute.side_effect = get_side_effect
        clock = FakeClock()
        with patch(PATCH_CLIENT, return_value=client), patch(
            "ga_cli.commands.audience_exports.time.monotonic", clock.monotonic
        ), patch("ga_cli.commands.audience_exports.time.sleep", clock.sleep):
            result = runner.invoke(app, _create_args("--wait", *extra))
        return result, exports, clock

    def test_wait_until_active_outputs_export_and_exits_0(self):
        creating = {**EXPORT_CREATING, "name": NEW_EXPORT_NAME}
        active = {**EXPORT_ACTIVE, "name": NEW_EXPORT_NAME}
        result, exports, clock = self._run(
            [
                {**creating, "percentageCompleted": 10},
                {**creating, "percentageCompleted": 60},
                active,
            ],
            "-o", "json",
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == active
        assert clock.sleeps == [10, 20]
        for call in exports.get.call_args_list:
            assert call.kwargs == {"name": NEW_EXPORT_NAME}
        err = _flat(result.stderr)
        assert "Created export 789" in err
        assert "Export 789: CREATING (10%)" in err
        assert "Export 789: CREATING (60%)" in err

    def test_wait_backs_off_from_10s_to_a_60s_cap(self):
        creating = {**EXPORT_CREATING, "name": NEW_EXPORT_NAME}
        result, _, clock = self._run(
            [creating] * 6 + [{**EXPORT_ACTIVE, "name": NEW_EXPORT_NAME}], "-o", "json"
        )

        assert result.exit_code == 0, result.output
        assert clock.sleeps == [10, 20, 40, 60, 60, 60]

    def test_wait_failed_exits_3_with_error_message(self):
        result, _, clock = self._run(
            [
                {**EXPORT_CREATING, "name": NEW_EXPORT_NAME},
                {**EXPORT_FAILED, "name": NEW_EXPORT_NAME},
            ],
            "-o", "table",
        )

        assert result.exit_code == 3
        assert "export 789 FAILED: Quota exhausted for property" in _flat(result.output)
        assert clock.sleeps == [10]

    def test_wait_timeout_exits_3_with_get_hint(self):
        creating = {**EXPORT_CREATING, "name": NEW_EXPORT_NAME}
        result, exports, clock = self._run(
            [creating] * 10, "--timeout", "30", "-o", "table"
        )

        assert result.exit_code == 3
        out = _flat(result.output)
        assert "export 789 is still CREATING after 30s" in out
        assert "check later with `ga audience-exports get -p 123 --export-id 789`" in out
        # Polls at t=0, 10, 30; the last sleep is clipped to the deadline.
        assert clock.sleeps == [10, 20]
        assert exports.get.call_count == 3

    def test_wait_timeout_is_structured_in_json_mode(self):
        creating = {**EXPORT_CREATING, "name": NEW_EXPORT_NAME}
        result, _, _ = self._run([creating] * 10, "--timeout", "5", "-o", "json")

        assert result.exit_code == 3
        assert result.stdout == ""
        lines = [ln for ln in _strip_ansi(result.stderr).splitlines() if ln.startswith("{")]
        payload = json.loads(lines[-1])
        assert payload["exit_code"] == 3
        assert payload["category"] == "api_error"
        assert "--export-id 789" in payload["message"]

    def test_wait_without_export_name_exits_3_without_polling(self):
        client, exports = _create_client(OPERATION_WITHOUT_NAME)
        exports.list.return_value.execute.return_value = {"audienceExports": []}

        with patch(PATCH_CLIENT, return_value=client), patch(
            "ga_cli.commands.audience_exports.time.sleep"
        ) as sleep:
            result = runner.invoke(app, _create_args("--wait", "-o", "table"))

        assert result.exit_code == 3
        assert "ga audience-exports list -p 123" in _flat(result.output)
        exports.get.assert_not_called()
        sleep.assert_not_called()

    def test_wait_polls_name_found_via_list_fallback(self):
        client, exports = _create_client(OPERATION_WITHOUT_NAME)
        exports.list.return_value.execute.return_value = {
            "audienceExports": [{**EXPORT_CREATING, "name": "properties/123/audienceExports/42",
                                 "audience": "properties/123/audiences/456"}],
        }
        exports.get.return_value.execute.return_value = {
            **EXPORT_ACTIVE, "name": "properties/123/audienceExports/42"
        }
        clock = FakeClock()

        with patch(PATCH_CLIENT, return_value=client), patch(
            "ga_cli.commands.audience_exports.time.monotonic", clock.monotonic
        ), patch("ga_cli.commands.audience_exports.time.sleep", clock.sleep):
            result = runner.invoke(app, _create_args("--wait", "-o", "json"))

        assert result.exit_code == 0, result.output
        exports.get.assert_called_once_with(name="properties/123/audienceExports/42")
        assert clock.sleeps == []


class TestCreateDescribe:
    def test_create_is_mutative_with_dry_run(self):
        commands = _describe()
        cmd = commands.get("ga audience-exports create")
        assert cmd is not None, "ga audience-exports create missing from --describe"
        assert cmd["mutative"] is True
        assert cmd["supports_dry_run"] is True

    def test_query_is_not_mutative(self):
        assert _describe()["ga audience-exports query"]["mutative"] is False

    def test_create_parameters(self):
        params = _describe()["ga audience-exports create"]["parameters"]
        props = params["properties"]
        assert "audience_id" in params["required"]
        assert "dimensions" in params["required"]
        assert props["audience_id"]["flag"] == "--audience-id"
        assert "aliases" not in props["audience_id"]
        assert props["timeout"]["default"] == 1800
        assert props["wait"]["default"] is False
