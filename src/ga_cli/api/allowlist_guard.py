"""Allowlist enforcement at the HTTP layer.

Every request the 4 API clients send goes through ``AllowlistHttp``. With an allowlist
configured, it extracts the account/property references from the request, checks them
before anything is sent, and filters the top-level list responses. Anything it can't
place is denied (fail closed).
"""

from __future__ import annotations

import enum
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import parse_qsl, unquote, urlsplit

from google_auth_httplib2 import AuthorizedHttp

from ..config.constants import ALLOWLIST_CACHE_TTL_SECONDS, get_allowlist_cache_path

GA_HOSTS = ("analyticsadmin.googleapis.com", "analyticsdata.googleapis.com")
DISCOVERY_HOST = "www.googleapis.com"

_VERSION = r"/v1(?:alpha|beta)"
# All matched with fullmatch()
_DISCOVERY_PATH = re.compile(r"/discovery/v1/apis/analytics(?:admin|data)/v1(?:alpha|beta)/rest")
_ACCOUNTS_LIST = re.compile(rf"{_VERSION}/accounts")
_SUMMARIES_LIST = re.compile(rf"{_VERSION}/accountSummaries")
_PROPERTIES_COLLECTION = re.compile(rf"{_VERSION}/properties")
_CHANGE_HISTORY = re.compile(rf"{_VERSION}/accounts/([0-9]+):searchChangeHistoryEvents")

# A resource reference at the start of a path or after a '/'
_PATH_REF = re.compile(r"(?:^|/)(accounts|properties)/([^/]*)")
# A resource reference anywhere in a query value (filter=parent:accounts/123)
_QUERY_REF = re.compile(r"(?<![A-Za-z0-9_])(accounts|properties)/([^\s,()\"']*)")
_ID = re.compile(r"([0-9]+)(?:\Z|[/:])")
_PARENT_FILTER = re.compile(r"parent:accounts/([0-9]+)")

Ref = tuple[str, str]  # ("accounts" | "properties", numeric id)


class UnverifiableError(Exception):
    """The request names a resource in a form the guard can't check."""


class Route(enum.Enum):
    DISCOVERY = "discovery"
    ACCOUNTS_LIST = "accounts_list"
    ACCOUNT_SUMMARIES_LIST = "account_summaries_list"
    PROPERTIES_LIST = "properties_list"
    CHANGE_HISTORY = "change_history"
    GENERIC = "generic"
    UNKNOWN_HOST = "unknown_host"


def classify_route(method: str, uri: str) -> Route:
    """Classify a request by host, method and path."""
    parts = urlsplit(uri)
    method = method.upper()
    host = (parts.hostname or "").lower()
    if parts.scheme != "https":
        return Route.UNKNOWN_HOST
    if host == DISCOVERY_HOST:
        if method == "GET" and _DISCOVERY_PATH.fullmatch(parts.path):
            return Route.DISCOVERY
        return Route.UNKNOWN_HOST
    if host not in GA_HOSTS:
        return Route.UNKNOWN_HOST
    if method == "GET" and parts.path == "/$discovery/rest":
        return Route.DISCOVERY
    if method == "GET":
        if _ACCOUNTS_LIST.fullmatch(parts.path):
            return Route.ACCOUNTS_LIST
        if _SUMMARIES_LIST.fullmatch(parts.path):
            return Route.ACCOUNT_SUMMARIES_LIST
        if _PROPERTIES_COLLECTION.fullmatch(parts.path):
            return Route.PROPERTIES_LIST
    if method == "POST" and _CHANGE_HISTORY.fullmatch(parts.path):
        return Route.CHANGE_HISTORY
    return Route.GENERIC


def _check_id(kind: str, tail: str, where: str) -> Ref:
    m = _ID.match(tail)
    if not m:
        raise UnverifiableError(f"can't read the {kind} ID in {where}")
    return kind, m.group(1)


