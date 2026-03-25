"""Tests for properties commands (list, get, create, delete)."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()


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

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["properties", "list", "--account-id", "123456"]
            )

        assert result.exit_code == 0
        assert "My Website" in result.output
        assert "My App" in result.output

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_account_id="123456"))
        mock_client = _mock_admin_client(properties=SAMPLE_PROPERTIES)

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
            result = runner.invoke(app, ["properties", "list"])

        assert result.exit_code == 0
        assert "My Website" in result.output

    def test_list_missing_account_id(self):
        result = runner.invoke(app, ["properties", "list"])

        assert result.exit_code != 0
        assert "account-id" in result.output.lower()

    def test_list_json_output(self):
        mock_client = _mock_admin_client(properties=SAMPLE_PROPERTIES)

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["properties", "list", "-a", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client(properties=[])

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
            result = runner.invoke(app, ["properties", "list", "-a", "123"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_passes_correct_filter(self):
        mock_client = _mock_admin_client(properties=[])

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
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

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["properties", "get", "--property-id", "111111"]
            )

        assert result.exit_code == 0
        assert "My Website" in result.output

    def test_get_uses_config_default(self):
        save_config(UserConfig(default_property_id="111111"))
        detail = {"name": "properties/111111", "displayName": "My Website"}
        mock_client = _mock_admin_client(property_detail=detail)

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
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

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
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

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
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
        result = runner.invoke(
            app, ["properties", "create", "--account-id", "123"]
        )

        assert result.exit_code != 0

    def test_create_missing_account_id(self):
        result = runner.invoke(
            app, ["properties", "create", "--name", "Test"]
        )

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

            result = runner.invoke(
                app, ["properties", "delete", "--property-id", "111111"]
            )

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

            result = runner.invoke(
                app, ["properties", "delete", "--property-id", "111111"]
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        mock_client.properties.return_value.delete.assert_not_called()

    def test_delete_skip_confirmation(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.properties.get_admin_client", return_value=mock_client
        ):
            result = runner.invoke(
                app, ["properties", "delete", "-p", "111111", "--yes"]
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_missing_property_id(self):
        result = runner.invoke(app, ["properties", "delete"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()
