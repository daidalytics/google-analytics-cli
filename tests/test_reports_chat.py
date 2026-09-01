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


class TestChatContinue:
    def test_continue_sends_the_cached_session_id(self, isolated_config_dir):
        from ga_cli.config.chat_session import save_session

        save_session("111", "cached-session-1")
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q", "--continue"])

        assert result.exit_code == 0
        assert _chat_body(mock_client)["sessionId"] == "cached-session-1"

    def test_successful_call_caches_the_returned_session(self, isolated_config_dir):
        from ga_cli.config.chat_session import load_session

        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert result.exit_code == 0
        assert load_session("111") == "session-abc123"

    def test_explicit_session_id_also_updates_the_cache(self, isolated_config_dir):
        from ga_cli.config.chat_session import load_session

        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "--session-id", "explicit-1"]
            )

        assert result.exit_code == 0
        assert load_session("111") == "session-abc123"

    def test_rejects_session_id_together_with_continue(self, isolated_config_dir):
        """Ambiguity here is a user mistake worth surfacing, not resolving."""
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["reports", "chat", "-p", "111", "q", "--continue", "--session-id", "x"],
            )

        assert result.exit_code != 0
        mock_client.properties.return_value.chat.assert_not_called()

    def test_continue_without_a_cached_session_errors_actionably(self, isolated_config_dir):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q", "--continue"])

        assert result.exit_code != 0
        mock_client.properties.return_value.chat.assert_not_called()
        assert "no saved chat session" in _strip_ansi(result.output).lower()

    def test_sessions_do_not_leak_between_properties(self, isolated_config_dir):
        from ga_cli.config.chat_session import save_session

        save_session("111", "cached-for-111")
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(app, ["reports", "chat", "-p", "222", "q", "--continue"])

        assert result.exit_code != 0
        mock_client.properties.return_value.chat.assert_not_called()


class TestChatExpiredSession:
    """A rejected session must fail loudly. Silently starting a new one would
    answer a follow-up without its context and look like it worked."""

    def test_expired_session_clears_the_cache(self, isolated_config_dir):
        from ga_cli.config.chat_session import load_session, save_session

        save_session("111", "stale-session")
        client = _failing_chat_client(
            _http_error(400, "Invalid session ID.", "INVALID_ARGUMENT")
        )

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q", "--continue"])

        assert result.exit_code != 0
        assert load_session("111") is None

    def test_expired_session_explains_what_happened(self, isolated_config_dir):
        from ga_cli.config.chat_session import save_session

        save_session("111", "stale-session")
        client = _failing_chat_client(
            _http_error(400, "Invalid session ID.", "INVALID_ARGUMENT")
        )

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q", "--continue"])

        combined = _strip_ansi(result.output).lower()
        assert "session" in combined
        assert "no longer valid" in combined or "expired" in combined

    def test_expired_session_does_not_retry_as_a_new_session(self, isolated_config_dir):
        from ga_cli.config.chat_session import save_session

        save_session("111", "stale-session")
        client = _failing_chat_client(
            _http_error(400, "Invalid session ID.", "INVALID_ARGUMENT")
        )

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            runner.invoke(app, ["reports", "chat", "-p", "111", "q", "--continue"])

        assert client.properties.return_value.chat.return_value.execute.call_count == 1

    def test_a_400_without_a_session_is_not_reported_as_expiry(self, isolated_config_dir):
        """Only blame the session when we actually sent one."""
        client = _failing_chat_client(
            _http_error(400, "Query cannot be parsed.", "INVALID_ARGUMENT")
        )

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        combined = _strip_ansi(result.output).lower()
        assert result.exit_code != 0
        assert "no longer valid" not in combined


def _mock_chat_sequence(responses):
    """Mock client returning each response in turn."""
    mock_client = MagicMock()
    mock_client.properties.return_value.chat.return_value.execute.side_effect = responses
    return mock_client


def _chat_bodies(mock_client) -> list:
    """Every request body the command sent, in order."""
    return [c.kwargs["body"] for c in mock_client.properties.return_value.chat.call_args_list]


def _prompts(*answers):
    """Patch the REPL prompt to yield `answers` in order."""
    prompt = MagicMock()
    prompt.return_value.ask.side_effect = list(answers)
    return patch("ga_cli.commands.reports.questionary.text", prompt)


