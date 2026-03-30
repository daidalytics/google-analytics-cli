"""Tests for audience commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_AUDIENCES = [
    {
        "name": "properties/123/audiences/1001",
        "displayName": "Purchasers",
        "description": "Users who made a purchase",
        "membershipDurationDays": 30,
        "filterClauses": [
            {
                "clauseType": "INCLUDE",
                "simpleFilter": {
                    "scope": "AUDIENCE_FILTER_SCOPE_ACROSS_ALL_SESSIONS",
                    "filterExpression": {
                        "andGroup": {
                            "filterExpressions": [
                                {
                                    "orGroup": {
                                        "filterExpressions": [
                                            {
                                                "dimensionOrMetricFilter": {
                                                    "fieldName": "eventName",
                                                    "stringFilter": {
                                                        "matchType": "EXACT",
                                                        "value": "purchase",
                                                    },
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    },
                },
            }
        ],
        "createTime": "2024-01-01T00:00:00Z",
    },
    {
        "name": "properties/123/audiences/1002",
        "displayName": "All Users",
        "description": "All visitors",
        "membershipDurationDays": 540,
        "filterClauses": [],
        "createTime": "2024-06-01T00:00:00Z",
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with audiences methods."""
    mock_client = MagicMock()
    aud = mock_client.properties.return_value.audiences.return_value

    aud.list.return_value.execute.return_value = {
        "audiences": SAMPLE_AUDIENCES,
    }
    aud.get.return_value.execute.return_value = SAMPLE_AUDIENCES[0]
    aud.create.return_value.execute.return_value = SAMPLE_AUDIENCES[0]
    aud.patch.return_value.execute.return_value = SAMPLE_AUDIENCES[0]
    aud.archive.return_value.execute.return_value = {}

    return mock_client


class TestAudiencesList:
    def test_list_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["audiences", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "Purchasers" in result.output
        assert "All Users" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        aud = mock_client.properties.return_value.audiences.return_value
        aud.list.return_value.execute.return_value = {"audiences": []}

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["audiences", "list", "-p", "123"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["audiences", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        aud = mock_client.properties.return_value.audiences.return_value
        aud.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["audiences", "list", "-p", "123"])

        assert result.exit_code == 1

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["audiences", "list"])
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["audiences", "list"])

        assert result.exit_code == 0
        assert "Purchasers" in result.output


class TestAudiencesGet:
    def test_get_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "get", "-p", "123", "--audience-id", "1001"],
            )

        assert result.exit_code == 0
        assert "Purchasers" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "get", "-p", "123", "-a", "1001", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"filterClauses"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        aud = mock_client.properties.return_value.audiences.return_value
        aud.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "get", "-p", "123", "-a", "missing"],
            )

        assert result.exit_code == 1


class TestAudiencesCreate:
    def test_create_basic(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {
            "displayName": "Purchasers",
            "description": "Users who made a purchase",
            "membershipDurationDays": 30,
            "filterClauses": [
                {
                    "clauseType": "INCLUDE",
                    "simpleFilter": {
                        "scope": "AUDIENCE_FILTER_SCOPE_ACROSS_ALL_SESSIONS",
                        "filterExpression": {
                            "andGroup": {
                                "filterExpressions": [
                                    {
                                        "orGroup": {
                                            "filterExpressions": [
                                                {
                                                    "dimensionOrMetricFilter": {
                                                        "fieldName": "eventName",
                                                        "stringFilter": {
                                                            "matchType": "EXACT",
                                                            "value": "purchase",
                                                        },
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        },
                    },
                }
            ],
        }
        config_file = tmp_path / "audience.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "create", "-p", "123", "--config", str(config_file)],
            )

        assert result.exit_code == 0
        aud = mock_client.properties.return_value.audiences.return_value
        body = aud.create.call_args[1]["body"]
        assert body["displayName"] == "Purchasers"
        assert body["membershipDurationDays"] == 30
        assert len(body["filterClauses"]) == 1

    def test_create_missing_config_file(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "create", "-p", "123", "--config", "/nonexistent.json"],
            )

        assert result.exit_code != 0

    def test_create_invalid_json(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ not valid json }")

        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "create", "-p", "123", "--config", str(config_file)],
            )

        assert result.exit_code != 0

    def test_create_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        aud = mock_client.properties.return_value.audiences.return_value
        aud.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "audience.json"
        config_file.write_text(json.dumps({"displayName": "Test"}))

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "create", "-p", "123", "--config", str(config_file)],
            )

        assert result.exit_code == 1


class TestAudiencesUpdate:
    def test_update_display_name(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {"displayName": "New Name", "description": "Updated desc"}
        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "audiences", "update",
                    "-p", "123",
                    "-a", "1001",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        aud = mock_client.properties.return_value.audiences.return_value
        call_args = aud.patch.call_args
        assert call_args[1]["body"]["displayName"] == "New Name"
        assert call_args[1]["body"]["description"] == "Updated desc"
        mask = call_args[1]["updateMask"]
        assert "displayName" in mask
        assert "description" in mask

    def test_update_event_trigger(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {
            "eventTrigger": {
                "eventName": "audience_joined",
                "logCondition": "AUDIENCE_JOINED",
            }
        }
        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "audiences", "update",
                    "-p", "123",
                    "-a", "1001",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        aud = mock_client.properties.return_value.audiences.return_value
        call_args = aud.patch.call_args
        assert call_args[1]["updateMask"] == "eventTrigger"
        assert call_args[1]["body"]["eventTrigger"]["eventName"] == "audience_joined"

    def test_update_empty_config(self, tmp_path):
        config_file = tmp_path / "empty.json"
        config_file.write_text("{}")

        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "audiences", "update",
                    "-p", "123",
                    "-a", "1001",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code != 0

    def test_update_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        aud = mock_client.properties.return_value.audiences.return_value
        aud.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps({"displayName": "Fail"}))

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "audiences", "update",
                    "-p", "123",
                    "-a", "1001",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 1


class TestAudiencesArchive:
    def test_archive_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "archive", "-p", "123", "-a", "1001", "--yes"],
            )

        assert result.exit_code == 0
        assert "archived" in result.output.lower()
        aud = mock_client.properties.return_value.audiences.return_value
        aud.archive.assert_called_once()

    def test_archive_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.audiences.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.audiences.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["audiences", "archive", "-p", "123", "-a", "1001"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_archive_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.audiences.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.audiences.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["audiences", "archive", "-p", "123", "-a", "1001"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        aud = mock_client.properties.return_value.audiences.return_value
        aud.archive.assert_not_called()

    def test_archive_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        aud = mock_client.properties.return_value.audiences.return_value
        aud.archive.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.audiences.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["audiences", "archive", "-p", "123", "-a", "1001", "--yes"],
            )

        assert result.exit_code == 1
