"""Tests for ga_cli.api.allowlist_guard."""

import json
from pathlib import Path

import pytest
from googleapiclient.discovery import build, build_from_document
from googleapiclient.http import HttpMockSequence

from ga_cli.api.allowlist_guard import (
    AllowlistHttp,
    Route,
    UnverifiableError,
    change_history_property,
    classify_route,
    extract_refs,
    reset_caches,
)
from ga_cli.config.allowlist import Allowlist, AllowlistSource
from ga_cli.utils.errors import AllowlistError

SNAPSHOTS = Path(__file__).resolve().parent.parent / ".api-snapshots"


def _ok(n=1):
    return [({"status": "200"}, "{}")] * n


def _capture(call, service, version):
    """Run ``call(client)`` against a real discovery-built client; return (method, uri, body)."""
    http = HttpMockSequence(_ok())
    if (service, version) == ("analyticsdata", "v1alpha"):
        client = build_from_document(
            (SNAPSHOTS / "analyticsdata_v1alpha.json").read_text(), http=http
        )
    else:
        client = build(service, version, http=http)
    call(client).execute()
    uri, method, body, _headers = http.request_sequence[0]
    return method, uri, body


A = ("analyticsadmin", "v1beta")
AA = ("analyticsadmin", "v1alpha")
D = ("analyticsdata", "v1beta")
DA = ("analyticsdata", "v1alpha")

# (id, client, call, expected route, expected refs)
REAL_CALLS = [
    ("property get", A, lambda c: c.properties().get(name="properties/123"),
     Route.GENERIC, {("properties", "123")}),
    ("data stream create", A,
     lambda c: c.properties().dataStreams().create(parent="properties/123", body={}),
     Route.GENERIC, {("properties", "123")}),
    ("properties list", A,
     lambda c: c.properties().list(filter="parent:accounts/5", pageSize=200),
     Route.PROPERTIES_LIST, {("accounts", "5")}),
    ("properties create", A,
     lambda c: c.properties().create(body={"parent": "accounts/5", "displayName": "x"}),
     Route.GENERIC, {("accounts", "5")}),
    ("change history", A,
     lambda c: c.accounts().searchChangeHistoryEvents(
         account="accounts/5", body={"property": "properties/1"}),
     Route.CHANGE_HISTORY, {("accounts", "5"), ("properties", "1")}),
    ("accounts list", A, lambda c: c.accounts().list(pageSize=200),
     Route.ACCOUNTS_LIST, set()),
    ("account summaries list", A, lambda c: c.accountSummaries().list(pageSize=200),
     Route.ACCOUNT_SUMMARIES_LIST, set()),
    ("account get", A, lambda c: c.accounts().get(name="accounts/5"),
     Route.GENERIC, {("accounts", "5")}),
    ("data sharing settings", A,
     lambda c: c.accounts().getDataSharingSettings(name="accounts/5/dataSharingSettings"),
     Route.GENERIC, {("accounts", "5")}),
    ("access bindings property", AA,
     lambda c: c.properties().accessBindings().list(parent="properties/123"),
     Route.GENERIC, {("properties", "123")}),
    ("access bindings account", AA,
     lambda c: c.accounts().accessBindings().list(parent="accounts/5"),
     Route.GENERIC, {("accounts", "5")}),
    ("access bindings batch", AA,
     lambda c: c.properties().accessBindings().batchCreate(
         parent="properties/123",
         body={"requests": [{"parent": "properties/123", "accessBinding": {}}]}),
     Route.GENERIC, {("properties", "123")}),
    ("access report property", A,
     lambda c: c.properties().runAccessReport(entity="properties/123", body={}),
     Route.GENERIC, {("properties", "123")}),
    ("access report account", A,
     lambda c: c.accounts().runAccessReport(entity="accounts/5", body={}),
     Route.GENERIC, {("accounts", "5")}),
    ("run report", D,
     lambda c: c.properties().runReport(property="properties/123", body={}),
     Route.GENERIC, {("properties", "123")}),
    ("batch run reports", D,
     lambda c: c.properties().batchRunReports(
         property="properties/123", body={"requests": [{"property": "properties/9"}]}),
     Route.GENERIC, {("properties", "123"), ("properties", "9")}),
    ("metadata", D,
     lambda c: c.properties().getMetadata(name="properties/123/metadata"),
     Route.GENERIC, {("properties", "123")}),
    ("funnel", DA,
     lambda c: c.properties().runFunnelReport(property="properties/123", body={}),
     Route.GENERIC, {("properties", "123")}),
    ("chat", DA,
     lambda c: c.properties().chat(property="properties/123", body={}),
     Route.GENERIC, {("properties", "123")}),
]


class TestExtractRefsRealClients:
    @pytest.mark.parametrize(
        "client,call,route,refs", [c[1:] for c in REAL_CALLS], ids=[c[0] for c in REAL_CALLS]
    )
    def test_real_uri(self, client, call, route, refs):
        method, uri, body = _capture(call, *client)
        assert classify_route(method, uri) == route
        assert extract_refs(uri, body) == refs

    def test_encoded_slash_in_property_id_is_unverifiable(self):
        method, uri, body = _capture(
            lambda c: c.properties().get(name="properties/123%2F..%2F999"), *A
        )
        assert "%2F" in uri
        with pytest.raises(UnverifiableError):
            extract_refs(uri, body)


