"""Allowlist guard coverage for ``ga audience-exports`` (SPEC D5).

These endpoints have no per-command allowlist code: the generic guard checks the request
path and every ``properties/…`` string in the body. The commands were added after the
guard was tested against real clients, so each endpoint is pinned here against a real
discovery-built analyticsdata v1beta client.
"""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ga_cli.api.allowlist_guard import extract_refs
from ga_cli.main import app
from ga_cli.utils.errors import AllowlistError
from tests.test_allowlist_guard import SUMMARIES_RESP, D, _al, _resp, _sent, guarded

PATCH_CLIENT = "ga_cli.commands.audience_exports.get_data_client"

# Property 1 is listed directly, so allowed calls need no accountSummaries lookup and a
# denied call sends nothing at all.
ALLOWED = _al(properties={"1"})
DIMENSIONS = [{"dimensionName": "deviceId"}]
EXPORT_1 = "properties/1/audienceExports/7"


def _exports(allowlist=ALLOWED, responses=()):
    """``properties().audienceExports()`` of a guarded v1beta client, and the mock HTTP."""
    c, inner = guarded(allowlist, list(responses), client=D)
    return c.properties().audienceExports(), inner


def _create_body(audience):
    return {"audience": audience, "dimensions": DIMENSIONS}


class TestCreate:
    def test_allowed_parent_and_audience(self):
        exports, inner = _exports(responses=[_resp({"name": "operations/1"})])
        exports.create(
            parent="properties/1", body=_create_body("properties/1/audiences/5")
        ).execute()
        assert _sent(inner) == [("POST", "beta/properties/1/audienceExports")]

    def test_disallowed_parent_denied(self):
        exports, inner = _exports()
        with pytest.raises(AllowlistError) as exc:
            exports.create(
                parent="properties/2", body=_create_body("properties/2/audiences/5")
            ).execute()
        assert exc.value.resource == "properties/2"
        assert inner.request_sequence == []

    def test_disallowed_parent_with_allowed_audience_denied(self):
        exports, inner = _exports()
        with pytest.raises(AllowlistError) as exc:
            exports.create(
                parent="properties/2", body=_create_body("properties/1/audiences/5")
            ).execute()
        assert exc.value.resource == "properties/2"
        assert inner.request_sequence == []

    def test_audience_of_other_property_denied_under_allowed_parent(self):
        """The body's audience is checked on its own; an allowed ``-p`` doesn't cover it."""
        exports, inner = _exports()
        with pytest.raises(AllowlistError) as exc:
            exports.create(
                parent="properties/1", body=_create_body("properties/2/audiences/5")
            ).execute()
        assert exc.value.resource == "properties/2"
        assert inner.request_sequence == []

    def test_audience_of_other_account_denied_after_lookup(self):
        # Account 10 holds property 1; property 2 sits in account 20
        exports, inner = _exports(_al(accounts={"10"}), [SUMMARIES_RESP])
        with pytest.raises(AllowlistError) as exc:
            exports.create(
                parent="properties/1", body=_create_body("properties/2/audiences/5")
            ).execute()
        assert exc.value.resource == "properties/2"
        assert _sent(inner) == [("GET", "beta/accountSummaries")]


class TestList:
    def test_allowed(self):
        exports, inner = _exports(responses=[_resp({"audienceExports": []})])
        exports.list(parent="properties/1", pageSize=1000).execute()
        assert _sent(inner) == [("GET", "beta/properties/1/audienceExports")]

    def test_denied(self):
        exports, inner = _exports()
        with pytest.raises(AllowlistError) as exc:
            exports.list(parent="properties/2", pageSize=1000).execute()
        assert exc.value.resource == "properties/2"
        assert inner.request_sequence == []


class TestGet:
    """Also the call ``create --wait`` polls with."""

    def test_allowed(self):
        exports, inner = _exports(responses=[_resp({"name": EXPORT_1, "state": "ACTIVE"})])
        exports.get(name=EXPORT_1).execute()
        assert _sent(inner) == [("GET", "beta/properties/1/audienceExports/7")]

    def test_denied(self):
        exports, inner = _exports()
        with pytest.raises(AllowlistError) as exc:
            exports.get(name="properties/2/audienceExports/7").execute()
        assert exc.value.resource == "properties/2"
        assert inner.request_sequence == []


