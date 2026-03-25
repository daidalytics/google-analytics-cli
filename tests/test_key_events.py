"""Tests for key events commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_KEY_EVENTS = [
    {
        "name": "properties/123/keyEvents/1",
        "eventName": "purchase",
        "createTime": "2024-01-15T10:00:00Z",
        "deletable": True,
        "custom": True,
        "countingMethod": "ONCE_PER_EVENT",
    },
    {
        "name": "properties/123/keyEvents/2",
        "eventName": "sign_up",
        "createTime": "2024-02-01T08:30:00Z",
        "deletable": True,
        "custom": True,
        "countingMethod": "ONCE_PER_SESSION",
    },
    {
        "name": "properties/123/keyEvents/3",
        "eventName": "first_visit",
        "createTime": "2024-01-01T00:00:00Z",
        "deletable": False,
        "custom": False,
        "countingMethod": "ONCE_PER_EVENT",
    },
]


def _mock_admin_client():
    """Create a mock Admin API client with keyEvents methods."""
    mock_client = MagicMock()
    ke = mock_client.properties.return_value.keyEvents.return_value

    ke.list.return_value.execute.return_value = {
        "keyEvents": SAMPLE_KEY_EVENTS,
    }
    ke.get.return_value.execute.return_value = SAMPLE_KEY_EVENTS[0]
    ke.create.return_value.execute.return_value = SAMPLE_KEY_EVENTS[0]
    ke.patch.return_value.execute.return_value = SAMPLE_KEY_EVENTS[0]
    ke.delete.return_value.execute.return_value = {}

    return mock_client


class TestKeyEventsList:
    def test_list_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["key-events", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "purchase" in result.output
        assert "sign_up" in result.output
        assert "first_visit" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client()
        ke = mock_client.properties.return_value.keyEvents.return_value
        ke.list.return_value.execute.return_value = {"keyEvents": []}

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["key-events", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["key-events", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"eventName"' in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        ke = mock_client.properties.return_value.keyEvents.return_value
        ke.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["key-events", "list", "-p", "123"]
            )

        assert result.exit_code == 1

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["key-events", "list"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["key-events", "list"])

        assert result.exit_code == 0
        assert "purchase" in result.output


class TestKeyEventsGet:
    def test_get_details(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["key-events", "get", "-p", "123", "--key-event-id", "1"],
            )

        assert result.exit_code == 0
        assert "purchase" in result.output

    def test_get_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["key-events", "get", "-p", "123", "-k", "1", "-o", "json"],
            )

        assert result.exit_code == 0
        assert '"countingMethod"' in result.output

    def test_get_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        ke = mock_client.properties.return_value.keyEvents.return_value
        ke.get.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b'{"error": {"message": "Not found"}}'
        )

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["key-events", "get", "-p", "123", "-k", "999"],
            )

        assert result.exit_code == 1


class TestKeyEventsCreate:
    def test_create_once_per_event(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "key-events", "create",
                    "-p", "123",
                    "--event-name", "purchase",
                ],
            )

        assert result.exit_code == 0
        ke = mock_client.properties.return_value.keyEvents.return_value
        body = ke.create.call_args[1]["body"]
        assert body["countingMethod"] == "ONCE_PER_EVENT"

    def test_create_once_per_session(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "key-events", "create",
                    "-p", "123",
                    "--event-name", "sign_up",
                    "--counting-method", "ONCE_PER_SESSION",
                ],
            )

        assert result.exit_code == 0
        ke = mock_client.properties.return_value.keyEvents.return_value
        body = ke.create.call_args[1]["body"]
        assert body["countingMethod"] == "ONCE_PER_SESSION"

    def test_create_invalid_counting_method(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "key-events", "create",
                    "-p", "123",
                    "--event-name", "test",
                    "--counting-method", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_create_requires_event_name(self):
        result = runner.invoke(
            app,
            ["key-events", "create", "-p", "123"],
        )

        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        ke = mock_client.properties.return_value.keyEvents.return_value
        ke.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "key-events", "create",
                    "-p", "123",
                    "--event-name", "test",
                ],
            )

        assert result.exit_code == 1


class TestKeyEventsUpdate:
    def test_update_counting_method(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "key-events", "update",
                    "-p", "123",
                    "-k", "1",
                    "--counting-method", "ONCE_PER_SESSION",
                ],
            )

        assert result.exit_code == 0
        ke = mock_client.properties.return_value.keyEvents.return_value
        call_args = ke.patch.call_args
        assert call_args[1]["updateMask"] == "countingMethod"
        assert call_args[1]["body"]["countingMethod"] == "ONCE_PER_SESSION"

    def test_update_invalid_counting_method(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "key-events", "update",
                    "-p", "123",
                    "-k", "1",
                    "--counting-method", "INVALID",
                ],
            )

        assert result.exit_code != 0

    def test_update_no_fields(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["key-events", "update", "-p", "123", "-k", "1"],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        ke = mock_client.properties.return_value.keyEvents.return_value
        ke.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "key-events", "update",
                    "-p", "123",
                    "-k", "1",
                    "--counting-method", "ONCE_PER_SESSION",
                ],
            )

        assert result.exit_code == 1


class TestKeyEventsDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["key-events", "delete", "-p", "123", "-k", "1", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        ke = mock_client.properties.return_value.keyEvents.return_value
        ke.delete.assert_called_once()

    def test_delete_confirms(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.key_events.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.key_events.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["key-events", "delete", "-p", "123", "-k", "1"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.key_events.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.key_events.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["key-events", "delete", "-p", "123", "-k", "1"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        ke = mock_client.properties.return_value.keyEvents.return_value
        ke.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.key_events.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["key-events", "delete", "-p", "123", "-k", "1", "--yes"],
            )

        assert result.exit_code == 1
