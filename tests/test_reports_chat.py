"""Tests for ga reports chat command."""

import json
import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


TEXT_ONLY_RESPONSE = {
    "sessionId": "session-abc123",
    "blocks": [
        {"text": "You had 4,210 users in the last 7 days."},
    ],
}


def _mock_chat_client(response=None):
    """Build a mock Data Alpha client whose chat() returns `response`."""
    mock_client = MagicMock()
    mock_client.properties.return_value.chat.return_value.execute.return_value = (
        response if response is not None else TEXT_ONLY_RESPONSE
    )
    return mock_client


def _chat_body(mock_client) -> dict:
    """Extract the request body the command sent."""
    return mock_client.properties.return_value.chat.call_args.kwargs["body"]


class TestChatOneShot:
    def test_renders_text_blocks(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "how many users?"])

        assert result.exit_code == 0
        assert "You had 4,210 users in the last 7 days." in _strip_ansi(result.output)

    def test_sends_user_query_to_the_api(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "how many users?"])

        assert result.exit_code == 0
        assert _chat_body(mock_client)["userQuery"] == "how many users?"
        assert mock_client.properties.return_value.chat.call_args.kwargs["property"] == (
            "properties/111"
        )

    def test_renders_multiple_text_blocks_in_order(self):
        mock_client = _mock_chat_client({
            "sessionId": "s1",
            "blocks": [{"text": "First point."}, {"text": "Second point."}],
        })

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        out = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert out.index("First point.") < out.index("Second point.")

    def test_does_not_interpret_response_text_as_rich_markup(self):
        """Model-generated text containing square brackets must render literally."""
        mock_client = _mock_chat_client({
            "sessionId": "s1",
            "blocks": [{"text": "Use [bold] tags carefully."}],
        })

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0
        assert "[bold]" in _strip_ansi(result.output)

    def test_skips_blocks_with_no_known_content(self):
        """A future block type must not crash the command."""
        mock_client = _mock_chat_client({
            "sessionId": "s1",
            "blocks": [{"chart": {"kind": "line"}}, {"text": "Still rendered."}],
        })

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0
        assert "Still rendered." in _strip_ansi(result.output)

    def test_handles_response_with_no_blocks(self):
        mock_client = _mock_chat_client({"sessionId": "s1"})

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0

    def test_json_output_is_a_lossless_passthrough(self):
        response = {
            "sessionId": "session-abc123",
            "blocks": [{"text": "hello"}],
            "propertyQuota": {"tokensPerDay": {"consumed": 5, "remaining": 95}},
        }
        mock_client = _mock_chat_client(response)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "-o", "json"]
            )

        assert result.exit_code == 0
        assert json.loads(result.output) == response


class TestChatSessionFlags:
    def test_prints_session_id_so_it_can_be_resumed(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0
        assert "session-abc123" in _strip_ansi(result.output)

    def test_omits_session_id_when_not_supplied(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert "sessionId" not in _chat_body(mock_client)

    def test_sends_explicit_session_id(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "--session-id", "prev-999"]
            )

        assert result.exit_code == 0
        assert _chat_body(mock_client)["sessionId"] == "prev-999"


class TestChatValidation:
    def test_rejects_missing_query(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111"])

        assert result.exit_code != 0
        mock_client.properties.return_value.chat.assert_not_called()

    def test_rejects_whitespace_only_query(self):
        """Don't spend chat quota on a blank request."""
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "   "])

        assert result.exit_code != 0
        mock_client.properties.return_value.chat.assert_not_called()

    def test_requires_a_property_id(self, isolated_config_dir):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "q"])

        assert result.exit_code != 0

    def test_uses_default_property_from_config(self, isolated_config_dir):
        from ga_cli.config.store import UserConfig, save_config

        save_config(UserConfig(default_property_id="654321"))
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "q"])

        assert result.exit_code == 0
        assert mock_client.properties.return_value.chat.call_args.kwargs["property"] == (
            "properties/654321"
        )
