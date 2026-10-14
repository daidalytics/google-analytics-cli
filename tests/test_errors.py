"""Tests for ga_cli.utils.errors."""

import json
from unittest.mock import MagicMock

import pytest

from ga_cli.utils.errors import (
    ADC_LOGIN_COMMAND,
    NotAuthenticatedError,
    classify_error,
    format_api_error,
    handle_error,
    require_options,
)
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

    def test_error_message_with_brackets_printed_verbatim(self, capsys):
        """API error text is not markup: '[/x]' used to raise MarkupError."""
        with pytest.raises(SystemExit):
            handle_error(ValueError("Invalid value [/x] in [foo]"))
        assert "Invalid value [/x] in [foo]" in capsys.readouterr().err


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
# ADC scope hint: 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT while using gcloud ADC
# ---------------------------------------------------------------------------
SCOPE_MESSAGE = "Request had insufficient authentication scopes."


def _google_error(status: int = 403, reason: str | None = "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
                  body: bytes | None = None):
    """An HttpError with the body Google sends for this failure."""
    from googleapiclient.errors import HttpError

    if body is None:
        error: dict = {
            "code": status,
            "message": SCOPE_MESSAGE,
            "status": "PERMISSION_DENIED",
        }
        if reason is not None:
            error["details"] = [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": reason,
                    "domain": "googleapis.com",
                    "metadata": {
                        "service": "analyticsdata.googleapis.com",
                        "method": "google.analytics.data.v1beta.BetaAnalyticsData.RunReport",
                    },
                }
            ]
        body = json.dumps({"error": error}).encode()
    resp = MagicMock()
    resp.status = status
    resp.reason = "Forbidden"
    return HttpError(resp, body)


@pytest.fixture
def auth_method(monkeypatch):
    """Set the method get_last_auth_method() reports."""
    def _set(method):
        monkeypatch.setattr("ga_cli.api.client._last_auth_method", method)

    return _set


class TestAdcScopeHint:
    def test_json_adds_hint_field(self, auth_method, capsys):
        auth_method("adc")
        set_output_format("json")

        with pytest.raises(SystemExit) as exc_info:
            handle_error(_google_error())

        assert exc_info.value.code == 2
        payload = json.loads(capsys.readouterr().err)
        assert payload["message"] == SCOPE_MESSAGE  # unchanged
        assert payload["category"] == "auth_error"
        assert payload["status_code"] == 403
        assert payload["hint"] == (
            "These credentials come from gcloud Application Default Credentials "
            f"without the Analytics scopes. Run: {ADC_LOGIN_COMMAND}"
        )

    def test_table_appends_hint(self, auth_method, capsys):
        auth_method("adc")
        set_output_format("table")

        with pytest.raises(SystemExit) as exc_info:
            handle_error(_google_error())

        assert exc_info.value.code == 2
        err = " ".join(capsys.readouterr().err.split())
        assert SCOPE_MESSAGE in err
        assert "gcloud Application Default Credentials without the Analytics scopes" in err
        assert "gcloud auth application-default login" in err
        assert err.index(SCOPE_MESSAGE) < err.index("Application Default Credentials")

    def test_hint_names_the_documented_scopes(self):
        assert "analytics.readonly" in ADC_LOGIN_COMMAND
        assert "cloud-platform" in ADC_LOGIN_COMMAND

    @pytest.mark.parametrize("method", ["oauth", "service-account", None])
    def test_no_hint_for_other_methods(self, auth_method, capsys, method):
        auth_method(method)
        set_output_format("json")

        with pytest.raises(SystemExit):
            handle_error(_google_error())

        payload = json.loads(capsys.readouterr().err)
        assert "hint" not in payload
        assert payload["message"] == SCOPE_MESSAGE

    @pytest.mark.parametrize("method", ["oauth", "service-account", None])
    def test_no_hint_in_table_for_other_methods(self, auth_method, capsys, method):
        auth_method(method)
        set_output_format("table")

        with pytest.raises(SystemExit):
            handle_error(_google_error())

        assert "Application Default Credentials" not in capsys.readouterr().err

    @pytest.mark.parametrize(
        "err",
        [
            pytest.param(_google_error(reason="IAM_PERMISSION_DENIED"), id="other-reason"),
            pytest.param(_google_error(reason=None), id="no-details"),
            pytest.param(
                _google_error(body=b'{"error": {"message": "Forbidden"}}'), id="bare-403"
            ),
            pytest.param(_google_error(body=b"not json"), id="non-json-body"),
            pytest.param(
                _google_error(body=b'{"error": {"details": "oops"}}'), id="malformed-details"
            ),
            pytest.param(_google_error(status=401), id="401-same-reason"),
            pytest.param(_google_error(status=400), id="400-same-reason"),
            pytest.param(RuntimeError("Not authenticated"), id="not-an-http-error"),
        ],
    )
    def test_no_hint_for_other_errors_under_adc(self, auth_method, capsys, err):
        auth_method("adc")
        set_output_format("json")

        with pytest.raises(SystemExit):
            handle_error(err)

        payload = json.loads(capsys.readouterr().err)
        assert "hint" not in payload


class TestLastAuthMethod:
    """api.client records how the credentials in use were resolved."""

    def test_none_before_resolution(self):
        from ga_cli.api.client import get_last_auth_method

        assert get_last_auth_method() is None

    def test_records_adc(self, no_gcloud_adc):
        from ga_cli.api.client import get_last_auth_method, resolve_credentials

        no_gcloud_adc.side_effect = None
        no_gcloud_adc.return_value = (object(), "proj")

        _creds, method = resolve_credentials()

        assert method == "adc"
        assert get_last_auth_method() == "adc"

    def test_records_oauth(self, monkeypatch):
        from ga_cli.api import client

        monkeypatch.setattr(client, "get_valid_credentials", lambda: object())

        client.resolve_credentials()

        assert client.get_last_auth_method() == "oauth"

    def test_records_service_account(self, monkeypatch):
        from ga_cli.api import client

        sa = MagicMock(expired=False)
        monkeypatch.setattr(client, "get_service_account_credentials", lambda: sa)

        client.resolve_credentials()

        assert client.get_last_auth_method() == "service-account"

    def test_failed_resolution_forgets_previous_method(self, no_gcloud_adc):
        from google.auth.exceptions import DefaultCredentialsError

        from ga_cli.api.client import get_last_auth_method, resolve_credentials

        no_gcloud_adc.side_effect = None
        no_gcloud_adc.return_value = (object(), "proj")
        resolve_credentials()
        no_gcloud_adc.side_effect = DefaultCredentialsError("gone")

        with pytest.raises(NotAuthenticatedError):
            resolve_credentials()

        assert get_last_auth_method() is None

    def test_cleared_with_client_cache(self, no_gcloud_adc):
        from ga_cli.api.client import (
            clear_client_cache,
            get_last_auth_method,
            resolve_credentials,
        )

        no_gcloud_adc.side_effect = None
        no_gcloud_adc.return_value = (object(), "proj")
        resolve_credentials()

        clear_client_cache()

        assert get_last_auth_method() is None


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