def _path_refs(path: str, where: str) -> set[Ref]:
    if any(seg in (".", "..") for seg in path.split("/")):
        raise UnverifiableError(f"dot segment in {where}")
    return {_check_id(kind, tail, where) for kind, tail in _PATH_REF.findall(path)}


def _body_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _body_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _body_strings(v)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        # json keeps only the last value; the server might read another one
        raise UnverifiableError("duplicate key in the request body")
    return dict(pairs)


def parse_body(body: Any) -> Any:
    """Decode a JSON request body; None for no body.

    Raises UnverifiableError for a body that isn't JSON, or that the server might
    read differently (duplicate keys).
    """
    if body is None or body in (b"", ""):
        return None
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            raise UnverifiableError("request body is not UTF-8 JSON") from None
    if not isinstance(body, str):
        raise UnverifiableError("request body is not JSON")
    try:
        return json.loads(body, object_pairs_hook=_reject_duplicate_keys)
    except ValueError:
        raise UnverifiableError("request body is not JSON") from None


def extract_refs(uri: str, body: Any = None) -> set[Ref]:
    """Collect every account/property the request names.

    Sources: the raw and percent-decoded path, the decoded query values, and every JSON
    body string that starts with ``accounts/`` or ``properties/``. Raises UnverifiableError
    when a reference can't be read cleanly (e.g. ``properties/123%2F..%2F999``).
    """
    parts = urlsplit(uri)
    refs = _path_refs(parts.path, "the request path")
    refs |= _path_refs(unquote(parts.path), "the request path")

    for _, value in parse_qsl(parts.query, keep_blank_values=True):
        for kind, tail in _QUERY_REF.findall(value):
            refs.add(_check_id(kind, tail, "the query string"))

    for s in _body_strings(parse_body(body)):
        if s.startswith(("accounts/", "properties/")):
            refs |= _path_refs(s, "the request body")
    return refs


def change_history_property(body: Any) -> Optional[str]:
    """The ``property`` a searchChangeHistoryEvents body narrows to, if any."""
    data = parse_body(body)
    return _id_of(data.get("property"), "properties") if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Property → account cache
# ---------------------------------------------------------------------------


def principal_of(credentials: Any) -> Optional[str]:
    """Identify whose property map the cache holds; None if it can't be told.

    A service account (key, impersonated, or behind Workload Identity Federation) is its
    email, and a user is a hash of the refresh token. An email without "@" is unknown:
    Compute Engine reports "default" until its first refresh.
    """
    email = getattr(credentials, "service_account_email", None)
    if isinstance(email, str) and "@" in email:
        return email
    token = getattr(credentials, "refresh_token", None)
    if isinstance(token, str) and token:
        return "oauth:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    return None


def fetch_account_summaries(credentials: Any, http: Any) -> list[dict]:
    """All account summaries, through a plain AuthorizedHttp that bypasses the guard.

    Not ``AllowlistHttp.request``'s ``super().request``: its 401 retry calls
    ``self.request`` and would re-enter the guard mid-refresh.
    """
    from googleapiclient.discovery import build

    from ..utils.pagination import paginate_all

    admin = build("analyticsadmin", "v1beta", http=AuthorizedHttp(credentials, http=http))
    return paginate_all(
        lambda **kw: admin.accountSummaries().list(**kw).execute(),
        "accountSummaries",
        pageSize=200,
    )


