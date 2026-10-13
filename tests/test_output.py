"""Tests for ga_cli.utils.output."""

import importlib
import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app
from ga_cli.utils.output import (
    _format_header,
    _format_value,
    _get_default_columns,
    error,
    get_current_output_format,
    get_output_format,
    info,
    is_tty,
    output,
    resolve_output_format,
    set_output_format,
    success,
    warn,
)


class TestIsTty:
    def test_returns_bool(self):
        result = is_tty()
        assert isinstance(result, bool)


class TestGetOutputFormat:
    def test_returns_requested_format(self):
        assert get_output_format("json") == "json"
        assert get_output_format("compact") == "compact"
        assert get_output_format("table") == "table"

    def test_defaults_to_json_when_not_tty(self, monkeypatch):
        monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: False)
        assert get_output_format(None) == "json"

    def test_defaults_to_table_when_tty(self, monkeypatch):
        monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: True)
        assert get_output_format(None) == "table"


class TestResolveOutputFormat:
    def _config(self, monkeypatch, value):
        monkeypatch.setattr("ga_cli.config.store.get_config_value", lambda key: value)

    def test_configured_table_ignored_when_piped(self, monkeypatch):
        self._config(monkeypatch, "table")
        monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: False)
        assert resolve_output_format(None) == "json"

    def test_configured_table_used_on_tty(self, monkeypatch):
        self._config(monkeypatch, "table")
        monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: True)
        assert resolve_output_format(None) == "table"

    def test_configured_json_used_on_tty(self, monkeypatch):
        self._config(monkeypatch, "json")
        monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: True)
        assert resolve_output_format(None) == "json"

    def test_unconfigured_tty_defaults_to_table(self, monkeypatch):
        self._config(monkeypatch, None)
        monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: True)
        assert resolve_output_format(None) == "table"

    def test_flag_wins_when_piped(self, monkeypatch):
        self._config(monkeypatch, "json")
        monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: False)
        assert resolve_output_format("table") == "table"
        assert get_current_output_format() == "table"


class TestPipedCliOutput:
    """End to end through a non-report command with stdout piped (conftest
    simulates a terminal by default)."""

    ACCOUNTS = [
        {"name": "accounts/123456", "displayName": "My Account"},
        {"name": "accounts/789012", "displayName": "Other Account"},
    ]

    def _list(self, monkeypatch, *args, error=None):
        monkeypatch.setattr(
            importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: False
        )
        mock_client = MagicMock()
        execute = mock_client.accounts.return_value.list.return_value.execute
        execute.return_value = {"accounts": self.ACCOUNTS}
        execute.side_effect = error
        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            return CliRunner().invoke(app, ["accounts", "list", *args])

    def test_defaults_to_json(self, monkeypatch):
        result = self._list(monkeypatch)
        assert result.exit_code == 0
        assert json.loads(result.stdout)[0]["name"] == "accounts/123456"

    def test_table_flag_wins(self, monkeypatch):
        result = self._list(monkeypatch, "-o", "table")
        assert result.exit_code == 0
        assert "My Account" in result.stdout
        assert not result.stdout.lstrip().startswith("[")

    def test_configured_table_ignored(self, monkeypatch):
        from ga_cli.config.store import set_config_value

        set_config_value("output_format", "table")
        assert json.loads(self._list(monkeypatch).stdout)[1]["name"] == "accounts/789012"

    def test_configured_compact_honoured(self, monkeypatch):
        from ga_cli.config.store import set_config_value

        set_config_value("output_format", "compact")
        result = self._list(monkeypatch)
        assert result.stdout.splitlines()[0] == "accounts/123456\tMy Account"

    def test_errors_are_structured_json(self, monkeypatch):
        result = self._list(monkeypatch, error=Exception("API quota exceeded"))
        assert result.exit_code != 0
        payload = json.loads(result.stderr)
        assert payload["error"] is True
        assert "API quota exceeded" in payload["message"]


class TestFormatHeader:
    def test_camel_case(self):
        assert _format_header("displayName") == "Display Name"

    def test_snake_case(self):
        assert _format_header("create_time") == "Create Time"

    def test_simple_word(self):
        assert _format_header("name") == "Name"

    def test_already_title_case(self):
        assert _format_header("Name") == "Name"


class TestFormatValue:
    def test_none_returns_empty(self):
        assert _format_value(None) == ""

    def test_bool_true(self):
        assert "Yes" in _format_value(True)

    def test_bool_false(self):
        assert "No" in _format_value(False)

    def test_list_with_items(self):
        assert _format_value([1, 2, 3]) == "[3 items]"

    def test_empty_list(self):
        assert _format_value([]) == "[]"

    def test_dict(self):
        result = _format_value({"key": "val"})
        parsed = json.loads(result)
        assert parsed == {"key": "val"}

    def test_string(self):
        assert _format_value("hello") == "hello"

    def test_int(self):
        assert _format_value(42) == "42"


class TestGetDefaultColumns:
    def test_priority_columns(self):
        item = {"name": "a", "displayName": "b", "type": "c", "extra": "d"}
        cols = _get_default_columns(item)
        assert cols == ["name", "displayName", "type"]

    def test_fallback_to_first_five_keys(self):
        item = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6}
        cols = _get_default_columns(item)
        assert len(cols) == 5