class TestChatInteractive:
    def test_loops_until_the_user_types_exit(self, isolated_config_dir):
        client = _mock_chat_sequence([
            {"sessionId": "s1", "blocks": [{"text": "first answer"}]},
            {"sessionId": "s1", "blocks": [{"text": "second answer"}]},
        ])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("first question", "second question", "exit"):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        out = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert len(_chat_bodies(client)) == 2
        assert "first answer" in out
        assert "second answer" in out

    def test_threads_the_session_between_turns(self, isolated_config_dir):
        client = _mock_chat_sequence([
            {"sessionId": "server-session", "blocks": [{"text": "a"}]},
            {"sessionId": "server-session", "blocks": [{"text": "b"}]},
        ])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("one", "two", "exit"):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        bodies = _chat_bodies(client)
        assert result.exit_code == 0
        assert "sessionId" not in bodies[0]
        assert bodies[1]["sessionId"] == "server-session"

    def test_quit_also_ends_the_session(self, isolated_config_dir):
        client = _mock_chat_sequence([{"sessionId": "s1", "blocks": [{"text": "a"}]}])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("one", "quit"):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        assert result.exit_code == 0
        assert len(_chat_bodies(client)) == 1

    def test_interrupting_the_prompt_exits_cleanly(self, isolated_config_dir):
        """questionary returns None for Ctrl-C / Ctrl-D."""
        client = _mock_chat_sequence([])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts(None):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        assert result.exit_code == 0
        assert _chat_bodies(client) == []

    def test_empty_input_ends_the_session(self, isolated_config_dir):
        client = _mock_chat_sequence([])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("   "):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        assert result.exit_code == 0
        assert _chat_bodies(client) == []

    def test_positional_query_becomes_the_first_turn(self, isolated_config_dir):
        client = _mock_chat_sequence([{"sessionId": "s1", "blocks": [{"text": "a"}]}])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("exit"):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "--interactive", "opening question"]
            )

        assert result.exit_code == 0
        assert _chat_bodies(client)[0]["userQuery"] == "opening question"

    def test_json_output_emits_one_object_per_turn(self, isolated_config_dir):
        client = _mock_chat_sequence([
            {"sessionId": "s1", "blocks": [{"text": "a"}]},
            {"sessionId": "s1", "blocks": [{"text": "b"}]},
        ])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("one", "two", "exit"):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "--interactive", "-o", "json"]
            )

        assert result.exit_code == 0
        lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["blocks"][0]["text"] == "a"
        assert json.loads(lines[1])["blocks"][0]["text"] == "b"

    def test_caches_the_session_after_each_turn(self, isolated_config_dir):
        from ga_cli.config.chat_session import load_session

        client = _mock_chat_sequence([{"sessionId": "repl-session", "blocks": []}])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("one", "exit"):
            runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        assert load_session("111") == "repl-session"

    def test_interactive_does_not_require_a_positional_query(self, isolated_config_dir):
        client = _mock_chat_sequence([])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("exit"):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        assert result.exit_code == 0


QUOTA_RESPONSE = {
    "sessionId": "s1",
    "blocks": [{"text": "answer"}],
    "propertyQuota": {
        "tokensPerDay": {"consumed": 1240, "remaining": 8760},
        "tokensPerHour": {"consumed": 180, "remaining": 820},
    },
}


class TestChatQuota:
    def test_one_shot_does_not_request_quota_by_default(self, isolated_config_dir):
        """Scripted output stays clean unless the caller asks."""
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            runner.invoke(app, ["reports", "chat", "-p", "111", "q"])

        assert not _chat_body(mock_client).get("returnPropertyQuota")

    def test_explicit_flag_requests_quota_in_one_shot(self, isolated_config_dir):
        mock_client = _mock_chat_client(QUOTA_RESPONSE)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "--return-property-quota"]
            )

        assert result.exit_code == 0
        assert _chat_body(mock_client)["returnPropertyQuota"] is True

    def test_interactive_requests_quota_by_default(self, isolated_config_dir):
        """Chat is token-metered; show consumption where it accumulates."""
        client = _mock_chat_sequence([QUOTA_RESPONSE])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("one", "exit"):
            result = runner.invoke(app, ["reports", "chat", "-p", "111", "--interactive"])

        assert result.exit_code == 0
        assert _chat_bodies(client)[0]["returnPropertyQuota"] is True

    def test_interactive_quota_can_be_turned_off(self, isolated_config_dir):
        client = _mock_chat_sequence([{"sessionId": "s1", "blocks": []}])

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=client), \
             _prompts("one", "exit"):
            result = runner.invoke(
                app,
                ["reports", "chat", "-p", "111", "--interactive",
                 "--no-return-property-quota"],
            )

        assert result.exit_code == 0
        assert not _chat_bodies(client)[0].get("returnPropertyQuota")

    def test_renders_both_chat_quota_fields(self, isolated_config_dir):
        mock_client = _mock_chat_client(QUOTA_RESPONSE)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "--return-property-quota"]
            )

        combined = _strip_ansi(result.output)
        assert "tokensPerDay" in combined
        assert "1240" in combined
        assert "tokensPerHour" in combined
        assert "180" in combined

    def test_tolerates_a_partial_quota_payload(self, isolated_config_dir):
        """PropertyChatQuota exposes only two fields; either may be absent."""
        mock_client = _mock_chat_client({
            "sessionId": "s1",
            "blocks": [{"text": "a"}],
            "propertyQuota": {"tokensPerDay": {"consumed": 5, "remaining": 95}},
        })

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "--return-property-quota"]
            )

        assert result.exit_code == 0
        assert "tokensPerDay" in _strip_ansi(result.output)

    def test_no_quota_in_response_renders_nothing(self, isolated_config_dir):
        mock_client = _mock_chat_client()

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app, ["reports", "chat", "-p", "111", "q", "--return-property-quota"]
            )

        assert result.exit_code == 0
        assert "Quota" not in _strip_ansi(result.output)

    def test_quota_stays_off_stdout_in_json_mode(self, isolated_config_dir):
        """The raw response already carries propertyQuota; stdout stays valid JSON."""
        mock_client = _mock_chat_client(QUOTA_RESPONSE)

        with patch("ga_cli.commands.reports.get_data_alpha_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["reports", "chat", "-p", "111", "q", "--return-property-quota", "-o", "json"],
            )

        assert result.exit_code == 0
        assert json.loads(result.stdout) == QUOTA_RESPONSE