class AllowlistCache:
    """Property → account map, from ``accountSummaries.list``, cached on disk for an hour.

    Each property maps to the account of the summary it sits in, never to its
    ``parent`` (which is ``properties/N`` for subproperties). An unknown property
    triggers at most one refresh per process.
    """

    def __init__(
        self,
        principal: Optional[str],
        fetch: Callable[[], list[dict]],
        path: Optional[Path] = None,
        ttl: int = ALLOWLIST_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ):
        self.principal = principal
        self._fetch = fetch
        self._path = path
        self._ttl = ttl
        self._clock = clock
        self._loaded = False
        self._refreshed = False
        self.properties: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self.account_names: dict[str, str] = {}
        self.fetched_at: Optional[float] = None

    @property
    def path(self) -> Path:
        return self._path or get_allowlist_cache_path()

    def _load_disk(self) -> bool:
        if self.principal is None:
            return False
        try:
            data = json.loads(self.path.read_text())
            fetched_at = float(data["fetched_at"])
            properties = data["properties"]
            names = data.get("names") or {}
            account_names = data.get("account_names") or {}
            if data.get("principal") != self.principal or not all(
                isinstance(d, dict) for d in (properties, names, account_names)
            ):
                return False
        except (OSError, ValueError, KeyError, TypeError):
            return False
        age = self._clock() - fetched_at
        if age < 0 or age >= self._ttl:
            return False
        self.properties = {str(k): str(v) for k, v in properties.items()}
        self.names = names
        self.account_names = account_names
        self.fetched_at = fetched_at
        return True

    def _save_disk(self) -> None:
        if self.principal is None:
            return
        data = {
            "principal": self.principal,
            "fetched_at": int(self.fetched_at or 0),
            "properties": self.properties,
            "names": self.names,
            "account_names": self.account_names,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".allowlist-cache.")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f)
                os.replace(tmp, self.path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        except OSError:
            pass  # best effort: the in-memory map still serves this process

    def refresh(self) -> None:
        """Rebuild the map from the API.

        Errors propagate (network/auth exit codes) and leave the cache unloaded, so a
        later call in the same process tries again instead of seeing an empty map.
        """
        summaries = self._fetch()
        properties: dict[str, str] = {}
        names: dict[str, str] = {}
        account_names: dict[str, str] = {}
        for summary in summaries:
            account = str(summary.get("account", ""))
            if not account.startswith("accounts/"):
                continue
            aid = account.split("/", 1)[1]
            account_names[aid] = summary.get("displayName", "")
            for prop in summary.get("propertySummaries") or []:
                name = str(prop.get("property", ""))
                if name.startswith("properties/"):
                    pid = name.split("/", 1)[1]
                    properties[pid] = aid
                    names[pid] = prop.get("displayName", "")
        self.properties = properties
        self.names = names
        self.account_names = account_names
        self.fetched_at = self._clock()
        self._loaded = True
        self._refreshed = True
        self._save_disk()

    def ensure_loaded(self) -> None:
        if not self._loaded:
            if self._load_disk():
                self._loaded = True
            else:
                self.refresh()

    def prop_map(self, expected: Iterable[str] = ()) -> dict[str, str]:
        """The whole map, refreshed once per process if it lacks one of ``expected``.

        Pass the allowlisted property IDs, so a property created and allowlisted since
        the cache was written is found without waiting for the TTL.
        """
        self.ensure_loaded()
        if not self._refreshed and any(pid not in self.properties for pid in expected):
            self.refresh()
        return self.properties

    def lookup(self, pid: str) -> Optional[str]:
        """The account of ``pid``, or None if it is still unknown after one refresh."""
        return self.prop_map((pid,)).get(pid)


_caches: dict[Optional[str], AllowlistCache] = {}


def cache_for(credentials: Any, http: Any) -> AllowlistCache:
    """The process-wide cache for these credentials' principal."""
    principal = principal_of(credentials)
    if principal not in _caches:
        _caches[principal] = AllowlistCache(
            principal, lambda: fetch_account_summaries(credentials, http)
        )
    return _caches[principal]


def reset_caches() -> None:
    """Forget in-process cache state (tests, re-authentication)."""
    _caches.clear()


def delete_cache_file() -> None:
    """Remove the on-disk cache (``ga auth login`` / ``logout``)."""
    reset_caches()
    try:
        get_allowlist_cache_path().unlink(missing_ok=True)
    except OSError:
        pass  # a stale file is still keyed to its principal, so it can't be misused


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------
_FILTERED_ROUTES = (Route.ACCOUNTS_LIST, Route.ACCOUNT_SUMMARIES_LIST, Route.PROPERTIES_LIST)


class AllowlistHttp(AuthorizedHttp):
    """AuthorizedHttp that checks every request against the allowlist before sending it.

    With no allowlist configured it is a pure passthrough. ``AuthorizedHttp``'s 401
    retry calls ``self.request`` again, so the check and the filters run twice on a
    retried request and must be idempotent.
    """

    def __init__(self, credentials: Any, http: Any = None, allowlist: Any = None, **kwargs):
        super().__init__(credentials, http=http, **kwargs)
        if allowlist is None:
            from ..config.allowlist import load_allowlist

            allowlist = load_allowlist()
        self.allowlist = allowlist

    def request(self, uri, method="GET", body=None, headers=None, *args, **kwargs):
        if not self.allowlist.enabled:
            return super().request(uri, method, body, headers, *args, **kwargs)

        route = self._check(uri, method, body, headers)
        response, content = super().request(uri, method, body, headers, *args, **kwargs)
        if route in _FILTERED_ROUTES and 200 <= int(response.status) < 300:
            content = self._filter(route, content, uri)
        return response, content

    # -- checks -------------------------------------------------------------

    @property
    def cache(self) -> AllowlistCache:
        return cache_for(self.credentials, self.http)

    def _deny(self, resource: str, reason: str):
        from ..utils.errors import AllowlistError

        raise AllowlistError(resource, f"{reason} ({self.allowlist.describe()})")

    def _account_of(self, pid: str) -> Optional[str]:
        return self.cache.lookup(pid)

    def _property_allowed(self, pid: str, looked_up: Optional[list] = None) -> bool:
        if self.allowlist.lists_property(pid):
            return True

        def account_of() -> Optional[str]:
            account = self._account_of(pid)
            if looked_up is not None:
                looked_up.append(account)
            return account

        return self.allowlist.allows_property(pid, account_of)

    def _check_ref(self, kind: str, ref_id: str) -> None:
        resource = f"{kind}/{ref_id}"
        if kind == "accounts":
            if not self.allowlist.allows_account(ref_id):
                self._deny(resource, f"{resource} is not on the allowlist for account-level calls")
            return
        looked_up: list = []
        if not self._property_allowed(ref_id, looked_up):
            if looked_up == [None]:
                self._deny(
                    resource,
                    f"{resource} is not visible to these credentials or not on the allowlist",
                )
            self._deny(resource, f"{resource} is not on the allowlist")

    def _check(self, uri: str, method: str, body: Any, headers: Optional[dict]) -> Route:
        route = classify_route(method, uri)
        if route is Route.DISCOVERY:
            return route
        parts = urlsplit(uri)
        if route is Route.UNKNOWN_HOST:
            self._deny(parts.hostname or uri, f"request to unexpected host {parts.hostname!r}")
        if any(k.lower() == "x-http-method-override" for k in (headers or {})):
            self._deny(parts.path, "request overrides its HTTP method; can't check the allowlist")
        try:
            refs = extract_refs(uri, body)
        except UnverifiableError as e:
            self._deny(parts.path, f"can't check the allowlist: {e}")

        if route is Route.PROPERTIES_LIST and refs and all(k == "accounts" for k, _ in refs):
            if len(refs) == 1:
                (_, aid), = refs
                if not self._account_listable(aid):
                    self._deny(f"accounts/{aid}", f"accounts/{aid} is not on the allowlist")
                return route

        if route is Route.CHANGE_HISTORY:
            aid = _CHANGE_HISTORY.fullmatch(parts.path).group(1)
            if not self.allowlist.allows_account(aid):
                pid = change_history_property(body)
                if (
                    pid is None
                    or not refs <= {("accounts", aid), ("properties", pid)}
                    or not self._property_allowed(pid)
                    or self._account_of(pid) != aid
                ):
                    self._deny(
                        f"accounts/{aid}",
                        f"accounts/{aid} is not on the allowlist; pass an allowed "
                        "--property-id to search one property's change history",
                    )
                return route

        if not refs:
            if route in (Route.ACCOUNTS_LIST, Route.ACCOUNT_SUMMARIES_LIST):
                return route
            self._deny(
                parts.path,
                "request names no account or property; can't check the allowlist",
            )
        for kind, ref_id in sorted(refs):
            self._check_ref(kind, ref_id)
        return route

    def _account_listable(self, aid: str) -> bool:
        """Properties of ``aid`` may be listed: account allowed, or one of its properties is."""
        if self.allowlist.allows_account(aid):
            return True
        prop_map = self.cache.prop_map(self.allowlist.listed_properties())
        return any(
            a == aid and self.allowlist.allows_property(p, lambda a=a: a)
            for p, a in prop_map.items()
        )

    # -- response filters -----------------------------------------------------

    def _filter(self, route: Route, content: Any, uri: str) -> Any:
        """Drop disallowed items from a list response. Idempotent; keeps other keys."""
        raw = content.decode("utf-8") if isinstance(content, bytes) else content
        try:
            data = json.loads(raw)
        except (ValueError, TypeError, UnicodeDecodeError):
            return content
        if not isinstance(data, dict):
            return content

        if route is Route.PROPERTIES_LIST:
            account = _filter_account(uri)
            if "properties" in data:
                data["properties"] = [
                    p for p in data["properties"] or []
                    if isinstance(p, dict) and self._listed_property_allowed(p, account)
                ]
        elif route is Route.ACCOUNTS_LIST:
            visible = self._visible_accounts()
            if "accounts" in data:
                data["accounts"] = [
                    a for a in data["accounts"] or []
                    if isinstance(a, dict) and _id_of(a.get("name"), "accounts") in visible
                ]
        elif "accountSummaries" in data:
            # Each summary carries its own properties, so no cache lookup is needed
            data["accountSummaries"] = [
                s for s in data["accountSummaries"] or []
                if isinstance(s, dict) and self._filter_summary(s)
            ]

        out = json.dumps(data)
        return out.encode("utf-8") if isinstance(content, bytes) else out

    def _listed_property_allowed(self, prop: dict, account: Optional[str]) -> bool:
        """``account``: the one the request's filter scoped the listing to, if known."""
        pid = _id_of(prop.get("name"), "properties")
        if pid is None:
            return False
        if account is None:
            return self._property_allowed(pid)
        return self.allowlist.allows_property(pid, lambda: account)

    def _filter_summary(self, summary: dict) -> bool:
        """Drop disallowed properties from ``summary``; False if the account is hidden."""
        aid = _id_of(summary.get("account"), "accounts")
        if aid is None:
            return False
        props = [
            p for p in summary.get("propertySummaries") or []
            if isinstance(p, dict)
            and (pid := _id_of(p.get("property"), "properties")) is not None
            and self.allowlist.allows_property(pid, lambda: aid)
        ]
        if "propertySummaries" in summary:
            summary["propertySummaries"] = props
        return bool(props) or self.allowlist.allows_account(aid)

    def _visible_accounts(self) -> set[str]:
        if all(s.properties is None for s in self.allowlist.sources):
            # Account-only allowlist: no property can add an account, so no lookup needed
            return set(self.allowlist.allowed_accounts() or ())
        return self.allowlist.visible_accounts(
            self.cache.prop_map(self.allowlist.listed_properties())
        )


def _filter_account(uri: str) -> Optional[str]:
    """The account in a properties list's ``filter=parent:accounts/N``, if that is the
    whole filter. The server then returns only that account's properties."""
    filters = [v for k, v in parse_qsl(urlsplit(uri).query, keep_blank_values=True)
               if k == "filter"]
    m = _PARENT_FILTER.fullmatch(filters[0]) if len(filters) == 1 else None
    return m.group(1) if m else None


def _id_of(name: Any, kind: str) -> Optional[str]:
    if isinstance(name, str):
        m = re.fullmatch(rf"{kind}/([0-9]+)", name)
        if m:
            return m.group(1)
    return None
