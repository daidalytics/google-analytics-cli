"""Tests for properties commands (list, get, create, delete)."""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _mock_admin_client(properties=None, property_detail=None):
    """Create a mock Admin API client with properties methods."""
    mock_client = MagicMock()

    mock_client.properties.return_value.list.return_value.execute.return_value = {
        "properties": properties or [],
    }
    mock_client.properties.return_value.get.return_value.execute.return_value = (
        property_detail or {}
    )
    mock_client.properties.return_value.create.return_value.execute.return_value = (
        property_detail or {}
    )
    mock_client.properties.return_value.delete.return_value.execute.return_value = {}
    mock_client.properties.return_value.patch.return_value.execute.return_value = (
        property_detail or {}
    )

    return mock_client


SAMPLE_PROPERTIES = [
    {
        "name": "properties/111111",
        "displayName": "My Website",
        "timeZone": "America/New_York",
        "currencyCode": "USD",
    },
    {
        "name": "properties/222222",
        "displayName": "My App",
        "timeZone": "Europe/London",
        "currencyCode": "GBP",
    },
]


class TestPropertiesList:
    def test_list_with_flag(self):
        mock_client = _mock_admin_client(properties=SAMPLE_PROPERTIES)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "list", "--account-id", "123456"])

        assert result.exit_code == 0
        assert "My Website" in result.output
        assert "My App" in result.output

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_account_id="123456"))
        mock_client = _mock_admin_client(properties=SAMPLE_PROPERTIES)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "list"])

        assert result.exit_code == 0
        assert "My Website" in result.output

    def test_list_missing_account_id(self):
        result = runner.invoke(app, ["properties", "list"])

        assert result.exit_code != 0
        assert "account-id" in result.output.lower()

    def test_list_json_output(self):
        mock_client = _mock_admin_client(properties=SAMPLE_PROPERTIES)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "list", "-a", "123", "-o", "json"])

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client(properties=[])

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "list", "-a", "123"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_passes_correct_filter(self):
        mock_client = _mock_admin_client(properties=[])

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            runner.invoke(app, ["properties", "list", "-a", "99999"])

        # Verify the filter was passed correctly
        list_call = mock_client.properties.return_value.list.call_args
        assert "parent:accounts/99999" in str(list_call)


class TestPropertiesGet:
    def test_get_with_flag(self):
        detail = {
            "name": "properties/111111",
            "displayName": "My Website",
            "timeZone": "America/New_York",
        }
        mock_client = _mock_admin_client(property_detail=detail)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "get", "--property-id", "111111"])

        assert result.exit_code == 0
        assert "My Website" in result.output

    def test_get_uses_config_default(self):
        save_config(UserConfig(default_property_id="111111"))
        detail = {"name": "properties/111111", "displayName": "My Website"}
        mock_client = _mock_admin_client(property_detail=detail)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "get"])

        assert result.exit_code == 0
        assert "My Website" in result.output

    def test_get_missing_property_id(self):
        result = runner.invoke(app, ["properties", "get"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()


class TestPropertiesCreate:
    def test_create_property(self):
        created = {
            "name": "properties/333333",
            "displayName": "New Prop",
            "timeZone": "America/Los_Angeles",
            "currencyCode": "USD",
        }
        mock_client = _mock_admin_client(property_detail=created)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "properties",
                    "create",
                    "--name",
                    "New Prop",
                    "--account-id",
                    "123",
                ],
            )

        assert result.exit_code == 0
        assert "New Prop" in result.output
        mock_client.properties.return_value.create.assert_called_once()

    def test_create_with_all_options(self):
        created = {
            "name": "properties/333333",
            "displayName": "Euro Site",
            "timeZone": "Europe/Berlin",
            "currencyCode": "EUR",
        }
        mock_client = _mock_admin_client(property_detail=created)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "properties",
                    "create",
                    "--name",
                    "Euro Site",
                    "-a",
                    "123",
                    "--timezone",
                    "Europe/Berlin",
                    "--currency",
                    "EUR",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.create.call_args
        body = call_args[1]["body"] if "body" in call_args[1] else call_args[0][0]
        assert body["timeZone"] == "Europe/Berlin"
        assert body["currencyCode"] == "EUR"

    def test_create_missing_name(self):
        result = runner.invoke(app, ["properties", "create", "--account-id", "123"])

        assert result.exit_code != 0

    def test_create_missing_account_id(self):
        result = runner.invoke(app, ["properties", "create", "--name", "Test"])

        assert result.exit_code != 0
        assert "account-id" in result.output.lower()