class TestExtractRefs:
    base = "https://analyticsadmin.googleapis.com/v1beta/"

    def test_decoded_path_reference(self):
        assert extract_refs(self.base + "properties%2F999") == {("properties", "999")}

    def test_dot_segments_unverifiable(self):
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "properties/1/../999")

    def test_non_numeric_id_unverifiable(self):
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "properties/abc")

    def test_wildcard_id_unverifiable(self):
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "accounts/-/properties")

    def test_query_filter(self):
        uri = self.base + "properties?filter=parent%3Aaccounts%2F42"
        assert extract_refs(uri) == {("accounts", "42")}

    def test_bad_query_reference_unverifiable(self):
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "properties?filter=parent%3Aaccounts%2Fx")

    def test_nested_body(self):
        body = '{"a": [{"b": {"property": "properties/7"}}], "n": 1, "x": "properties-ish"}'
        assert extract_refs(self.base + "properties/1", body) == {
            ("properties", "1"), ("properties", "7")}

    def test_body_bytes(self):
        assert extract_refs(self.base + "x", b'{"parent": "accounts/3"}') == {("accounts", "3")}

    def test_body_only_strings_starting_with_prefix(self):
        body = '{"value": "see properties/9"}'
        assert extract_refs(self.base + "properties/1", body) == {("properties", "1")}

    def test_empty_body_adds_nothing(self):
        assert extract_refs(self.base + "properties/1", b"") == {("properties", "1")}

    @pytest.mark.parametrize("body", [b"\xff\x00", "not json", 42])
    def test_non_json_body_unverifiable(self, body):
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "properties/1", body)

    def test_duplicate_body_keys_unverifiable(self):
        body = '{"property": "properties/999", "property": "properties/1"}'
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "properties/1", body)

    def test_trailing_newline_in_id_unverifiable(self):
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "properties/123%0A")

    def test_bad_body_reference_unverifiable(self):
        with pytest.raises(UnverifiableError):
            extract_refs(self.base + "properties/1", '{"property": "properties/1/../2"}')

    @pytest.mark.parametrize("body", [
        {"displayName": "properties/legacy"},
        {"displayName": "accounts/42 shop", "description": "properties/999 copy"},
        {"dimensionFilter": {"filter": {
            "fieldName": "pagePath", "stringFilter": {"value": "properties/999"}}}},
        {"dimensionFilter": {"filter": {
            "fieldName": "pagePath", "inListFilter": {"values": ["accounts/42", "x"]}}}},
        {"userQuery": "properties/999 sessions last week"},
    ], ids=["display-name", "description", "string-filter", "in-list-filter", "chat-query"])
    def test_free_text_fields_are_not_references(self, body):
        """The API never reads these as resource names, so they can't deny a request (#46)."""
        assert extract_refs(self.base + "properties/1", json.dumps(body)) == {("properties", "1")}

    @pytest.mark.parametrize("body,ref", [
        ({"parent": "accounts/2"}, ("accounts", "2")),
        ({"audience": "properties/2/audiences/5"}, ("properties", "2")),
        ({"sourceProperties": ["properties/2"]}, ("properties", "2")),
        ({"title": "properties/2"}, ("properties", "2")),
        ({"filter": {"value": "properties/2"}}, ("properties", "2")),
    ], ids=["parent", "audience", "list", "unknown-field", "value-outside-a-filter"])
    def test_every_other_field_is_still_checked(self, body, ref):
        """Only the known free-text fields are skipped; anything else stays fail closed."""
        assert ref in extract_refs(self.base + "properties/1", json.dumps(body))


class TestClassifyRoute:
    @pytest.mark.parametrize("method,uri,route", [
        ("GET", "https://www.googleapis.com/discovery/v1/apis/analyticsdata/v1alpha/rest",
         Route.DISCOVERY),
        ("GET", "https://analyticsdata.googleapis.com/$discovery/rest?version=v1alpha",
         Route.DISCOVERY),
        ("POST", "https://www.googleapis.com/discovery/v1/apis/analyticsdata/v1alpha/rest",
         Route.UNKNOWN_HOST),
        ("GET", "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest",
         Route.UNKNOWN_HOST),
        ("GET", "https://example.com/v1beta/accounts", Route.UNKNOWN_HOST),
        ("GET", "http://analyticsadmin.googleapis.com/v1beta/accounts", Route.UNKNOWN_HOST),
        ("GET", "https://analyticsadmin.googleapis.com/v1alpha/accounts", Route.ACCOUNTS_LIST),
        ("POST", "https://analyticsadmin.googleapis.com/v1beta/accounts:provisionAccountTicket",
         Route.GENERIC),
        ("POST", "https://analyticsadmin.googleapis.com/v1beta/properties", Route.GENERIC),
    ])
    def test_routes(self, method, uri, route):
        assert classify_route(method, uri) == route


class TestChangeHistoryProperty:
    def test_reads_property(self):
        assert change_history_property('{"property": "properties/12"}') == "12"

    def test_absent(self):
        assert change_history_property("{}") is None
        assert change_history_property(None) is None


# ---------------------------------------------------------------------------
# Property → account cache
# ---------------------------------------------------------------------------
SUMMARIES = [
    {
        "account": "accounts/10",
        "displayName": "Client A",
        "propertySummaries": [
            {"property": "properties/1", "displayName": "Shop A", "parent": "accounts/10"},
            # Subproperty: parent is a property, but it belongs to account 10
            {"property": "properties/3", "displayName": "Sub A", "parent": "properties/1"},
        ],
    },
    {
        "account": "accounts/20",
        "displayName": "Client B",
        "propertySummaries": [{"property": "properties/2", "displayName": "Shop B"}],
    },
]


