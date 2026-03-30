"""Tests for event create rule commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_RULES = [
    {
        "name": "properties/123/dataStreams/456/eventCreateRules/r1",
        "destinationEvent": "custom_purchase",
        "eventConditions": [
            {
                "field": "event_name",
                "comparisonType": "EQUALS",
                "value": "purchase",
            }
        ],
        "sourceCopyParameters": True,
        "parameterMutations": [
            {"parameter": "source", "parameterValue": "custom"}
        ],
    },
    {
        "name": "properties/123/dataStreams/456/eventCreateRules/r2",
        "destinationEvent": "custom_signup",
        "eventConditions": [
            {
                "field": "event_name",
                "comparisonType": "EQUALS",
                "value": "sign_up",
            }
        ],
        "sourceCopyParameters": False,
        "parameterMutations": [],
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with eventCreateRules methods."""
    mock_client = MagicMock()
    ecr = (
        mock_client.properties.return_value
        .dataStreams.return_value
        .eventCreateRules.return_value
    )

    ecr.list.return_value.execute.return_value = {
        "eventCreateRules": SAMPLE_RULES,
    }
    ecr.get.return_value.execute.return_value = SAMPLE_RULES[0]
    ecr.create.return_value.execute.return_value = SAMPLE_RULES[0]
    ecr.patch.return_value.execute.return_value = SAMPLE_RULES[0]
    ecr.delete.return_value.execute.return_value = {}

    return mock_client


class TestEventCreateRulesList:
    def test_list_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "list", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 0
        assert "custom_purchase" in result.output
        assert "custom_signup" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.list.return_value.execute.return_value = {"eventCreateRules": []}

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "list", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "list", "-p", "123", "-s", "456", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"destinationEvent"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "list", "-p", "123", "-s", "456"],
            )

        assert result.exit_code == 1

    def test_list_missing_property_id(self):
        result = runner.invoke(
            app, ["event-create-rules", "list", "-s", "456"]
        )
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_missing_stream_id(self):
        result = runner.invoke(
            app, ["event-create-rules", "list", "-p", "123"]
        )
        assert result.exit_code != 0

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["event-create-rules", "list", "-s", "456"]
            )

        assert result.exit_code == 0
        assert "custom_purchase" in result.output


class TestEventCreateRulesGet:
    def test_get_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "get", "-p", "123", "-s", "456", "-r", "r1"],
            )

        assert result.exit_code == 0
        assert "custom_purchase" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "get", "-p", "123", "-s", "456", "-r", "r1", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"eventConditions"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "get", "-p", "123", "-s", "456", "-r", "missing"],
            )

        assert result.exit_code == 1


class TestEventCreateRulesCreate:
    def test_create_basic(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {
            "destinationEvent": "custom_purchase",
            "eventConditions": [
                {
                    "field": "event_name",
                    "comparisonType": "EQUALS",
                    "value": "purchase",
                }
            ],
            "sourceCopyParameters": True,
        }
        config_file = tmp_path / "rule.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "create",
                    "-p", "123", "-s", "456",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        body = ecr.create.call_args[1]["body"]
        assert body["destinationEvent"] == "custom_purchase"
        assert len(body["eventConditions"]) == 1

    def test_create_missing_config_file(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "create",
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
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "create",
                    "-p", "123", "-s", "456",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code != 0

    def test_create_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "rule.json"
        config_file.write_text(json.dumps({"destinationEvent": "test"}))

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "create",
                    "-p", "123", "-s", "456",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 1


class TestEventCreateRulesUpdate:
    def test_update_destination_event(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {"destinationEvent": "renamed_purchase"}
        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        call_args = ecr.patch.call_args
        assert call_args[1]["updateMask"] == "destinationEvent"
        assert call_args[1]["body"]["destinationEvent"] == "renamed_purchase"

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
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        assert ecr.patch.call_args[1]["updateMask"] == "eventConditions"

    def test_update_empty_config(self, tmp_path):
        config_file = tmp_path / "empty.json"
        config_file.write_text("{}")

        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code != 0

    def test_update_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps({"destinationEvent": "fail"}))

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "event-create-rules", "update",
                    "-p", "123", "-s", "456", "-r", "r1",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 1


class TestEventCreateRulesDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "delete", "-p", "123", "-s", "456", "-r", "r1", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.delete.assert_called_once()

    def test_delete_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.event_create_rules.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.event_create_rules.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["event-create-rules", "delete", "-p", "123", "-s", "456", "-r", "r1"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.event_create_rules.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.event_create_rules.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["event-create-rules", "delete", "-p", "123", "-s", "456", "-r", "r1"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.delete.assert_not_called()

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        ecr = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .eventCreateRules.return_value
        )
        ecr.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.event_create_rules.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["event-create-rules", "delete", "-p", "123", "-s", "456", "-r", "r1", "--yes"],
            )

        assert result.exit_code == 1
