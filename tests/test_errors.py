"""Tests for ga_cli.utils.errors."""

import json
from unittest.mock import MagicMock

import pytest

from ga_cli.utils.errors import classify_error, format_api_error, handle_error, require_options
from ga_cli.utils.output import set_output_format


# ---------------------------------------------------------------------------
# format_api_error
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# classify_error
# ---------------------------------------------------------------------------
class TestClassifyError:
    def test_http_401_is_auth_error(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 401
        err = HttpError(resp, b'{"error": {"message": "Unauthenticated"}}')
        exit_code, category = classify_error(err)
        assert exit_code == 2
        assert category == "auth_error"

    def test_http_403_is_auth_error(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 403
        err = HttpError(resp, b'{"error": {"message": "Forbidden"}}')
        exit_code, category = classify_error(err)
        assert exit_code == 2
        assert category == "auth_error"

    def test_http_404_is_api_error(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 404
        err = HttpError(resp, b'{"error": {"message": "Not found"}}')
        exit_code, category = classify_error(err)
        assert exit_code == 3
        assert category == "api_error"

    def test_http_500_is_api_error(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 500
        err = HttpError(resp, b'{"error": {"message": "Internal error"}}')
        exit_code, category = classify_error(err)
        assert exit_code == 3
        assert category == "api_error"

    def test_http_400_is_api_error(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 400
        err = HttpError(resp, b'{"error": {"message": "Bad request"}}')
        exit_code, category = classify_error(err)
        assert exit_code == 3
        assert category == "api_error"

    def test_refresh_error_is_auth_error(self):
        from google.auth.exceptions import RefreshError

        err = RefreshError("token expired")
        exit_code, category = classify_error(err)
        assert exit_code == 2
        assert category == "auth_error"

    def test_runtime_error_with_auth_in_message(self):
        err = RuntimeError("Not authenticated. Run: ga auth login")
        exit_code, category = classify_error(err)
        assert exit_code == 2
        assert category == "auth_error"

    def test_runtime_error_without_auth_is_api_error(self):
        err = RuntimeError("Something else failed")
        exit_code, category = classify_error(err)
        assert exit_code == 3
        assert category == "api_error"

    def test_connection_error_is_network_error(self):
        from requests.exceptions import ConnectionError as RequestsConnectionError

        err = RequestsConnectionError("Connection refused")
        exit_code, category = classify_error(err)
        assert exit_code == 4
        assert category == "network_error"

    def test_timeout_error_is_network_error(self):
        from requests.exceptions import Timeout

        err = Timeout("Request timed out")
        exit_code, category = classify_error(err)
        assert exit_code == 4
        assert category == "network_error"

    def test_os_error_connection_refused_is_network_error(self):
        import errno

        err = OSError(errno.ECONNREFUSED, "Connection refused")
        exit_code, category = classify_error(err)
        assert exit_code == 4
        assert category == "network_error"

    def test_os_error_file_not_found_is_not_network_error(self):
        import errno

        err = OSError(errno.ENOENT, "File not found")
        exit_code, category = classify_error(err)
        # Non-network OSError falls through to api_error
        assert exit_code == 3
        assert category == "api_error"

    def test_generic_exception_is_api_error(self):
        err = ValueError("unexpected")
        exit_code, category = classify_error(err)
        assert exit_code == 3
        assert category == "api_error"


# ---------------------------------------------------------------------------
# handle_error — table format (human-readable, existing behavior)
# ---------------------------------------------------------------------------
class TestHandleError:
    def test_exits_with_code_1_for_generic_error(self):
        """Generic errors (api_error category) exit with code 3."""
        err = ValueError("test error")
        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)
        assert exc_info.value.code == 3

    def test_exits_with_code_2_for_auth_error(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 403
        err = HttpError(resp, b'{"error": {"message": "Forbidden"}}')
        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)
        assert exc_info.value.code == 2

    def test_exits_with_code_3_for_api_error(self):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 404
        err = HttpError(resp, b'{"error": {"message": "Not found"}}')
        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)
        assert exc_info.value.code == 3

    def test_prints_error_message_in_table_format(self, capsys):
        err = ValueError("visible error")
        with pytest.raises(SystemExit):
            handle_error(err)
        captured = capsys.readouterr()
        assert "visible error" in captured.err


# ---------------------------------------------------------------------------
# handle_error — JSON format (structured output for agents)
# ---------------------------------------------------------------------------
class TestHandleErrorJson:
    def test_json_output_for_api_error(self, capsys):
        from googleapiclient.errors import HttpError

        set_output_format("json")
        resp = MagicMock()
        resp.status = 404
        err = HttpError(resp, b'{"error": {"message": "Not found"}}')

        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)

        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        payload = json.loads(captured.err)
        assert payload["error"] is True
        assert payload["exit_code"] == 3
        assert payload["category"] == "api_error"
        assert payload["message"] == "Not found"
        assert payload["status_code"] == 404

    def test_json_output_for_auth_error(self, capsys):
        from googleapiclient.errors import HttpError

        set_output_format("json")
        resp = MagicMock()
        resp.status = 403
        err = HttpError(resp, b'{"error": {"message": "Permission denied"}}')

        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        payload = json.loads(captured.err)
        assert payload["error"] is True
        assert payload["exit_code"] == 2
        assert payload["category"] == "auth_error"
        assert payload["message"] == "Permission denied"
        assert payload["status_code"] == 403

    def test_json_output_for_generic_error(self, capsys):
        set_output_format("json")
        err = ValueError("something broke")

        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)

        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        payload = json.loads(captured.err)
        assert payload["error"] is True
        assert payload["exit_code"] == 3
        assert payload["category"] == "api_error"
        assert payload["message"] == "something broke"
        assert "status_code" not in payload

    def test_json_output_for_network_error(self, capsys):
        from requests.exceptions import ConnectionError as RequestsConnectionError

        set_output_format("json")
        err = RequestsConnectionError("Connection refused")

        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)

        assert exc_info.value.code == 4
        captured = capsys.readouterr()
        payload = json.loads(captured.err)
        assert payload["error"] is True
        assert payload["exit_code"] == 4
        assert payload["category"] == "network_error"

    def test_json_output_for_runtime_auth_error(self, capsys):
        set_output_format("json")
        err = RuntimeError("Not authenticated. Run: ga auth login")

        with pytest.raises(SystemExit) as exc_info:
            handle_error(err)

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        payload = json.loads(captured.err)
        assert payload["category"] == "auth_error"

    def test_table_format_still_prints_human_readable(self, capsys):
        """Ensure table format is unchanged — no JSON on stderr."""
        set_output_format("table")
        err = ValueError("human error")

        with pytest.raises(SystemExit):
            handle_error(err)

        captured = capsys.readouterr()
        assert "human error" in captured.err
        # Should NOT be valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(captured.err)


# ---------------------------------------------------------------------------
# require_options (unchanged behavior)
# ---------------------------------------------------------------------------
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
