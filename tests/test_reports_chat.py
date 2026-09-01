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


TABLE_RESPONSE = {
    "sessionId": "session-t1",
    "blocks": [
        {"text": "Your top pages:"},
        {
            "table": {
                "headers": [
                    {"header": "pagePath", "dataType": "STRING"},
                    {"header": "views", "dataType": "INTEGER"},
                ],
                "rows": [
                    {"columns": [{"value": "/home"}, {"value": "4210"}]},
                    {"columns": [{"value": "/pricing"}, {"value": "1884"}]},
                ],
            }
        },
    ],
}


class TestChatTableRendering:
    def test_renders_table_headers_and_values(self):
        mock_client = _mock_chat_client(TABLE_RESPONSE)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        out = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "pagePath" in out
        assert "views" in out
        assert "/home" in out
        assert "4210" in out
        assert "/pricing" in out

    def test_renders_text_before_the_table_it_introduces(self):
        """Block order is meaningful — text introduces the table that follows."""
        mock_client = _mock_chat_client(TABLE_RESPONSE)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        out = _strip_ansi(result.output)
        assert out.index("Your top pages:") < out.index("/home")

    def test_renders_ragged_rows_without_raising(self):
        """Alpha responses may return fewer cells than headers."""
        mock_client = _mock_chat_client({
            "sessionId": "s1",
            "blocks": [{
                "table": {
                    "headers": [
                        {"header": "country"},
                        {"header": "users"},
                        {"header": "sessions"},
                    ],
                    "rows": [{"columns": [{"value": "Sweden"}]}],
                }
            }],
        })

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0
        assert "Sweden" in _strip_ansi(result.output)

    def test_handles_table_with_no_rows(self):
        mock_client = _mock_chat_client({
            "sessionId": "s1",
            "blocks": [{"table": {"headers": [{"header": "country"}], "rows": []}}],
        })

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0


class TestChatCompactOutput:
    def test_emits_tab_separated_rows_with_a_header_line(self):
        mock_client = _mock_chat_client(TABLE_RESPONSE)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "-o", "compact"]
            )

        assert result.exit_code == 0
        lines = _strip_ansi(result.output).strip().splitlines()
        assert "pagePath\tviews" in lines
        assert "/home\t4210" in lines
        assert "/pricing\t1884" in lines

    def test_keeps_session_id_off_stdout(self):
        """stdout must stay pipeable; the session ID belongs on stderr."""
        mock_client = _mock_chat_client(TABLE_RESPONSE)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "-o", "compact"]
            )

        assert result.exit_code == 0
        # Result.output combines both streams in click >= 8.2; assert on the
        # stdout-only accessor to prove the session ID never reaches a pipe.
        assert "session-t1" not in _strip_ansi(result.stdout)
        assert "session-t1" in _strip_ansi(result.stderr)


def _http_error(status: int, message: str, api_status: str = ""):
    """Build a googleapiclient HttpError with a realistic error body."""
    from googleapiclient.errors import HttpError

    resp = MagicMock()
    resp.status = status
    resp.reason = "Forbidden" if status == 403 else "Error"
    content = json.dumps({
        "error": {"code": status, "message": message, "status": api_status}
    }).encode()
    return HttpError(resp, content)


def _failing_chat_client(exc):
    mock_client = MagicMock()
    mock_client.properties.return_value.chat.return_value.execute.side_effect = exc
    return mock_client


class TestChatScopePreflight:
    def test_missing_scope_exits_2_without_calling_the_api(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.has_scope", return_value=False), \
             patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 2
        mock_client.properties.return_value.chat.assert_not_called()

    def test_missing_scope_message_tells_the_user_to_re_authenticate(self):
        with patch("ga_cli.commands.reports.has_scope", return_value=False):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        combined = _strip_ansi(result.output)
        assert "ga auth login" in combined
        assert "analytics.chatbot.read" in combined

    def test_missing_scope_emits_structured_json_error(self):
        with patch("ga_cli.commands.reports.has_scope", return_value=False):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "-o", "json"]
            )

        assert result.exit_code == 2
        payload = json.loads(_strip_ansi(result.stderr).strip())
        assert payload["error"] is True
        assert payload["exit_code"] == 2
        assert payload["category"] == "auth_error"
        assert "ga auth login" in payload["message"]

    def test_present_scope_proceeds_to_the_api(self):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.has_scope", return_value=True), \
             patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0
        mock_client.properties.return_value.chat.assert_called_once()


class TestChatForbidden:
    """The API returns the generic Data API permission message for both
    'no property access' and 'chat not enabled', so the CLI must name both."""

    def test_403_names_both_possible_causes(self):
        exc = _http_error(
            403,
            "User does not have sufficient permissions for this property.",
            "PERMISSION_DENIED",
        )
        client = _failing_chat_client(exc)

        with patch("ga_cli.commands.reports.has_scope", return_value=True), \
             patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        combined = _strip_ansi(result.output).lower()
        assert result.exit_code == 2
        assert "access" in combined
        assert "not enabled" in combined

    def test_403_suggests_a_command_that_distinguishes_the_causes(self):
        exc = _http_error(403, "User does not have sufficient permissions.", "PERMISSION_DENIED")
        client = _failing_chat_client(exc)

        with patch("ga_cli.commands.reports.has_scope", return_value=True), \
             patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert "ga properties get -p 111" in _strip_ansi(result.output)

    def test_403_emits_structured_json_error(self):
        exc = _http_error(403, "User does not have sufficient permissions.", "PERMISSION_DENIED")
        client = _failing_chat_client(exc)

        with patch("ga_cli.commands.reports.has_scope", return_value=True), \
             patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "-o", "json"]
            )

        assert result.exit_code == 2
        payload = json.loads(_strip_ansi(result.stderr).strip())
        assert payload["category"] == "auth_error"
        assert payload["status_code"] == 403

    def test_non_403_errors_use_the_standard_handler(self):
        """A 500 must not be dressed up as a permissions problem."""
        exc = _http_error(500, "Internal error")
        client = _failing_chat_client(exc)

        with patch("ga_cli.commands.reports.has_scope", return_value=True), \
             patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        combined = _strip_ansi(result.output).lower()
        assert result.exit_code == 3
        assert "not enabled" not in combined
