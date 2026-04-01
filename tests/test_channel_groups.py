"""Tests for channel group commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_GROUPS = [
    {
        "name": "properties/123/channelGroups/1001",
        "displayName": "Default Channel Group",
        "description": "System-defined channel group",
        "systemDefined": True,
        "groupingRule": [
            {
                "displayName": "Organic Search",
                "expression": {
                    "andGroup": {
                        "filterExpressions": [
                            {
                                "orGroup": {
                                    "filterExpressions": [
                                        {
                                            "filter": {
                                                "fieldName": "sessionSource",
                                                "stringFilter": {
                                                    "matchType": "CONTAINS",
                                                    "value": "google",
                                                },
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                },
            }
        ],
    },
    {
        "name": "properties/123/channelGroups/1002",
        "displayName": "Custom Channels",
        "description": "My custom grouping",
        "systemDefined": False,
        "groupingRule": [],
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with channelGroups methods."""
    mock_client = MagicMock()
    cg = mock_client.properties.return_value.channelGroups.return_value

    cg.list.return_value.execute.return_value = {
        "channelGroups": SAMPLE_GROUPS,
    }
    cg.get.return_value.execute.return_value = SAMPLE_GROUPS[0]
    cg.create.return_value.execute.return_value = SAMPLE_GROUPS[1]
    cg.patch.return_value.execute.return_value = SAMPLE_GROUPS[1]
    cg.delete.return_value.execute.return_value = {}

    return mock_client


class TestChannelGroupsList:
    def test_list_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["channel-groups", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "Default Channel" in result.output
        assert "Custom Channels" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.list.return_value.execute.return_value = {"channelGroups": []}

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["channel-groups", "list", "-p", "123"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["channel-groups", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["channel-groups", "list", "-p", "123"])

        assert result.exit_code == 2

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["channel-groups", "list"])
        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["channel-groups", "list"])

        assert result.exit_code == 0
        assert "Default Channel" in result.output


class TestChannelGroupsGet:
    def test_get_table(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "get", "-p", "123", "--channel-group-id", "1001"],
            )

        assert result.exit_code == 0
        assert "Default Channel" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "get", "-p", "123", "-g", "1001", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"groupingRule"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "get", "-p", "123", "-g", "missing"],
            )

        assert result.exit_code == 3


class TestChannelGroupsCreate:
    def test_create_basic(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {
            "displayName": "Custom Channels",
            "description": "My custom grouping",
            "groupingRule": [
                {
                    "displayName": "Paid Search",
                    "expression": {
                        "andGroup": {
                            "filterExpressions": [
                                {
                                    "orGroup": {
                                        "filterExpressions": [
                                            {
                                                "filter": {
                                                    "fieldName": "sessionCampaignName",
                                                    "stringFilter": {
                                                        "matchType": "CONTAINS",
                                                        "value": "paid",
                                                    },
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    },
                }
            ],
        }
        config_file = tmp_path / "channel_group.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "create", "-p", "123", "--config", str(config_file)],
            )

        assert result.exit_code == 0
        cg = mock_client.properties.return_value.channelGroups.return_value
        body = cg.create.call_args[1]["body"]
        assert body["displayName"] == "Custom Channels"
        assert len(body["groupingRule"]) == 1

    def test_create_missing_config_file(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "create", "-p", "123", "--config", "/nonexistent.json"],
            )

        assert result.exit_code != 0

    def test_create_invalid_json(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ not valid }")

        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "create", "-p", "123", "--config", str(config_file)],
            )

        assert result.exit_code != 0

    def test_create_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "channel_group.json"
        config_file.write_text(json.dumps({"displayName": "Test"}))

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "create", "-p", "123", "--config", str(config_file)],
            )

        assert result.exit_code == 3


class TestChannelGroupsUpdate:
    def test_update_display_name(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {"displayName": "Renamed Channels", "description": "Updated"}
        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "channel-groups", "update",
                    "-p", "123",
                    "-g", "1002",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        cg = mock_client.properties.return_value.channelGroups.return_value
        call_args = cg.patch.call_args
        assert call_args[1]["body"]["displayName"] == "Renamed Channels"
        mask = call_args[1]["updateMask"]
        assert "displayName" in mask
        assert "description" in mask

    def test_update_grouping_rules(self, tmp_path):
        mock_client = _mock_admin_alpha_client()
        config = {
            "groupingRule": [
                {"displayName": "Direct", "expression": {}}
            ]
        }
        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps(config))

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "channel-groups", "update",
                    "-p", "123",
                    "-g", "1002",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 0
        cg = mock_client.properties.return_value.channelGroups.return_value
        call_args = cg.patch.call_args
        assert call_args[1]["updateMask"] == "groupingRule"
        assert len(call_args[1]["body"]["groupingRule"]) == 1

    def test_update_empty_config(self, tmp_path):
        config_file = tmp_path / "empty.json"
        config_file.write_text("{}")

        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "channel-groups", "update",
                    "-p", "123",
                    "-g", "1002",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code != 0

    def test_update_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        config_file = tmp_path / "update.json"
        config_file.write_text(json.dumps({"displayName": "Fail"}))

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "channel-groups", "update",
                    "-p", "123",
                    "-g", "1002",
                    "--config", str(config_file),
                ],
            )

        assert result.exit_code == 3


class TestChannelGroupsDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "delete", "-p", "123", "-g", "1002", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.delete.assert_called_once()

    def test_delete_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.channel_groups.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.channel_groups.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["channel-groups", "delete", "-p", "123", "-g", "1002"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.channel_groups.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.channel_groups.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["channel-groups", "delete", "-p", "123", "-g", "1002"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.delete.assert_not_called()

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        cg = mock_client.properties.return_value.channelGroups.return_value
        cg.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.channel_groups.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["channel-groups", "delete", "-p", "123", "-g", "1002", "--yes"],
            )

        assert result.exit_code == 3
