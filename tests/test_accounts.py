"""Tests for accounts commands (list, get, update, change-history)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


def _mock_admin_client(accounts=None, account_detail=None, account_patch_result=None):
    """Create a mock Admin API client with accounts methods."""
    mock_client = MagicMock()

    # accounts().list().execute()
    mock_client.accounts.return_value.list.return_value.execute.return_value = {
        "accounts": accounts or [],
    }

    # accounts().get().execute()
    mock_client.accounts.return_value.get.return_value.execute.return_value = (
        account_detail or {}
    )

    # accounts().patch().execute()
    mock_client.accounts.return_value.patch.return_value.execute.return_value = (
        account_patch_result or {}
    )

    return mock_client


SAMPLE_ACCOUNTS = [
    {
        "name": "accounts/123456",
        "displayName": "My Account",
        "createTime": "2023-01-01T00:00:00Z",
    },
    {
        "name": "accounts/789012",
        "displayName": "Other Account",
        "createTime": "2023-06-15T00:00:00Z",
    },
]


class TestAccountsList:
    def test_list_table_output(self):
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "list"])

        assert result.exit_code == 0
        assert "My Account" in result.output
        assert "Other Account" in result.output

    def test_list_json_output(self):
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "list", "--output", "json"])

        assert result.exit_code == 0
        assert "accounts/123456" in result.output
        assert "My Account" in result.output

    def test_list_compact_output(self):
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "list", "--output", "compact"])

        assert result.exit_code == 0
        assert "accounts/123456" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client(accounts=[])

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "list"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_respects_config_output_format(self):
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with (
            patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client),
            patch("ga_cli.commands.accounts.get_effective_value") as mock_effective,
        ):
            mock_effective.return_value = "json"
            result = runner.invoke(app, ["accounts", "list"])

        assert result.exit_code == 0
        # JSON output contains raw field names with quotes
        assert '"displayName"' in result.output

    def test_list_api_error(self):
        mock_client = MagicMock()
        mock_client.accounts.return_value.list.return_value.execute.side_effect = (
            Exception("API quota exceeded")
        )

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "list"])

        assert result.exit_code == 1
        assert "API quota exceeded" in result.output

    def test_list_pagination(self):
        """Verify paginate_all is used to fetch all pages."""
        page1 = [SAMPLE_ACCOUNTS[0]]
        page2 = [SAMPLE_ACCOUNTS[1]]

        mock_client = MagicMock()
        mock_client.accounts.return_value.list.return_value.execute.side_effect = [
            {"accounts": page1, "nextPageToken": "token123"},
            {"accounts": page2},
        ]

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "list", "--output", "json"])

        assert result.exit_code == 0
        assert "My Account" in result.output
        assert "Other Account" in result.output


class TestAccountsGet:
    def test_get_account(self):
        detail = {
            "name": "accounts/123456",
            "displayName": "My Account",
            "createTime": "2023-01-01T00:00:00Z",
            "updateTime": "2024-01-01T00:00:00Z",
        }
        mock_client = _mock_admin_client(account_detail=detail)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "get", "--account-id", "123456"])

        assert result.exit_code == 0
        assert "My Account" in result.output
        mock_client.accounts.return_value.get.assert_called_once_with(
            name="accounts/123456"
        )

    def test_get_json_output(self):
        detail = {
            "name": "accounts/123456",
            "displayName": "My Account",
        }
        mock_client = _mock_admin_client(account_detail=detail)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["accounts", "get", "--account-id", "123456", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_get_requires_account_id(self):
        result = runner.invoke(app, ["accounts", "get"])

        assert result.exit_code != 0
        assert "account-id" in result.output.lower() or "missing" in result.output.lower()

    def test_get_api_error(self):
        mock_client = MagicMock()
        mock_client.accounts.return_value.get.return_value.execute.side_effect = (
            Exception("Account not found")
        )

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "get", "--account-id", "999"])

        assert result.exit_code == 1
        assert "Account not found" in result.output


class TestAccountsUpdate:
    UPDATED_ACCOUNT = {
        "name": "accounts/123456",
        "displayName": "New Name",
        "createTime": "2023-01-01T00:00:00Z",
        "updateTime": "2024-06-01T00:00:00Z",
    }

    def test_update_name_table_output(self):
        mock_client = _mock_admin_client(account_patch_result=self.UPDATED_ACCOUNT)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["accounts", "update", "--account-id", "123456", "--name", "New Name"]
            )

        assert result.exit_code == 0
        assert "New Name" in result.output
        mock_client.accounts.return_value.patch.assert_called_once_with(
            name="accounts/123456",
            body={"displayName": "New Name"},
            updateMask="displayName",
        )

    def test_update_name_json_output(self):
        mock_client = _mock_admin_client(account_patch_result=self.UPDATED_ACCOUNT)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "accounts", "update",
                    "--account-id", "123456",
                    "--name", "New Name",
                    "-o", "json",
                ],
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output
        assert "New Name" in result.output

    def test_update_requires_account_id(self):
        result = runner.invoke(app, ["accounts", "update", "--name", "New Name"])

        assert result.exit_code != 0
        assert "account-id" in result.output.lower() or "missing" in result.output.lower()

    def test_update_requires_name(self):
        result = runner.invoke(app, ["accounts", "update", "--account-id", "123456"])

        assert result.exit_code != 0
        assert "name" in result.output.lower() or "missing" in result.output.lower()

    def test_update_api_error(self):
        mock_client = MagicMock()
        mock_client.accounts.return_value.patch.return_value.execute.side_effect = (
            Exception("Permission denied")
        )

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["accounts", "update", "--account-id", "123456", "--name", "New Name"]
            )

        assert result.exit_code == 1
        assert "Permission denied" in result.output

    def test_update_respects_config_output_format(self):
        mock_client = _mock_admin_client(account_patch_result=self.UPDATED_ACCOUNT)

        with (
            patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client),
            patch("ga_cli.commands.accounts.get_effective_value") as mock_effective,
        ):
            mock_effective.return_value = "json"
            result = runner.invoke(
                app, ["accounts", "update", "--account-id", "123456", "--name", "New Name"]
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output


SAMPLE_CHANGE_HISTORY_RESPONSE = {
    "changeHistoryEvents": [
        {
            "id": "event1",
            "changeTime": "2024-01-15T10:30:00Z",
            "actorType": "USER",
            "userActorEmail": "admin@example.com",
            "changes": [
                {
                    "resource": "PROPERTY",
                    "action": "UPDATED",
                    "resourceAfterChange": {
                        "property": {
                            "name": "properties/123",
                            "displayName": "My Site",
                        }
                    },
                }
            ],
        },
        {
            "id": "event2",
            "changeTime": "2024-01-14T08:00:00Z",
            "actorType": "USER",
            "userActorEmail": "dev@example.com",
            "changes": [
                {
                    "resource": "DATA_STREAM",
                    "action": "CREATED",
                    "resourceAfterChange": {
                        "dataStream": {
                            "name": "properties/123/dataStreams/456",
                            "displayName": "Web Stream",
                        }
                    },
                }
            ],
        },
        {
            "id": "event3",
            "changeTime": "2024-01-13T15:00:00Z",
            "actorType": "SYSTEM",
            "changes": [
                {
                    "resource": "PROPERTY",
                    "action": "DELETED",
                    "resourceBeforeChange": {
                        "property": {
                            "name": "properties/789",
                            "displayName": "Old Site",
                        }
                    },
                }
            ],
        },
    ]
}


def _mock_change_history_client(response=None):
    """Create a mock Admin API client with searchChangeHistoryEvents."""
    mock_client = MagicMock()
    mock_search = mock_client.accounts.return_value.searchChangeHistoryEvents
    mock_search.return_value.execute.return_value = (
        response if response is not None else SAMPLE_CHANGE_HISTORY_RESPONSE
    )
    return mock_client


class TestChangeHistory:
    def test_list_changes_table(self):
        mock_client = _mock_change_history_client()

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["accounts", "change-history", "--account-id", "123456"]
            )

        assert result.exit_code == 0
        assert "admin@example" in result.output
        assert "dev@example" in result.output
        assert "SYSTEM" in result.output

    def test_filter_by_property(self):
        mock_client = _mock_change_history_client()

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["accounts", "change-history", "--account-id", "123456", "--property-id", "123"],
            )

        assert result.exit_code == 0
        call_args = mock_client.accounts.return_value.searchChangeHistoryEvents.call_args
        body = call_args[1]["body"]
        assert body["property"] == "properties/123"

    def test_filter_by_action(self):
        mock_client = _mock_change_history_client()

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["accounts", "change-history", "--account-id", "123456", "--action", "CREATED"],
            )

        assert result.exit_code == 0
        call_args = mock_client.accounts.return_value.searchChangeHistoryEvents.call_args
        body = call_args[1]["body"]
        assert body["action"] == ["CREATED"]

    def test_filter_by_resource_type(self):
        mock_client = _mock_change_history_client()

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "accounts", "change-history",
                    "--account-id", "123456",
                    "--resource-type", "PROPERTY",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.accounts.return_value.searchChangeHistoryEvents.call_args
        body = call_args[1]["body"]
        assert body["resourceType"] == ["PROPERTY"]

    def test_json_output(self):
        mock_client = _mock_change_history_client()

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["accounts", "change-history", "--account-id", "123456", "-o", "json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]["id"] == "event1"

    def test_empty_history(self):
        mock_client = _mock_change_history_client(response={"changeHistoryEvents": []})

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["accounts", "change-history", "--account-id", "123456"]
            )

        assert result.exit_code == 0
        assert "No changes found" in result.output

    def test_api_error(self):
        mock_client = MagicMock()
        mock_search = mock_client.accounts.return_value.searchChangeHistoryEvents
        mock_search.return_value.execute.side_effect = (
            Exception("Permission denied")
        )

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["accounts", "change-history", "--account-id", "123456"]
            )

        assert result.exit_code == 1
        assert "Permission denied" in result.output

    def test_uses_config_account_id(self):
        mock_client = _mock_change_history_client()

        with (
            patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client),
            patch("ga_cli.commands.accounts.get_effective_value") as mock_effective,
        ):
            mock_effective.side_effect = (
                lambda val, key: "999" if key == "default_account_id" else val
            )
            result = runner.invoke(app, ["accounts", "change-history"])

        assert result.exit_code == 0
        call_args = mock_client.accounts.return_value.searchChangeHistoryEvents.call_args
        assert call_args[1]["account"] == "accounts/999"