class TestPropertiesDelete:
    def test_delete_with_confirmation(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.properties.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.properties.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True

            result = runner.invoke(app, ["properties", "delete", "--property-id", "111111"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        mock_client.properties.return_value.delete.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.properties.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.properties.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False

            result = runner.invoke(app, ["properties", "delete", "--property-id", "111111"])

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        mock_client.properties.return_value.delete.assert_not_called()

    def test_delete_skip_confirmation(self):
        mock_client = _mock_admin_client()

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "delete", "-p", "111111", "--yes"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_missing_property_id(self):
        result = runner.invoke(app, ["properties", "delete"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()


class TestPropertiesUpdate:
    def test_update_name(self):
        updated = {
            "name": "properties/111111",
            "displayName": "Updated Name",
            "timeZone": "America/New_York",
            "currencyCode": "USD",
        }
        mock_client = _mock_admin_client(property_detail=updated)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["properties", "update", "-p", "111111", "--name", "Updated Name"],
            )

        assert result.exit_code == 0
        assert "Updated Name" in result.output
        call_args = mock_client.properties.return_value.patch.call_args
        assert call_args[1]["updateMask"] == "displayName"
        assert call_args[1]["body"]["displayName"] == "Updated Name"

    def test_update_timezone(self):
        updated = {"name": "properties/111111", "timeZone": "Europe/Berlin"}
        mock_client = _mock_admin_client(property_detail=updated)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["properties", "update", "-p", "111111", "--timezone", "Europe/Berlin"],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.patch.call_args
        assert call_args[1]["updateMask"] == "timeZone"

    def test_update_currency(self):
        updated = {"name": "properties/111111", "currencyCode": "EUR"}
        mock_client = _mock_admin_client(property_detail=updated)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["properties", "update", "-p", "111111", "--currency", "EUR"],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.patch.call_args
        assert call_args[1]["updateMask"] == "currencyCode"

    def test_update_multiple_fields(self):
        updated = {
            "name": "properties/111111",
            "displayName": "New",
            "timeZone": "Europe/London",
        }
        mock_client = _mock_admin_client(property_detail=updated)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "properties",
                    "update",
                    "-p",
                    "111111",
                    "--name",
                    "New",
                    "--timezone",
                    "Europe/London",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.properties.return_value.patch.call_args
        mask = call_args[1]["updateMask"]
        assert "displayName" in mask
        assert "timeZone" in mask

    def test_update_no_fields(self):
        result = runner.invoke(app, ["properties", "update", "-p", "111111"])

        assert result.exit_code != 0

    def test_update_json_output(self):
        updated = {"name": "properties/111111", "displayName": "Test"}
        mock_client = _mock_admin_client(property_detail=updated)

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["properties", "update", "-p", "111111", "--name", "Test", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_update_api_error(self):
        mock_client = MagicMock()
        mock_client.properties.return_value.patch.return_value.execute.side_effect = Exception(
            "API error"
        )

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["properties", "update", "-p", "111111", "--name", "Fail"],
            )

        assert result.exit_code != 0


class TestPropertiesAcknowledgeUdc:
    def test_acknowledge_with_confirmation(self):
        mock_client = _mock_admin_client()
        ack = mock_client.properties.return_value.acknowledgeUserDataCollection
        ack.return_value.execute.return_value = {}

        with (
            patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client),
            patch("ga_cli.commands.properties.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app, ["properties", "acknowledge-udc", "--property-id", "111111"]
            )

        assert result.exit_code == 0
        assert "acknowledged" in result.output.lower()
        mock_client.properties.return_value.acknowledgeUserDataCollection.assert_called_once()

    def test_acknowledge_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client),
            patch("ga_cli.commands.properties.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app, ["properties", "acknowledge-udc", "--property-id", "111111"]
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        mock_client.properties.return_value.acknowledgeUserDataCollection.assert_not_called()

    def test_acknowledge_skip_confirmation(self):
        mock_client = _mock_admin_client()
        ack = mock_client.properties.return_value.acknowledgeUserDataCollection
        ack.return_value.execute.return_value = {}

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "acknowledge-udc", "-p", "111111", "--yes"])

        assert result.exit_code == 0
        assert "acknowledged" in result.output.lower()
        call_args = mock_client.properties.return_value.acknowledgeUserDataCollection.call_args
        assert call_args[1]["property"] == "properties/111111"
        assert "acknowledgement" in call_args[1]["body"]

    def test_acknowledge_requires_property_id(self):
        result = runner.invoke(app, ["properties", "acknowledge-udc"])

        assert result.exit_code != 0
        assert "property-id" in _strip_ansi(result.output).lower()

    def test_acknowledge_api_error(self):
        mock_client = MagicMock()
        ack = mock_client.properties.return_value.acknowledgeUserDataCollection
        ack.return_value.execute.side_effect = Exception("Permission denied")

        with patch("ga_cli.commands.properties.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "acknowledge-udc", "-p", "111111", "--yes"])

        assert result.exit_code == 3
        assert "Permission denied" in result.output


SAMPLE_QUOTAS_RESPONSE = {
    "corePropertyQuota": {
        "tokensPerDay": {"consumed": 500, "remaining": 24500},
        "tokensPerHour": {"consumed": 50, "remaining": 4950},
        "concurrentRequests": {"consumed": 2, "remaining": 8},
        "serverErrorsPerProjectPerHour": {"consumed": 0, "remaining": 10},
        "potentiallyThresholdedRequestsPerHour": {"consumed": 1, "remaining": 119},
    },
}


def _mock_data_alpha_client(quotas_response=None):
    """Create a mock Data Alpha API client for quotas."""
    mock_client = MagicMock()
    snapshot = mock_client.properties.return_value.getPropertyQuotasSnapshot
    snapshot.return_value.execute.return_value = (
        SAMPLE_QUOTAS_RESPONSE if quotas_response is None else quotas_response
    )
    return mock_client


class TestPropertiesQuotas:
    def test_quotas_table_output(self):
        mock_client = _mock_data_alpha_client()

        with patch("ga_cli.commands.properties.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "quotas", "-p", "111111"])

        assert result.exit_code == 0
        assert "Tokens Per Day" in result.output
        assert "Tokens Per Hour" in result.output
        assert "Concurrent Requests" in result.output
        assert "500" in result.output
        assert "24500" in result.output

    def test_quotas_json_output(self):
        mock_client = _mock_data_alpha_client()

        with patch("ga_cli.commands.properties.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "quotas", "-p", "111111", "-o", "json"])

        assert result.exit_code == 0
        assert "tokensPerDay" in result.output
        assert "500" in result.output

    def test_quotas_uses_config_default(self):
        save_config(UserConfig(default_property_id="111111"))
        mock_client = _mock_data_alpha_client()

        with patch("ga_cli.commands.properties.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "quotas"])

        assert result.exit_code == 0
        assert "Tokens Per Day" in result.output

    def test_quotas_missing_property_id(self):
        result = runner.invoke(app, ["properties", "quotas"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_quotas_api_error(self):
        mock_client = MagicMock()
        snapshot = mock_client.properties.return_value.getPropertyQuotasSnapshot
        snapshot.return_value.execute.side_effect = (
            Exception("Quota API error")
        )

        with patch("ga_cli.commands.properties.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "quotas", "-p", "111111"])

        assert result.exit_code == 3
        assert "Quota API error" in result.output

    def test_quotas_empty_response(self):
        mock_client = _mock_data_alpha_client(quotas_response={})

        with patch("ga_cli.commands.properties.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["properties", "quotas", "-p", "111111"])

        assert result.exit_code == 0
        assert "No quota data" in result.output

    def test_quotas_calls_correct_endpoint(self):
        mock_client = _mock_data_alpha_client()

        with patch("ga_cli.commands.properties.get_data_alpha_client", return_value=mock_client):
            runner.invoke(app, ["properties", "quotas", "-p", "999"])

        mock_client.properties.return_value.getPropertyQuotasSnapshot.assert_called_once_with(
            name="properties/999/propertyQuotasSnapshot"
        )