class FakeFetch:
    def __init__(self, pages=None, error=None):
        self.calls = 0
        self.pages = pages if pages is not None else SUMMARIES
        self.error = error

    def __call__(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.pages


def _cache(tmp_path, fetch, principal="p1", now=1_000_000.0, ttl=3600):
    from ga_cli.api.allowlist_guard import AllowlistCache

    return AllowlistCache(
        principal, fetch, path=tmp_path / "allowlist-cache.json", ttl=ttl, clock=lambda: now
    )


class TestCache:
    def test_miss_refreshes_and_writes_disk(self, tmp_path):
        fetch = FakeFetch()
        cache = _cache(tmp_path, fetch)
        assert cache.lookup("2") == "20"
        assert fetch.calls == 1
        data = json.loads((tmp_path / "allowlist-cache.json").read_text())["entries"]["p1"]
        assert data["properties"] == {"1": "10", "3": "10", "2": "20"}
        assert data["names"]["1"] == "Shop A"
        assert data["account_names"]["20"] == "Client B"

    def test_subproperty_mapped_to_enclosing_account(self, tmp_path):
        assert _cache(tmp_path, FakeFetch()).lookup("3") == "10"

    def test_fresh_disk_hit_makes_no_call(self, tmp_path):
        _cache(tmp_path, FakeFetch(), now=1_000_000.0).lookup("1")
        fetch = FakeFetch()
        assert _cache(tmp_path, fetch, now=1_000_100.0).lookup("1") == "10"
        assert fetch.calls == 0

    def test_stale_disk_refreshes(self, tmp_path):
        _cache(tmp_path, FakeFetch(), now=1_000_000.0).lookup("1")
        fetch = FakeFetch()
        assert _cache(tmp_path, fetch, now=1_000_000.0 + 3600).lookup("1") == "10"
        assert fetch.calls == 1

    def test_unknown_after_refresh_is_none_and_refreshes_once(self, tmp_path):
        _cache(tmp_path, FakeFetch()).lookup("1")  # fresh file on disk
        fetch = FakeFetch()
        cache = _cache(tmp_path, fetch)
        assert cache.lookup("999") is None
        assert cache.lookup("998") is None
        assert fetch.calls == 1

    def test_principal_mismatch_is_miss(self, tmp_path):
        _cache(tmp_path, FakeFetch(), principal="p1").lookup("1")
        fetch = FakeFetch()
        _cache(tmp_path, fetch, principal="p2").lookup("1")
        assert fetch.calls == 1

    def test_two_principals_share_the_file(self, tmp_path):
        """Two identities alternating in one profile keep each other's map (#45)."""
        _cache(tmp_path, FakeFetch(), principal="p1").lookup("1")
        _cache(tmp_path, FakeFetch(), principal="p2").lookup("1")
        for principal in ("p1", "p2"):
            fetch = FakeFetch()
            assert _cache(tmp_path, fetch, principal=principal).lookup("1") == "10"
            assert fetch.calls == 0

    def test_expired_entries_are_dropped_on_write(self, tmp_path):
        _cache(tmp_path, FakeFetch(), principal="p1", now=1_000_000.0).lookup("1")
        _cache(tmp_path, FakeFetch(), principal="p2", now=1_000_000.0 + 3600).lookup("1")
        data = json.loads((tmp_path / "allowlist-cache.json").read_text())
        assert list(data["entries"]) == ["p2"]

    def test_single_principal_file_from_0_7_0_dev_is_miss(self, tmp_path):
        (tmp_path / "allowlist-cache.json").write_text(json.dumps({
            "principal": "p1", "fetched_at": 1_000_000, "properties": {"1": "10"}}))
        fetch = FakeFetch()
        assert _cache(tmp_path, fetch).lookup("1") == "10"
        assert fetch.calls == 1

    def test_corrupt_file_is_miss(self, tmp_path):
        (tmp_path / "allowlist-cache.json").write_text("{not json")
        fetch = FakeFetch()
        assert _cache(tmp_path, fetch).lookup("1") == "10"
        assert fetch.calls == 1

    def test_refresh_failure_propagates(self, tmp_path):
        with pytest.raises(ConnectionError):
            _cache(tmp_path, FakeFetch(error=ConnectionError("down"))).lookup("1")
        assert not (tmp_path / "allowlist-cache.json").exists()

    def test_failed_refresh_is_retried(self, tmp_path):
        fetch = FakeFetch(error=ConnectionError("down"))
        cache = _cache(tmp_path, fetch)
        with pytest.raises(ConnectionError):
            cache.lookup("1")
        fetch.error = None
        assert cache.lookup("1") == "10"
        assert fetch.calls == 2

    @pytest.mark.parametrize("bad", [[1], "ab", 5])
    def test_malformed_names_is_miss(self, tmp_path, bad):
        _cache(tmp_path, FakeFetch()).lookup("1")
        path = tmp_path / "allowlist-cache.json"
        data = json.loads(path.read_text())
        data["entries"]["p1"]["names"] = bad
        path.write_text(json.dumps(data))
        fetch = FakeFetch()
        assert _cache(tmp_path, fetch).lookup("1") == "10"
        assert fetch.calls == 1

    def test_prop_map_refreshes_once_for_missing_expected(self, tmp_path):
        _cache(tmp_path, FakeFetch()).lookup("1")  # fresh file without property 4
        new = SUMMARIES + [{"account": "accounts/30", "propertySummaries": [
            {"property": "properties/4"}]}]
        fetch = FakeFetch(pages=new)
        cache = _cache(tmp_path, fetch)
        assert cache.prop_map({"1"})["1"] == "10"
        assert fetch.calls == 0
        assert cache.prop_map({"4"})["4"] == "30"
        assert cache.prop_map({"999"}).get("999") is None
        assert fetch.calls == 1

    def test_writes_through_symlink_without_temp_files(self, tmp_path):
        """Same atomic write as config.json: a symlinked cache file stays a symlink."""
        real = tmp_path / "elsewhere" / "allowlist-cache.json"
        real.parent.mkdir()
        real.write_text("{}")
        (tmp_path / "allowlist-cache.json").symlink_to(real)
        _cache(tmp_path, FakeFetch()).lookup("1")
        assert (tmp_path / "allowlist-cache.json").is_symlink()
        assert "1" in real.read_text()
        assert sorted(p.name for p in real.parent.iterdir()) == ["allowlist-cache.json"]

    def test_unknown_principal_skips_disk(self, tmp_path):
        cache = _cache(tmp_path, FakeFetch(), principal=None)
        assert cache.lookup("1") == "10"
        assert not (tmp_path / "allowlist-cache.json").exists()

    def test_principal_of(self):
        from types import SimpleNamespace

        from ga_cli.api.allowlist_guard import principal_of

        sa = SimpleNamespace(service_account_email="sa@x.iam.gserviceaccount.com")
        assert principal_of(sa) == "sa@x.iam.gserviceaccount.com"
        oauth = SimpleNamespace(refresh_token="secret")
        p = principal_of(oauth)
        assert p.startswith("oauth:") and "secret" not in p and len(p) == len("oauth:") + 16
        assert principal_of(SimpleNamespace()) is None

    def test_fetch_paginates_with_auth_through_plain_http(self):
        from google.oauth2.credentials import Credentials

        from ga_cli.api.allowlist_guard import fetch_account_summaries

        inner = HttpMockSequence([
            ({"status": "200"}, json.dumps(
                {"accountSummaries": SUMMARIES[:1], "nextPageToken": "t"})),
            ({"status": "200"}, json.dumps({"accountSummaries": SUMMARIES[1:]})),
        ])
        creds = Credentials(token="tok", refresh_token="r")
        result = fetch_account_summaries(creds, inner)
        assert [s["account"] for s in result] == ["accounts/10", "accounts/20"]
        uri, _, _, headers = inner.request_sequence[0]
        assert "accountSummaries" in uri and "pageSize=200" in uri
        assert headers["authorization"] == "Bearer tok"
        assert "pageToken=t" in inner.request_sequence[1][0]


# ---------------------------------------------------------------------------
# AllowlistHttp: enforcement with real discovery-built clients
# ---------------------------------------------------------------------------

class FakeCreds:
    """Minimal google-auth credentials: adds a bearer token, refresh bumps it."""

    refresh_token = "refresh-token"

    def __init__(self):
        self.token = "t1"
        self.refreshes = 0

    def before_request(self, request, method, url, headers):
        headers["authorization"] = f"Bearer {self.token}"

    def refresh(self, request):
        self.refreshes += 1
        self.token = f"t{self.refreshes + 1}"


class MetadataCreds(FakeCreds):
    """Compute Engine style: the account email is "default" until the first refresh."""

    service_account_email = "default"
    refresh_token = None
    valid = False

    def refresh(self, request):
        super().refresh(request)
        self.service_account_email = "sa@proj.iam.gserviceaccount.com"
        self.valid = True

    def before_request(self, request, method, url, headers):
        if not self.valid:
            self.refresh(request)
        super().before_request(request, method, url, headers)


def _al(accounts=None, properties=None, env_accounts=None, env_properties=None):
    sources = []
    if accounts is not None or properties is not None:
        sources.append(AllowlistSource(
            "config",
            None if accounts is None else frozenset(accounts),
            None if properties is None else frozenset(properties),
        ))
    if env_accounts is not None or env_properties is not None:
        sources.append(AllowlistSource(
            "env",
            None if env_accounts is None else frozenset(env_accounts),
            None if env_properties is None else frozenset(env_properties),
        ))
    return Allowlist(tuple(sources))


def _resp(body=None, status="200"):
    return ({"status": status}, json.dumps(body if body is not None else {}))


SUMMARIES_RESP = _resp({"accountSummaries": SUMMARIES})


@pytest.fixture(autouse=True)
def _reset_guard_caches():
    reset_caches()
    yield
    reset_caches()


def guarded(allowlist, responses, client=A, creds=None):
    """A real client over AllowlistHttp over HttpMockSequence; returns (client, inner)."""
    inner = HttpMockSequence(responses)
    http = AllowlistHttp(creds or FakeCreds(), http=inner, allowlist=allowlist)
    if client == DA:
        c = build_from_document((SNAPSHOTS / "analyticsdata_v1alpha.json").read_text(), http=http)
    else:
        c = build(client[0], client[1], http=http)
    return c, inner


def _sent(inner):
    return [(m, u.split("?")[0].rsplit("/v1", 1)[-1]) for u, m, _b, _h in inner.request_sequence]


class TestGuardOff:
    def test_passthrough_unchanged(self):
        c, inner = guarded(_al(), [_resp({"accounts": [{"name": "accounts/1"}]})])
        assert c.accounts().list().execute() == {"accounts": [{"name": "accounts/1"}]}
        assert len(inner.request_sequence) == 1
        assert inner.request_sequence[0][3]["authorization"] == "Bearer t1"

    def test_no_filtering_when_off(self):
        body = {"properties": [{"name": "properties/999"}]}
        c, inner = guarded(_al(), [_resp(body)])
        assert c.properties().list(filter="parent:accounts/5").execute() == body

    def test_loads_allowlist_when_not_given(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "1")
        http = AllowlistHttp(FakeCreds(), http=HttpMockSequence([]))
        assert http.allowlist.enabled

    def test_unreadable_config_fails_closed(self, tmp_path):
        (tmp_path / "config.json").write_text('{"allowed_property_ids": ["1"],}')
        with pytest.raises(AllowlistError):
            AllowlistHttp(FakeCreds(), http=HttpMockSequence([]))


class TestPropertyAllowlist:
    def test_property_not_on_allowlist_is_not_sent(self):
        c, inner = guarded(_al(properties={"1"}), [])
        with pytest.raises(AllowlistError) as exc:
            c.properties().get(name="properties/999").execute()
        assert exc.value.resource == "properties/999"
        assert "not on the allowlist" in str(exc.value)
        assert inner.request_sequence == []

    def test_directly_listed_property_needs_no_cache(self):
        c, inner = guarded(_al(properties={"1"}), [_resp({"name": "properties/1"})])
        c.properties().get(name="properties/1").execute()
        assert _sent(inner) == [("GET", "beta/properties/1")]

    def test_property_via_account_uses_cache(self):
        c, inner = guarded(_al(accounts={"10"}), [SUMMARIES_RESP, _resp()])
        c.properties().get(name="properties/3").execute()  # subproperty of account 10
        assert _sent(inner) == [("GET", "beta/accountSummaries"), ("GET", "beta/properties/3")]

    def test_property_of_other_account_denied(self):
        c, inner = guarded(_al(accounts={"10"}), [SUMMARIES_RESP])
        with pytest.raises(AllowlistError) as exc:
            c.properties().get(name="properties/2").execute()
        assert "is not on the allowlist" in str(exc.value)
        assert _sent(inner) == [("GET", "beta/accountSummaries")]

    def test_unknown_property_single_refresh_then_deny(self):
        c, inner = guarded(_al(accounts={"10"}), [SUMMARIES_RESP])
        with pytest.raises(AllowlistError) as exc:
            c.properties().get(name="properties/999").execute()
        assert "not visible to these credentials" in str(exc.value)
        with pytest.raises(AllowlistError):
            c.properties().get(name="properties/998").execute()
        assert _sent(inner) == [("GET", "beta/accountSummaries")]

    def test_client_derives_its_cache_once(self, monkeypatch):
        """Not once per property while filtering a list (#45)."""
        import ga_cli.api.allowlist_guard as guard

        calls = []
        real = guard.principal_of
        monkeypatch.setattr(guard, "principal_of", lambda c: calls.append(c) or real(c))
        listing = {"properties": [{"name": f"properties/{p}"} for p in ("1", "2", "3")]}
        c, _ = guarded(_al(accounts={"10"}), [_resp(listing), SUMMARIES_RESP])
        result = c.properties().list(filter="ancestor:accounts/10").execute()
        assert [p["name"] for p in result["properties"]] == ["properties/1", "properties/3"]
        assert len(calls) == 1

    def test_metadata_credentials_fetch_once_and_persist(self, isolated_config_dir):
        """Compute Engine names its account only after a refresh: one fetch, saved (#45)."""
        c, inner = guarded(
            _al(accounts={"10"}), [SUMMARIES_RESP, _resp(), _resp()], creds=MetadataCreds()
        )
        c.properties().get(name="properties/1").execute()
        c.properties().get(name="properties/3").execute()
        assert _sent(inner) == [
            ("GET", "beta/accountSummaries"),
            ("GET", "beta/properties/1"),
            ("GET", "beta/properties/3"),
        ]
        assert "sa@proj.iam.gserviceaccount.com" in (
            isolated_config_dir / "allowlist-cache.json").read_text()

    def test_metadata_credentials_read_the_cache_in_the_next_process(self):
        guarded(_al(accounts={"10"}), [SUMMARIES_RESP, _resp()], creds=MetadataCreds())[0] \
            .properties().get(name="properties/1").execute()
        reset_caches()  # a new process, with fresh credentials that say "default" again
        c, inner = guarded(_al(accounts={"10"}), [_resp()], creds=MetadataCreds())
        c.properties().get(name="properties/1").execute()
        assert _sent(inner) == [("GET", "beta/properties/1")]

    def test_denial_of_property_only_allowlist_makes_no_lookup(self):
        c, inner = guarded(_al(properties={"1"}), [])
        with pytest.raises(AllowlistError):
            c.properties().get(name="properties/2").execute()
        assert inner.request_sequence == []

    def test_env_narrows_file(self):
        c, inner = guarded(_al(accounts={"10", "20"}, env_properties={"2"}), [SUMMARIES_RESP])
        with pytest.raises(AllowlistError):
            c.properties().get(name="properties/1").execute()
        assert _sent(inner) == [("GET", "beta/accountSummaries")]

    def test_encoded_slash_denied(self):
        c, inner = guarded(_al(properties={"123"}), [])
        with pytest.raises(AllowlistError):
            c.properties().get(name="properties/123%2F..%2F999").execute()
        assert inner.request_sequence == []

    def test_refresh_failure_propagates_and_sends_nothing(self):
        from googleapiclient.errors import HttpError

        c, inner = guarded(_al(accounts={"10"}), [_resp({"error": {}}, status="500")])
        with pytest.raises(HttpError):
            c.properties().get(name="properties/1").execute()
        assert _sent(inner) == [("GET", "beta/accountSummaries")]


class TestAccountLevel:
    def test_account_allowed(self):
        c, inner = guarded(_al(accounts={"10"}), [_resp()])
        c.accounts().get(name="accounts/10").execute()
        assert _sent(inner) == [("GET", "beta/accounts/10")]

    def test_property_only_allowlist_denies_parent_account(self):
        c, inner = guarded(_al(properties={"1"}), [])
        with pytest.raises(AllowlistError) as exc:
            c.accounts().get(name="accounts/10").execute()
        assert exc.value.resource == "accounts/10"
        assert inner.request_sequence == []

    def test_property_create_needs_account(self):
        c, inner = guarded(_al(properties={"1"}), [])
        with pytest.raises(AllowlistError):
            c.properties().create(body={"parent": "accounts/10", "displayName": "x"}).execute()
        assert inner.request_sequence == []

    def test_no_reference_route_denied(self):
        c, inner = guarded(_al(accounts={"10"}), [])
        with pytest.raises(AllowlistError) as exc:
            c.accounts().provisionAccountTicket(body={}).execute()
        assert "names no account or property" in str(exc.value)
        assert inner.request_sequence == []

    def test_unknown_host_denied(self):
        http = AllowlistHttp(FakeCreds(), http=HttpMockSequence([]), allowlist=_al(accounts={"1"}))
        with pytest.raises(AllowlistError):
            http.request("https://example.com/v1beta/accounts")

    def test_method_override_header_denied(self):
        http = AllowlistHttp(FakeCreds(), http=HttpMockSequence([]), allowlist=_al(accounts={"1"}))
        with pytest.raises(AllowlistError):
            http.request(
                "https://analyticsadmin.googleapis.com/v1beta/accounts",
                headers={"X-HTTP-Method-Override": "DELETE"},
            )


# Property 4 in account 30, created after SUMMARIES was cached
NEW_SUMMARIES_RESP = _resp({"accountSummaries": SUMMARIES + [{
    "account": "accounts/30",
    "displayName": "Client C",
    "propertySummaries": [{"property": "properties/4", "displayName": "New"}],
}]})


def _warm_disk_cache():
    """Write a fresh allowlist-cache.json from SUMMARIES, then forget it in memory."""
    c, _ = guarded(_al(accounts={"10"}), [SUMMARIES_RESP, _resp()])
    c.properties().get(name="properties/1").execute()
    reset_caches()


class TestNewlyAllowlistedProperty:
    def test_properties_list_refreshes_stale_map(self):
        _warm_disk_cache()
        listing = {"properties": [{"name": "properties/4"}]}
        c, inner = guarded(_al(properties={"4"}), [NEW_SUMMARIES_RESP, _resp(listing)])
        assert c.properties().list(filter="parent:accounts/30").execute() == listing
        assert _sent(inner) == [("GET", "beta/accountSummaries"), ("GET", "beta/properties")]

    def test_accounts_list_refreshes_stale_map(self):
        _warm_disk_cache()
        accounts = {"accounts": [{"name": "accounts/10"}, {"name": "accounts/30"}]}
        c, _ = guarded(_al(properties={"4"}), [_resp(accounts), NEW_SUMMARIES_RESP])
        assert c.accounts().list().execute() == {"accounts": [{"name": "accounts/30"}]}

    def test_fresh_map_with_every_listed_property_is_not_refetched(self):
        _warm_disk_cache()
        accounts = {"accounts": [{"name": "accounts/10"}, {"name": "accounts/20"}]}
        c, inner = guarded(_al(properties={"2"}), [_resp(accounts)])
        assert c.accounts().list().execute() == {"accounts": [{"name": "accounts/20"}]}
        assert len(inner.request_sequence) == 1


class TestSpecialRoutes:
    def test_properties_list_allowed_account_without_properties_is_empty(self):
        c, inner = guarded(_al(accounts={"30"}), [_resp({"nextPageToken": "n"})])
        assert c.properties().list(filter="parent:accounts/30").execute() == {
            "nextPageToken": "n"}
        assert _sent(inner) == [("GET", "beta/properties")]

    def test_properties_list_account_with_allowed_property(self):
        listing = {"properties": [{"name": "properties/1"}, {"name": "properties/3"}]}
        c, inner = guarded(_al(properties={"1"}), [SUMMARIES_RESP, _resp(listing)])
        result = c.properties().list(filter="parent:accounts/10").execute()
        assert result == {"properties": [{"name": "properties/1"}]}

    def test_properties_list_other_account_denied(self):
        c, inner = guarded(_al(properties={"1"}), [SUMMARIES_RESP])
        with pytest.raises(AllowlistError) as exc:
            c.properties().list(filter="parent:accounts/20").execute()
        assert exc.value.resource == "accounts/20"
        assert _sent(inner) == [("GET", "beta/accountSummaries")]

    def test_change_history_allowed_account(self):
        c, inner = guarded(_al(accounts={"10"}), [_resp()])
        c.accounts().searchChangeHistoryEvents(account="accounts/10", body={}).execute()
        assert _sent(inner) == [("POST", "beta/accounts/10:searchChangeHistoryEvents")]

    def test_change_history_via_allowed_property(self):
        c, inner = guarded(_al(properties={"1"}), [SUMMARIES_RESP, _resp()])
        c.accounts().searchChangeHistoryEvents(
            account="accounts/10", body={"property": "properties/1"}).execute()
        assert _sent(inner)[-1] == ("POST", "beta/accounts/10:searchChangeHistoryEvents")

    def test_change_history_without_property_denied(self):
        c, inner = guarded(_al(properties={"1"}), [])
        with pytest.raises(AllowlistError):
            c.accounts().searchChangeHistoryEvents(account="accounts/10", body={}).execute()
        assert inner.request_sequence == []

    def test_change_history_property_of_other_account_denied(self):
        c, inner = guarded(_al(properties={"2"}), [SUMMARIES_RESP])
        with pytest.raises(AllowlistError):
            c.accounts().searchChangeHistoryEvents(
                account="accounts/10", body={"property": "properties/2"}).execute()
        assert _sent(inner) == [("GET", "beta/accountSummaries")]


class TestPerClient:
    @pytest.mark.parametrize("client,call", [
        (AA, lambda c, p: c.properties().accessBindings().list(parent=f"properties/{p}")),
        (D, lambda c, p: c.properties().runReport(property=f"properties/{p}", body={})),
        (DA, lambda c, p: c.properties().runFunnelReport(property=f"properties/{p}", body={})),
        (A, lambda c, p: c.properties().dataStreams().list(parent=f"properties/{p}")),
    ], ids=["admin-v1alpha", "data-v1beta", "data-v1alpha", "admin-v1beta"])
    def test_allow_and_deny(self, client, call):
        c, inner = guarded(_al(properties={"1"}), [_resp()], client=client)
        call(c, "1").execute()
        assert len(inner.request_sequence) == 1
        with pytest.raises(AllowlistError):
            call(c, "2").execute()
        assert len(inner.request_sequence) == 1

    def test_batch_with_disallowed_nested_property(self):
        c, inner = guarded(_al(properties={"1"}), [], client=D)
        with pytest.raises(AllowlistError) as exc:
            c.properties().batchRunReports(
                property="properties/1", body={"requests": [{"property": "properties/2"}]}
            ).execute()
        assert exc.value.resource == "properties/2"
        assert inner.request_sequence == []

    @pytest.mark.parametrize("responses", [
        lambda doc: [({"status": "200"}, doc)],
        lambda doc: [({"status": "404"}, ""), ({"status": "200"}, doc)],
    ], ids=["www-discovery", "dollar-discovery"])
    def test_dynamic_discovery_passes(self, responses):
        doc = (SNAPSHOTS / "analyticsdata_v1alpha.json").read_text()
        inner = HttpMockSequence(responses(doc) + [_resp()])
        http = AllowlistHttp(FakeCreds(), http=inner, allowlist=_al(properties={"1"}))
        c = build("analyticsdata", "v1alpha", http=http, static_discovery=False,
                  cache_discovery=False)
        c.properties().runFunnelReport(property="properties/1", body={}).execute()
        uris = [u for u, *_ in inner.request_sequence]
        assert "discovery" in uris[0]
        assert uris[-1].startswith("https://analyticsdata.googleapis.com/v1alpha/properties/1:")


class TestRetry:
    def test_401_retry_is_checked_again(self, monkeypatch):
        c, inner = guarded(_al(properties={"1"}), [_resp(status="401"), _resp({"ok": 1})])
        http = c._http
        checks = []
        orig = http._check
        monkeypatch.setattr(http, "_check", lambda *a: checks.append(a[0]) or orig(*a))
        assert c.properties().get(name="properties/1").execute() == {"ok": 1}
        assert len(checks) == 2
        assert http.credentials.refreshes == 1
        assert inner.request_sequence[1][3]["authorization"] == "Bearer t2"

    def test_401_retry_filters_idempotently(self):
        listing = {"accounts": [{"name": "accounts/10"}, {"name": "accounts/20"}]}
        c, inner = guarded(_al(accounts={"10"}), [_resp(status="401"), _resp(listing)])
        assert c.accounts().list().execute() == {"accounts": [{"name": "accounts/10"}]}


# ---------------------------------------------------------------------------
# Response filtering
# ---------------------------------------------------------------------------
class TestFilter:
    ACCOUNTS = {"accounts": [{"name": "accounts/10"}, {"name": "accounts/20"},
                             {"name": "accounts/30"}], "nextPageToken": "n"}
    URI = "https://analyticsadmin.googleapis.com/v1beta/accounts"

    def test_accounts_list_account_allowlist_needs_no_cache(self):
        c, inner = guarded(_al(accounts={"10", "30"}), [_resp(self.ACCOUNTS)])
        result = c.accounts().list().execute()
        assert result == {"accounts": [{"name": "accounts/10"}, {"name": "accounts/30"}],
                          "nextPageToken": "n"}
        assert len(inner.request_sequence) == 1

    def test_accounts_list_property_allowlist(self):
        c, inner = guarded(_al(properties={"2"}), [_resp(self.ACCOUNTS), SUMMARIES_RESP])
        assert c.accounts().list().execute()["accounts"] == [{"name": "accounts/20"}]

    def test_account_summaries_filtered_without_a_second_fetch(self):
        c, inner = guarded(_al(properties={"1"}), [SUMMARIES_RESP])
        result = c.accountSummaries().list().execute()
        assert [s["account"] for s in result["accountSummaries"]] == ["accounts/10"]
        assert [p["property"] for p in result["accountSummaries"][0]["propertySummaries"]] == [
            "properties/1"]
        assert len(inner.request_sequence) == 1

    def test_account_summaries_allowed_account_keeps_all_properties(self):
        c, _ = guarded(_al(accounts={"20"}, properties={"1"}), [SUMMARIES_RESP])
        result = c.accountSummaries().list().execute()
        assert [
            (s["account"], [p["property"] for p in s["propertySummaries"]])
            for s in result["accountSummaries"]
        ] == [("accounts/10", ["properties/1"]), ("accounts/20", ["properties/2"])]

    def test_properties_list_scoped_by_filter_needs_no_cache(self):
        # properties/3 is a subproperty (parent properties/1) in account 10
        listing = {"properties": [{"name": "properties/3", "parent": "properties/1"}]}
        c, inner = guarded(_al(accounts={"10"}), [_resp(listing)])
        assert c.properties().list(filter="parent:accounts/10").execute() == listing
        assert _sent(inner) == [("GET", "beta/properties")]

    def test_properties_list_other_filter_uses_cache(self):
        listing = {"properties": [{"name": "properties/1"}, {"name": "properties/2"}]}
        c, inner = guarded(_al(accounts={"10"}), [_resp(listing), SUMMARIES_RESP])
        result = c.properties().list(filter="ancestor:accounts/10").execute()
        assert result == {"properties": [{"name": "properties/1"}]}
        assert _sent(inner) == [("GET", "beta/properties"), ("GET", "beta/accountSummaries")]

    def test_filter_is_idempotent(self):
        http = AllowlistHttp(FakeCreds(), http=HttpMockSequence([]),
                             allowlist=_al(accounts={"10"}))
        once = http._filter(Route.ACCOUNTS_LIST, json.dumps(self.ACCOUNTS).encode(), self.URI)
        assert isinstance(once, bytes)
        assert http._filter(Route.ACCOUNTS_LIST, once, self.URI) == once

    @pytest.mark.parametrize(
        "content",
        [b"\xff\xfe not utf-8", b"<html>", b'[{"name": "accounts/20"}]', "not json"],
        ids=["not-utf8", "html", "json-array", "str"],
    )
    def test_unreadable_list_response_fails_closed(self, content):
        """A list response the filter can't read is never passed through unfiltered (#46)."""
        http = AllowlistHttp(FakeCreds(), http=HttpMockSequence([]),
                             allowlist=_al(accounts={"10"}))
        with pytest.raises(AllowlistError) as exc:
            http._filter(Route.ACCOUNTS_LIST, content, self.URI)
        assert exc.value.resource == "/v1beta/accounts"

    def test_non_2xx_untouched(self):
        from googleapiclient.errors import HttpError

        c, _ = guarded(_al(accounts={"10"}), [_resp(self.ACCOUNTS, status="500")])
        with pytest.raises(HttpError) as exc:
            c.accounts().list().execute()
        assert b"accounts/20" in exc.value.content

    def test_paginate_all_crosses_empty_page(self):
        from ga_cli.utils.pagination import paginate_all

        pages = [
            _resp({"accounts": [{"name": "accounts/20"}], "nextPageToken": "p2"}),
            _resp({"accounts": [{"name": "accounts/10"}]}),
        ]
        c, inner = guarded(_al(accounts={"10"}), pages)
        result = paginate_all(lambda **kw: c.accounts().list(**kw).execute(), "accounts")
        assert result == [{"name": "accounts/10"}]
        assert len(inner.request_sequence) == 2


# ---------------------------------------------------------------------------
# End to end through the CLI
# ---------------------------------------------------------------------------
class TestCli:
    @pytest.fixture
    def cli(self, monkeypatch):
        from typer.testing import CliRunner

        from ga_cli.api import client as client_mod
        from ga_cli.main import app

        holder = {}

        def run(args, responses):
            inner = HttpMockSequence(responses)
            holder["inner"] = inner
            monkeypatch.setattr(client_mod, "_get_credentials", lambda: FakeCreds())
            monkeypatch.setattr(client_mod, "build_http", lambda: inner)
            client_mod.clear_client_cache()
            return CliRunner().invoke(app, args)

        yield run, holder
        client_mod.clear_client_cache()

    def test_accounts_list_filtered_across_pages(self, cli, monkeypatch):
        run, holder = cli
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "10")
        result = run(["accounts", "list", "-o", "json"], [
            _resp({"accounts": [{"name": "accounts/20"}], "nextPageToken": "p2"}),
            _resp({"accounts": [{"name": "accounts/10", "displayName": "A"}]}),
        ])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == [{"name": "accounts/10", "displayName": "A"}]

    def test_denied_command_exits_5_with_json_payload(self, cli, monkeypatch):
        run, holder = cli
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "1")
        result = run(["properties", "get", "-p", "999", "-o", "json"], [])
        assert result.exit_code == 5
        payload = json.loads(result.stderr)
        assert payload["category"] == "allowlist_error"
        assert payload["resource"] == "properties/999"
        assert holder["inner"].request_sequence == []

    def test_malformed_allowlist_exits_5(self, cli, monkeypatch):
        run, _ = cli
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "abc")
        result = run(["properties", "get", "-p", "1", "-o", "json"], [])
        assert result.exit_code == 5
        assert json.loads(result.stderr)["resource"] == "GA_CLI_ALLOWED_PROPERTIES"
