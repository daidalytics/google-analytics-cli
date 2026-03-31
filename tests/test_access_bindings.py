"""Tests for access binding commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_BINDINGS = [
    {
        "name": "properties/123/accessBindings/b1",
        "user": "alice@example.com",
        "roles": ["predefinedRoles/editor", "predefinedRoles/no-cost-data"],
    },
    {
        "name": "properties/123/accessBindings/b2",
        "user": "bob@example.com",
        "roles": ["predefinedRoles/viewer"],
    },
]

SAMPLE_ACCOUNT_BINDINGS = [
    {
        "name": "accounts/999/accessBindings/b1",
        "user": "carol@example.com",
        "roles": ["predefinedRoles/admin"],
    },
]


def _mock_admin_alpha_client():
    """Create a mock Admin API alpha client with accessBindings methods."""
    mock_client = MagicMock()

    # Property-level accessBindings
    prop_ab = (
        mock_client.properties.return_value
        .accessBindings.return_value
    )
    prop_ab.list.return_value.execute.return_value = {
        "accessBindings": SAMPLE_BINDINGS,
    }
    prop_ab.get.return_value.execute.return_value = SAMPLE_BINDINGS[0]
    prop_ab.create.return_value.execute.return_value = SAMPLE_BINDINGS[0]
    prop_ab.patch.return_value.execute.return_value = SAMPLE_BINDINGS[0]
    prop_ab.delete.return_value.execute.return_value = {}

    # Account-level accessBindings
    acct_ab = (
        mock_client.accounts.return_value
        .accessBindings.return_value
    )
    acct_ab.list.return_value.execute.return_value = {
        "accessBindings": SAMPLE_ACCOUNT_BINDINGS,
    }
    acct_ab.get.return_value.execute.return_value = SAMPLE_ACCOUNT_BINDINGS[0]
    acct_ab.create.return_value.execute.return_value = SAMPLE_ACCOUNT_BINDINGS[0]
    acct_ab.patch.return_value.execute.return_value = SAMPLE_ACCOUNT_BINDINGS[0]
    acct_ab.delete.return_value.execute.return_value = {}

    return mock_client


class TestAccessBindingsList:
    def test_list_property_level(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "list", "-p", "123"],
            )

        assert result.exit_code == 0
        assert "alice@example.com" in result.output
        assert "bob@example.com" in result.output

    def test_list_account_level(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "list", "-a", "999"],
            )

        assert result.exit_code == 0
        assert "carol@example.com" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "list", "-p", "123", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"user"' in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_alpha_client()
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        prop_ab.list.return_value.execute.return_value = {"accessBindings": []}

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "list", "-p", "123"],
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_both_parents_error(self):
        result = runner.invoke(
            app,
            ["access-bindings", "list", "-a", "999", "-p", "123"],
        )
        assert result.exit_code != 0
        assert "not both" in result.output.lower()

    def test_list_neither_parent_error(self):
        result = runner.invoke(
            app,
            ["access-bindings", "list"],
        )
        assert result.exit_code != 0

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "list"],
            )

        assert result.exit_code == 0
        assert "alice@example.com" in result.output

    def test_list_roles_display_stripped(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "list", "-p", "123"],
            )

        assert result.exit_code == 0
        # Roles should be displayed without predefinedRoles/ prefix
        assert "editor" in result.output
        assert "predefinedRoles/" not in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        prop_ab.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "list", "-p", "123"],
            )

        assert result.exit_code == 1


class TestAccessBindingsGet:
    def test_get_property_level(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "get", "-p", "123", "-b", "b1"],
            )

        assert result.exit_code == 0
        assert "alice@example.com" in result.output

    def test_get_account_level(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "get", "-a", "999", "-b", "b1"],
            )

        assert result.exit_code == 0
        assert "carol@example.com" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "get", "-p", "123", "-b", "b1", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"roles"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        prop_ab.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "get", "-p", "123", "-b", "missing"],
            )

        assert result.exit_code == 1


class TestAccessBindingsCreate:
    def test_create_property_level(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "access-bindings", "create",
                    "-p", "123",
                    "--user", "alice@example.com",
                    "--roles", "editor,no-cost-data",
                ],
            )

        assert result.exit_code == 0
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        body = prop_ab.create.call_args[1]["body"]
        assert body["user"] == "alice@example.com"
        assert "predefinedRoles/editor" in body["roles"]
        assert "predefinedRoles/no-cost-data" in body["roles"]

    def test_create_account_level(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "access-bindings", "create",
                    "-a", "999",
                    "--user", "carol@example.com",
                    "--roles", "admin",
                ],
            )

        assert result.exit_code == 0
        acct_ab = (
            mock_client.accounts.return_value
            .accessBindings.return_value
        )
        body = acct_ab.create.call_args[1]["body"]
        assert body["user"] == "carol@example.com"
        assert "predefinedRoles/admin" in body["roles"]

    def test_create_full_role_name(self):
        """Roles with predefinedRoles/ prefix should pass through unchanged."""
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "access-bindings", "create",
                    "-p", "123",
                    "--user", "alice@example.com",
                    "--roles", "predefinedRoles/viewer",
                ],
            )

        assert result.exit_code == 0
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        body = prop_ab.create.call_args[1]["body"]
        assert body["roles"] == ["predefinedRoles/viewer"]

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        prop_ab.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "access-bindings", "create",
                    "-p", "123",
                    "--user", "alice@example.com",
                    "--roles", "viewer",
                ],
            )

        assert result.exit_code == 1


class TestAccessBindingsUpdate:
    def test_update_roles(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "access-bindings", "update",
                    "-p", "123", "-b", "b1",
                    "--roles", "viewer,no-revenue-data",
                ],
            )

        assert result.exit_code == 0
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        call_args = prop_ab.patch.call_args[1]
        assert call_args["name"] == "properties/123/accessBindings/b1"
        assert "predefinedRoles/viewer" in call_args["body"]["roles"]
        assert "predefinedRoles/no-revenue-data" in call_args["body"]["roles"]

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        prop_ab.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "access-bindings", "update",
                    "-p", "123", "-b", "b1",
                    "--roles", "viewer",
                ],
            )

        assert result.exit_code == 1


class TestAccessBindingsDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_alpha_client()

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "delete", "-p", "123", "-b", "b1", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_prompts_without_yes(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.access_bindings.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.access_bindings.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["access-bindings", "delete", "-p", "123", "-b", "b1"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_alpha_client()

        with (
            patch(
                "ga_cli.commands.access_bindings.get_admin_alpha_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.access_bindings.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["access-bindings", "delete", "-p", "123", "-b", "b1"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        prop_ab.delete.assert_not_called()

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_alpha_client()
        prop_ab = (
            mock_client.properties.return_value
            .accessBindings.return_value
        )
        prop_ab.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.access_bindings.get_admin_alpha_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["access-bindings", "delete", "-p", "123", "-b", "b1", "--yes"],
            )

        assert result.exit_code == 1
