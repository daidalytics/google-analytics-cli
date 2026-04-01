"""Tests for ga_cli.utils.output."""

import json
import sys

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
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        assert get_output_format(None) == "json"

    def test_defaults_to_table_when_tty(self, monkeypatch):
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        assert get_output_format(None) == "table"


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