class TestOutputJson:
    def test_json_format(self, capsys):
        data = [{"name": "test", "value": 123}]
        output(data, fmt="json")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data

    def test_json_single_dict(self, capsys):
        data = {"name": "test"}
        output(data, fmt="json")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data


class TestOutputCompact:
    def test_compact_list_of_dicts(self, capsys):
        data = [
            {"name": "accounts/123", "displayName": "My Account"},
            {"name": "accounts/456", "displayName": "Other Account"},
        ]
        output(data, fmt="compact")
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2
        assert "accounts/123" in lines[0]
        assert "My Account" in lines[0]

    def test_compact_tsv_has_header_and_rows(self, capsys):
        data = [
            {"country": "Switzerland", "sessions": "500"},
            {"country": "Germany", "sessions": "300"},
        ]
        output(data, fmt="compact", tsv=True)
        assert capsys.readouterr().out == (
            "country\tsessions\nSwitzerland\t500\nGermany\t300\n"
        )

    def test_compact_tsv_follows_columns(self, capsys):
        data = [{"country": "Germany", "sessions": "300", "extra": "x"}]
        output(data, fmt="compact", columns=["sessions", "country"], tsv=True)
        assert capsys.readouterr().out == "sessions\tcountry\n300\tGermany\n"

    def test_compact_tsv_escapes_separators(self, capsys):
        data = [{"pageTitle": "a\tb\nc\\d\re", "sessions": "1"}]
        output(data, fmt="compact", tsv=True)
        lines = capsys.readouterr().out.splitlines()
        assert lines[1] == "a\\tb\\nc\\\\d\\re\t1"
        assert all(line.count("\t") == 1 for line in lines)

    def test_compact_tsv_escapes_terminal_control_characters(self, capsys):
        """Report values are attacker-controllable: no raw ESC, CSI or DEL."""
        data = [{"pageTitle": "\x1b[2J\x1b]0;pwned\x07title\x9b31m\x7f", "sessions": "1"}]
        output(data, fmt="compact", tsv=True)
        out = capsys.readouterr().out
        assert out.splitlines()[1] == (
            "\\x1b[2J\\x1b]0;pwned\\x07title\\x9b31m\\x7f\t1"
        )
        assert not any(ord(ch) < 0x20 and ch not in "\t\n" for ch in out)

    def test_compact_without_tsv_keeps_name_format(self, capsys):
        output([{"country": "Germany", "sessions": "300"}], fmt="compact")
        assert capsys.readouterr().out == "\t\n"

    def test_compact_single_dict(self, capsys):
        data = {"name": "test"}
        output(data, fmt="compact")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data


class TestOutputTable:
    def test_empty_list(self, capsys):
        output([], fmt="table")
        captured = capsys.readouterr()
        assert "No results found" in captured.out

    def test_list_of_dicts_no_error(self):
        """Table output should not raise for a list of dicts."""
        data = [{"name": "test", "displayName": "Test"}]
        # Should not raise
        output(data, fmt="table")

    def test_single_dict_no_error(self):
        """Table output should not raise for a single dict."""
        data = {"name": "test", "value": "123"}
        output(data, fmt="table")


class TestTableMarkupEscaping:
    """Report values are attacker-controllable text, never Rich markup."""

    def test_brackets_in_values_render_literally(self, capsys):
        output([{"pagePath": "/search?q=[foo]bar"}], fmt="table")
        assert "/search?q=[foo]bar" in capsys.readouterr().out

    def test_closing_tag_in_value_does_not_raise(self, capsys):
        output([{"pageTitle": "Docs [/admin] x"}], fmt="table")
        assert "Docs [/admin] x" in capsys.readouterr().out

    def test_brackets_in_headers_render_literally(self, capsys):
        """Pivot headers carry data values: '{pivot value} / {metric}'."""
        output(
            [{"a": "1"}], fmt="table", columns=["a"], headers=["[/x] / sessions"]
        )
        assert "[/x] / sessions" in capsys.readouterr().out

    def test_brackets_in_dict_values_render_literally(self, capsys):
        output({"displayName": "Shop [bold]EU[/bold]"}, fmt="table")
        assert "Shop [bold]EU[/bold]" in capsys.readouterr().out

    def test_bool_markup_still_styled(self):
        assert _format_value(True) == "[green]Yes[/green]"


class TestOutputFormatTracking:
    def test_default_format_is_table(self):
        assert get_current_output_format() == "table"

    def test_set_and_get_format(self):
        set_output_format("json")
        assert get_current_output_format() == "json"

        set_output_format("compact")
        assert get_current_output_format() == "compact"

    def test_set_format_persists(self):
        set_output_format("json")
        # Call get twice to verify it doesn't reset
        assert get_current_output_format() == "json"
        assert get_current_output_format() == "json"


class TestConvenienceFunctions:
    def test_success_writes_to_stderr(self, capsys):
        success("it worked")
        captured = capsys.readouterr()
        assert "it worked" in captured.err
        assert "OK" in captured.err

    def test_error_writes_to_stderr(self, capsys):
        error("something broke")
        captured = capsys.readouterr()
        assert "something broke" in captured.err
        assert "Error" in captured.err

    def test_warn_writes_to_stderr(self, capsys):
        warn("be careful")
        captured = capsys.readouterr()
        assert "be careful" in captured.err
        assert "Warning" in captured.err

    def test_info_writes_to_stderr(self, capsys):
        info("fyi")
        captured = capsys.readouterr()
        assert "fyi" in captured.err
        assert "Info" in captured.err
