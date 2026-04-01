"""Tests for event edit rule commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_RULES = [
    {
        "name": "properties/123/dataStreams/456/eventEditRules/r1",
        "displayName": "Edit purchase event",
        "eventConditions": [
            {
                "field": "event_name",
                "comparisonType": "EQUALS",
                "value": "purchase",
            }
        ],
        "parameterMutations": [
            {"parameter": "currency", "parameterValue": "USD"}
        ],
        "processingOrder": "1",
    },
    {
        "name": "properties/123/dataStreams/456/eventEditRules/r2",
        "displayName": "Edit signup event",
        "eventConditions": [
            {
                "field": "event_name",
                "comparisonType": "EQUALS",
                "value": "sign_up",
            }
        ],
        "parameterMutations": [
            {"parameter": "method", "parameterValue": "email"}
        ],
        "processingOrder": "2",
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with eventEditRules methods."""
    mock_client = MagicMock()
    eer = (
        mock_client.properties.return_value
        .dataStreams.return_value
        .eventEditRules.return_value
    )

    eer.list.return_value.execute.return_value = {
        "eventEditRules": SAMPLE_RULES,
    }
    eer.get.return_value.execute.return_value = SAMPLE_RULES[0]
    eer.create.return_value.execute.return_value = SAMPLE_RULES[0]
    eer.patch.return_value.execute.return_value = SAMPLE_RULES[0]
    eer.delete.return_value.execute.return_value = {}
    eer.reorder.return_value.execute.return_value = {}

    return mock_client


class TestEventEditRulesList:
    def test_list_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "list", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 0
        assert "Edit purchase event" in result.output
        assert "Edit signup event" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.list.return_value.execute.return_value = {"eventEditRules": []}

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "list", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "list", "-p", "123", "-s", "456", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "list", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 2

    def test_list_missing_property_id(self):
        result = runner.invoke(
            app, ["event-edit-rules", "list", "-s", "456"]
        )
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_missing_stream_id(self):
        result = runner.invoke(
            app, ["event-edit-rules", "list", "-p", "123"]
        )
        assert result.exit_code != 0

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["event-edit-rules", "list", "-s", "456"]
            )

        assert result.exit_code == 0
        assert "Edit purchase event" in result.output


class TestEventEditRulesGet:
    def test_get_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "get", "-p", "123", "-s", "456", "-r", "r1"],
            )

        assert result.exit_code == 0
        assert "Edit purchase event" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "get", "-p", "123", "-s", "456", "-r", "r1", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"eventConditions"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "get", "-p", "123", "-s", "456", "-r", "missing"],
            )

        assert result.exit_code == 3


class TestEventEditRulesCreate:
    def test_create_basic(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {
            "displayName": "Edit purchase event",
            "eventConditions": [
                {
                    "field": "event_name",
                    "comparisonType": "EQUALS",
                    "value": "purchase",
                }
            ],
            "parameterMutations": [
                {"parameter": "currency", "parameterValue": "USD"}
            ],
        }
        config_file = tmp_path / "rule.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "create",
                    "-p", "123", "-s", "456",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        body = eer.create.call_args[1]["body"]
        assert body["displayName"] == "Edit purchase event"
        assert len(body["eventConditions"]) == 1

    def test_create_missing_config_file(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "create",
                    "-p", "123", "-s", "456",
                    "--config", "/nonexistent.json",
                ],
            )

        assert result.exit_code != 0

    def test_create_invalid_json(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ not valid }")

        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "create",
                    "-p", "123", "-s", "456",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code != 0

    def test_create_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "rule.json"
        config_file.write_text(json.dumps({"displayName": "test"}))

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "create",
                    "-p", "123", "-s", "456",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 3


class TestEventEditRulesUpdate:
    def test_update_display_name(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {"displayName": "Renamed rule"}
        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        call_args = eer.patch.call_args
        assert call_args[1]["updateMask"] == "displayName"
        assert call_args[1]["body"]["displayName"] == "Renamed rule"

    def test_update_conditions(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {
            "eventConditions": [
                {"field": "event_name", "comparisonType": "CONTAINS", "value": "buy"}
            ]
        }
        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        assert eer.patch.call_args[1]["updateMask"] == "eventConditions"

    def test_update_empty_config(self, tmp_path):
        config_file = tmp_path / "empty.json"
        config_file.write_text("{}")

        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code != 0

    def test_update_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps({"displayName": "fail"}))

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 3


class TestEventEditRulesDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "delete", "-p", "123", "-s", "456", "-r", "r1", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.delete.assert_called_once()

    def test_delete_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.event_edit_rules.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["event-edit-rules", "delete", "-p", "123", "-s", "456", "-r", "r1"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.event_edit_rules.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["event-edit-rules", "delete", "-p", "123", "-s", "456", "-r", "r1"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.delete.assert_not_called()

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-edit-rules", "delete", "-p", "123", "-s", "456", "-r", "r1", "--yes"],
            )

        assert result.exit_code == 3


class TestEventEditRulesReorder:
    def test_reorder_success(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "reorder",
                    "-p", "123", "-s", "456",
                    "--rule-ids", "r2,r1",
                ],
            )

        assert result.exit_code == 0
        assert "reordered" in result.output.lower()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        call_args = eer.reorder.call_args[1]
        assert call_args["parent"] == "properties/123/dataStreams/456"
        assert call_args["body"]["eventEditRules"] == [
            "properties/123/dataStreams/456/eventEditRules/r2",
            "properties/123/dataStreams/456/eventEditRules/r1",
        ]

    def test_reorder_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        eer = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventEditRules.return_value
        )
        eer.reorder.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.event_edit_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-edit-rules", "reorder",
                    "-p", "123", "-s", "456",
                    "--rule-ids", "r1,r2",
                ],
            )

        assert result.exit_code == 3

    def test_reorder_missing_property_id(self):
        result = runner.invoke(
            app,
            ["event-edit-rules", "reorder", "-s", "456", "--rule-ids", "r1,r2"],
        )
        assert result.exit_code != 0