class TestQuery:
    BODY = {"offset": 0, "limit": 10}

    def test_allowed(self):
        exports, inner = _exports(responses=[_resp({"audienceRows": []})])
        exports.query(name=EXPORT_1, body=self.BODY).execute()
        assert _sent(inner) == [("POST", "beta/properties/1/audienceExports/7:query")]

    def test_body_holds_no_refs(self):
        exports, inner = _exports(responses=[_resp()])
        exports.query(name=EXPORT_1, body=self.BODY).execute()
        uri, _method, body, _headers = inner.request_sequence[0]
        assert json.loads(body) == self.BODY
        assert extract_refs(uri, body) == {("properties", "1")}

    def test_denied(self):
        exports, inner = _exports()
        with pytest.raises(AllowlistError) as exc:
            exports.query(name="properties/2/audienceExports/7", body=self.BODY).execute()
        assert exc.value.resource == "properties/2"
        assert inner.request_sequence == []


# ---------------------------------------------------------------------------
# End to end through the CLI
# ---------------------------------------------------------------------------
def _invoke(args, responses=()):
    """Run ``ga audience-exports …`` with a guarded data client; returns (result, inner)."""
    c, inner = guarded(ALLOWED, list(responses), client=D)
    with patch(PATCH_CLIENT, return_value=c):
        result = CliRunner().invoke(app, ["audience-exports", *args])
    return result, inner


class TestCli:
    @pytest.mark.parametrize("prop", ["1", "999"], ids=["allowed", "not-allowed"])
    def test_create_dry_run_sends_nothing(self, prop):
        """Dry runs send nothing, so they aren't checked (SPEC D5), as in the PR's others."""
        result, inner = _invoke(
            ["create", "-p", prop, "--audience-id", "5", "--dimensions", "deviceId", "--dry-run"]
        )
        assert result.exit_code == 0, result.output
        assert inner.request_sequence == []
        payload = json.loads(result.stdout)
        assert payload["dry_run"] is True
        assert payload["resource"] == f"properties/{prop}/audienceExports"
        assert payload["body"]["audience"] == f"properties/{prop}/audiences/5"

    def test_create_allowed(self):
        operation = {"name": "operations/op1", "response": {"name": EXPORT_1}}
        result, inner = _invoke(
            ["create", "-p", "1", "--audience-id", "5", "--dimensions", "deviceId", "-o", "json"],
            [_resp(operation)],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["exportId"] == "7"
        assert _sent(inner) == [("POST", "beta/properties/1/audienceExports")]

    def test_create_list_fallback_and_wait_poll_allowed(self):
        """No export name in the Operation: ``list`` finds it, then ``--wait`` polls ``get``."""
        listing = {"audienceExports": [{
            "name": EXPORT_1,
            "audience": "properties/1/audiences/5",
            "beginCreatingTime": "2026-10-16T08:00:00Z",
        }]}
        result, inner = _invoke(
            ["create", "-p", "1", "--audience-id", "5", "--dimensions", "deviceId",
             "--wait", "-o", "json"],
            [
                _resp({"name": "operations/op1"}),
                _resp(listing),
                _resp({"name": EXPORT_1, "state": "ACTIVE"}),
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["state"] == "ACTIVE"
        assert _sent(inner) == [
            ("POST", "beta/properties/1/audienceExports"),
            ("GET", "beta/properties/1/audienceExports"),
            ("GET", "beta/properties/1/audienceExports/7"),
        ]

    @pytest.mark.parametrize("args", [
        ["list", "-p", "2"],
        ["get", "-p", "2", "--export-id", "7"],
        ["query", "-p", "2", "--export-id", "7", "--limit", "10"],
        ["create", "-p", "2", "--audience-id", "5", "--dimensions", "deviceId"],
        ["create", "-p", "1", "--audience-id", "properties/2/audiences/5",
         "--dimensions", "deviceId"],
    ], ids=["list", "get", "query", "create", "create-other-property-audience"])
    def test_denied_exits_5_with_json_error(self, args):
        result, inner = _invoke([*args, "-o", "json"])
        assert result.exit_code == 5, result.output
        payload = json.loads(result.stderr)
        assert payload["category"] == "allowlist_error"
        assert payload["resource"] == "properties/2"
        assert inner.request_sequence == []
