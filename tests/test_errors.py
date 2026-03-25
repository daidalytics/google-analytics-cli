"""Tests for ga_cli.utils.errors."""

import json
from unittest.mock import MagicMock

import pytest

from ga_cli.utils.errors import format_api_error, handle_error, require_options


class TestFormatApiError:
    def test_generic_exception(self):
        err = ValueError("something went wrong")
        assert format_api_error(err) == "something went wrong"

    def test_http_error_with_json_body(self):

        from googleapiclient.errors import HttpError

        content = json.dumps({
            "error": {"message": "Permission denied", "code": 403}
        }).encode()

        resp = MagicMock()
        resp.status = 403
        resp.reason = "Forbidden"

        err = HttpError(resp, content)
        assert format_api_error(err) == "Permission denied"

    def test_http_error_with_invalid_json(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 500
        resp.reason = "Internal Server Error"

        err = HttpError(resp, b"not json")
        result = format_api_error(err)
        # Should fall back to str(err) without crashing
        assert isinstance(result, str)


class TestHandleError:
    def test_exits_with_code_1(self):
        err = ValueError("test error")
        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)
        assert exc_info.value.code == 1

    def test_prints_error_message(self, capsys):
        err = ValueError("visible error")
        with pytest.raises(SystemExit):
            handle_error(err)
        captured = capsys.readouterr()
        assert "visible error" in captured.err


class TestRequireOptions:
    def test_passes_when_all_present(self):
        options = {"account_id": "123", "property_id": "456"}
        # Should not raise
        require_options(options, ["account_id", "property_id"])

    def test_raises_when_missing(self):
        import typer
        options = {"account_id": "123"}
        with pytest.raises(typer.BadParameter) as exc_info:
            require_options(options, ["account_id", "property_id"])
        assert "--property-id" in str(exc_info.value)

    def test_raises_when_empty_value(self):
        import typer
        options = {"account_id": "123", "property_id": ""}
        with pytest.raises(typer.BadParameter):
            require_options(options, ["account_id", "property_id"])

    def test_raises_when_none_value(self):
        import typer
        options = {"account_id": "123", "property_id": None}
        with pytest.raises(typer.BadParameter):
            require_options(options, ["account_id", "property_id"])
