"""Tests for Measurement Protocol secrets commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_MP_SECRETS = [
    {
        "name": "properties/123/dataStreams/456/measurementProtocolSecrets/789",
        "displayName": "Web Secret",
        "secretValue": "abc123secret",
    },
    {
        "name": "properties/123/dataStreams/456/measurementProtocolSecrets/790",
        "displayName": "Server Secret",
        "secretValue": "def456secret",
    },
]


def _mock_admin_client():
    """Create a mock Admin API client with measurementProtocolSecrets methods."""
    mock_client = MagicMock()
    mps = (
        mock_client.properties.return_value
        .dataStreams.return_value
        .measurementProtocolSecrets.return_value
    )

    mps.list.return_value.execute.return_value = {
        "measurementProtocolSecrets": SAMPLE_MP_SECRETS,
    }
    mps.get.return_value.execute.return_value = SAMPLE_MP_SECRETS[0]
    mps.create.return_value.execute.return_value = SAMPLE_MP_SECRETS[0]
    mps.patch.return_value.execute.return_value = SAMPLE_MP_SECRETS[0]
    mps.delete.return_value.execute.return_value = {}

    return mock_client


class TestMPSecretsList:
    def test_list_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["mp-secrets", "list", "-p", "123", "-s", "456"]
            )

        assert result.exit_code == 0
        assert "Web Secret" in result.output
        assert "Server Secret" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["mp-secrets", "list", "-p", "123", "-s", "456", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"secretValue"' in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client()
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        mps.list.return_value.execute.return_value = {"measurementProtocolSecrets": []}

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["mp-secrets", "list", "-p", "123", "-s", "456"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        mps.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["mp-secrets", "list", "-p", "123", "-s", "456"]
            )

        assert result.exit_code == 2

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["mp-secrets", "list", "-s", "456"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_missing_stream_id(self):
        result = runner.invoke(app, ["mp-secrets", "list", "-p", "123"])

        assert result.exit_code != 0

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["mp-secrets", "list", "-s", "456"])

        assert result.exit_code == 0
        assert "Web Secret" in result.output


class TestMPSecretsGet:
    def test_get_details(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["mp-secrets", "get", "-p", "123", "-s", "456", "--secret-id", "789"],
            )

        assert result.exit_code == 0
        assert "Web Secret" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["mp-secrets", "get", "-p", "123", "-s", "456", "--secret-id", "789", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"secretValue"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        mps.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["mp-secrets", "get", "-p", "123", "-s", "456", "--secret-id", "999"],
            )

        assert result.exit_code == 3


class TestMPSecretsCreate:
    def test_create_secret(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "mp-secrets", "create",
                    "-p", "123",
                    "-s", "456",
                    "--display-name", "Web Secret",
                ],
            )

        assert result.exit_code == 0
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        body = mps.create.call_args[1]["body"]
        assert body["displayName"] == "Web Secret"

    def test_create_requires_display_name(self):
        result = runner.invoke(
            app,
            ["mp-secrets", "create", "-p", "123", "-s", "456"],
        )

        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        mps.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "mp-secrets", "create",
                    "-p", "123",
                    "-s", "456",
                    "--display-name", "Test",
                ],
            )

        assert result.exit_code == 3


class TestMPSecretsUpdate:
    def test_update_display_name(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "mp-secrets", "update",
                    "-p", "123",
                    "-s", "456",
                    "--secret-id", "789",
                    "--display-name", "Updated Name",
                ],
            )

        assert result.exit_code == 0
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        call_args = mps.patch.call_args
        assert call_args[1]["updateMask"] == "displayName"
        assert call_args[1]["body"]["displayName"] == "Updated Name"

    def test_update_no_fields(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["mp-secrets", "update", "-p", "123", "-s", "456", "--secret-id", "789"],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        mps.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "mp-secrets", "update",
                    "-p", "123",
                    "-s", "456",
                    "--secret-id", "789",
                    "--display-name", "Test",
                ],
            )

        assert result.exit_code == 3


class TestMPSecretsDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["mp-secrets", "delete", "-p", "123", "-s", "456", "--secret-id", "789", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        mps.delete.assert_called_once()

    def test_delete_confirms(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.mp_secrets.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.mp_secrets.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["mp-secrets", "delete", "-p", "123", "-s", "456", "--secret-id", "789"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.mp_secrets.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.mp_secrets.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["mp-secrets", "delete", "-p", "123", "-s", "456", "--secret-id", "789"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        mps = (
            mock_client.properties.return_value
            .dataStreams.return_value
            .measurementProtocolSecrets.return_value
        )
        mps.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.mp_secrets.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["mp-secrets", "delete", "-p", "123", "-s", "456", "--secret-id", "789", "--yes"],
            )

        assert result.exit_code == 3
