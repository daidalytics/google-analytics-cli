"""Tests for Firebase links commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_FIREBASE_LINKS = [
    {
        "name": "properties/123/firebaseLinks/abc123",
        "project": "projects/my-firebase-project",
        "createTime": "2024-01-15T10:00:00Z",
    },
]


def _mock_admin_client():
    """Create a mock Admin API client with firebaseLinks methods."""
    mock_client = MagicMock()
    fl = mock_client.properties.return_value.firebaseLinks.return_value

    fl.list.return_value.execute.return_value = {
        "firebaseLinks": SAMPLE_FIREBASE_LINKS,
    }
    fl.create.return_value.execute.return_value = SAMPLE_FIREBASE_LINKS[0]
    fl.delete.return_value.execute.return_value = {}

    return mock_client


class TestFirebaseLinksList:
    def test_list_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["firebase-links", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "firebaseLinks" in result.output or "firebase" in result.output.lower()

    def test_list_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["firebase-links", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"project"' in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client()
        fl = mock_client.properties.return_value.firebaseLinks.return_value
        fl.list.return_value.execute.return_value = {"firebaseLinks": []}

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["firebase-links", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        fl = mock_client.properties.return_value.firebaseLinks.return_value
        fl.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["firebase-links", "list", "-p", "123"]
            )

        assert result.exit_code == 2

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["firebase-links", "list"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["firebase-links", "list"])

        assert result.exit_code == 0
        assert "firebaseLinks" in result.output or "firebase" in result.output.lower()


class TestFirebaseLinksCreate:
    def test_create_link(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "firebase-links", "create",
                    "-p", "123",
                    "--project", "projects/my-firebase-project",
                ],
            )

        assert result.exit_code == 0
        fl = mock_client.properties.return_value.firebaseLinks.return_value
        body = fl.create.call_args[1]["body"]
        assert body["project"] == "projects/my-firebase-project"

    def test_create_requires_project(self):
        result = runner.invoke(
            app,
            ["firebase-links", "create", "-p", "123"],
        )

        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        fl = mock_client.properties.return_value.firebaseLinks.return_value
        fl.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "firebase-links", "create",
                    "-p", "123",
                    "--project", "projects/my-firebase-project",
                ],
            )

        assert result.exit_code == 3


class TestFirebaseLinksDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["firebase-links", "delete", "-p", "123", "--link-id", "abc123", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        fl = mock_client.properties.return_value.firebaseLinks.return_value
        fl.delete.assert_called_once()

    def test_delete_confirms(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.firebase_links.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.firebase_links.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["firebase-links", "delete", "-p", "123", "--link-id", "abc123"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.firebase_links.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.firebase_links.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["firebase-links", "delete", "-p", "123", "--link-id", "abc123"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        fl = mock_client.properties.return_value.firebaseLinks.return_value
        fl.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.firebase_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["firebase-links", "delete", "-p", "123", "--link-id", "abc123", "--yes"],
            )

        assert result.exit_code == 3
