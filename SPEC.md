# Spec: Account and property allowlist

Status: **Implemented: pending release** (branch `feat/allowlist`)
Target version: 0.6.0
Previous spec (output escaping and input validation, shipped in 0.5.0): `git show 225822f:SPEC.md`

---

## Objective

Let a user pin `ga` to a set of GA4 accounts and/or properties, so that a stray `-p`, a wrong
default, or an agent working on behalf of one client can't read or change another client's data.

Users: analysts in a terminal who work across many client accounts with one Google login, and AI
agents running `ga` non-interactively. Today the only limit is whatever the credential can see.
`default_account_id` / `default_property_id` are only defaults, and any flag overrides them
(`config/store.py::get_effective_value`).

This is a **client-side guardrail, not a security boundary.** Any process holding the token can
call the API directly, edit `config.json`, point `GA_CLI_CONFIG_DIR` somewhere else, or fake a
TTY (`script`, `expect`) to get past the interactive-only config change. An env-only allowlist is
advisory: the agent's shell can drop the variable. The file allowlist is the fence, and env narrows
it per session. For a hard boundary, use a service account that is only granted access to the
allowed accounts (`--service-account` already works). The README documents this.

What it does protect against: a wrong `-p` or default, and a well-meaning agent that wanders into
another client's account. Filtering the list endpoints also keeps other clients' account and
property names out of an agent's context.

| # | Requirement |
|---|---|
| R1 | Opt-in: with no allowlist configured, API behaviour and command output are byte-identical to 0.5.0, except for three intended additions: `ga config get` lists the two new keys as `null`, `ga auth status` adds `"allowlist": {"enabled": false}`, and `--describe`/`--help` list `ga allowlist` |
| R2 | When configured, every Admin/Data API request is checked **before it is sent**, for all 4 clients and all ~30 command groups, without per-command code |
| R3 | Fails closed: if the CLI can't prove a request is allowed, it doesn't send it |
| R4 | Top-level list endpoints (`accounts`, `accountSummaries`, `properties`) return only allowed items |
| R5 | Denials have their own exit code (5) and category (`allowlist_error`) |
| R6 | An agent can't widen its own allowlist through the CLI: no flag, no non-interactive config change, env can only narrow |
| R7 | `ga allowlist show` prints the active allowlist |

---

## Design

### Configuration

Two new keys in `config.json`, stored as JSON lists of numeric ID strings:

```json
{ "allowed_account_ids": ["123", "456"], "allowed_property_ids": ["250400352"] }
```

Two env vars, comma-separated: `GA_CLI_ALLOWED_ACCOUNTS`, `GA_CLI_ALLOWED_PROPERTIES`.
`accounts/123` / `properties/123` prefixes are accepted and normalised to the bare ID (the
prefix must match the key: `properties/123` in an accounts list is an error). A
non-numeric entry is an error (exit 5) as soon as the first API client is built.

**One source** = the file keys or the env vars. A source is configured if either of its two keys
is set. A key set to an empty list or an empty env string adds nothing, so a source whose keys
are all empty denies everything (fail closed).

**What a source allows:**
- *Property P* if `account(P) ∈ accounts` or `P ∈ properties`.
- *Account-level call on A* (e.g. `accounts get`, account access bindings, account access
  reports, data-sharing settings) only if `A ∈ accounts`. An allowed property does **not** grant
  account-level calls on its parent.

**Effective allowlist:** a request must be allowed by **every configured source**. With both file
and env set, that is the intersection, so a launcher can pin an agent to a subset by env, and an
agent setting env can't widen what the file allows. With no source configured, the guard is off.

New module `config/allowlist.py`:

```python
@dataclass(frozen=True)
class AllowlistSource:
    name: str                          # "config" | "env"
    accounts: frozenset[str] | None    # None = key not set
    properties: frozenset[str] | None

@dataclass(frozen=True)
class Allowlist:
    sources: tuple[AllowlistSource, ...]   # empty → guard off
    # account_of is only called when some source doesn't list pid directly
    def allows_property(self, pid: str, account_of: Callable[[], str | None]) -> bool: ...
    def allows_account(self, aid: str) -> bool: ...
    def visible_accounts(self, prop_map: dict[str, str]) -> set[str]: ...  # for list filtering

def load_allowlist() -> Allowlist: ...
```

`UserConfig` gets `allowed_account_ids` / `allowed_property_ids: Optional[list[str]]`, read in
`load_config`. `VALID_CONFIG_KEYS` lists them.

### Changing the allowlist (R6)

- `ga config set allowed_account_ids 123,456` parses the comma list and validates it like the env
  values.
- `set` / `unset` on either allowlist key, and `config reset` when an allowlist key is set,
  require an interactive terminal (`sys.stdin.isatty()`). They show old → new and ask
  `questionary.confirm(..., default=False)`. Without a TTY: `error("Allowlist settings can only be
  changed interactively")`, exit 1, file unchanged.
- `config setup` keeps the existing allowlist keys. Today it writes a fresh `UserConfig()`, which
  would silently wipe the allowlist.
- No CLI flag reads or overrides the allowlist.

### Enforcement at the HTTP layer (R2, R3)

New module `api/allowlist_guard.py`:

```python
class AllowlistHttp(google_auth_httplib2.AuthorizedHttp):
    def request(self, uri, method="GET", body=None, headers=None, **kwargs):
        ...check, then super().request(...), then filter the response if needed
```

`api/client.py` gets one helper used by all 4 getters:

```python
def _build(service: str, version: str, **kwargs) -> Resource:
    creds = _get_credentials()
    http = AllowlistHttp(creds, http=googleapiclient.http.build_http())
    return build(service, version, http=http, **kwargs)
```

`AllowlistHttp` is a pure passthrough when `load_allowlist()` has no sources (R1).

`build(http=…)` vs `build(credentials=…)` (checked against google-api-python-client 2.193):
- `build` skips `with_scopes()`. That's harmless because both credential types are already
  scoped: stored OAuth scopes, and service accounts built with `OAUTH_SCOPES`.
- `build` skips the mTLS endpoint switch, so `GOOGLE_API_USE_MTLS_ENDPOINT` can no longer
  change the host.
- The v1alpha data client's discovery fetch now goes through `AllowlistHttp`, with auth. It
  requests `www.googleapis.com/discovery/v1/apis/analyticsdata/v1alpha/rest` first, then
  `analyticsdata.googleapis.com/$discovery/rest?version=v1alpha` on a 404.

**Per-request check:**

1. **Passthrough:** only `GET`s of the two discovery URL shapes above. Any other host is
   **denied**. Only the 4 GA clients use `AllowlistHttp`, so an unexpected host is a bug, not
   something to wave through.
2. **Extract references** (`accounts/{digits}`, `properties/{digits}`) from:
   - the **percent-decoded** URI path, and each URL-decoded query value (`properties list`
     sends `filter=parent%3Aaccounts%2F123`). In the path, an ID must be followed by `/`, `:`
     or the end of the path. Anything else is denied. googleapiclient's pattern check
     (`^properties/[^/]+$`) rejects `-p 123/../999` but sends `-p 123%2F..%2F999` as is, so
     the raw path would otherwise yield only `properties/123`;
   - the JSON body, recursively: every string value that **starts with** `accounts/N` or
     `properties/N`. This covers `parent` on create, `property` in change-history bodies and any
     nested request lists, including future ones. A report filter value that literally starts
     with `properties/123` would also be checked; that is an accepted fail-closed false positive.
   - A body that isn't JSON, a body with duplicate keys, an ID followed by anything other than
     `/`, `:` or the end (including a trailing newline), a `.`/`..` path segment, and an
     `X-HTTP-Method-Override` header all make the request unverifiable, so it is denied. These
     are cases where the server might read the request differently from the guard.
3. **Check every reference.** A property listed directly in every source's `properties` is
   allowed without a lookup, so the common agent setup (`GA_CLI_ALLOWED_PROPERTIES=…`) never
   touches the cache or makes an extra API call. Otherwise `account(P)` comes from the
   allowlist cache (below).
   Two routes are checked per property despite an account in the URI:
   - `GET …/properties?filter=parent:accounts/A`: allowed if `allows_account(A)`, or if any
     allowed property belongs to A. The first clause matters for an allowed account with no
     properties yet, which must list as empty and not exit 5. The response is filtered.
   - `POST …/accounts/A:searchChangeHistoryEvents`: allowed if `A` passes `allows_account`, **or**
     the body's `property` is allowed and belongs to A.
4. **No references at all:** allowed only for the known top-level list routes
   `GET /v1{alpha,beta}/accounts` and `GET /v1{alpha,beta}/accountSummaries`, whose responses are
   filtered. Anything else (`accounts:provisionAccountTicket`, a future `/batch` endpoint, an
   unknown route) is **denied**: "request names no account or property; can't check the
   allowlist".
5. **Denied** → raise `AllowlistError(resource="properties/999", reason=…)`. Nothing is sent.
   The exception propagates out of `.execute()` into each command's existing
   `except Exception: handle_error(e)`. `AllowlistError` must not subclass `OSError` or
   `RuntimeError`. googleapiclient's `_retry_request` retries the `OSError` family, and
   `classify_error` maps a `RuntimeError` whose message mentions auth to `auth_error`.

**401 retry re-enters the guard.** `AuthorizedHttp.request` handles a 401 by refreshing and
calling `self.request(…, _credential_refresh_attempt=n)`, which is `AllowlistHttp.request` again.
So `AllowlistHttp.request` passes `**kwargs` through unchanged, and the check and the filters
must be idempotent. A filtered body may be filtered a second time.

**Response filtering (R4):** only on 2xx with a JSON body. `nextPageToken` is kept, so
`utils/pagination.py::paginate_all` keeps working when a page filters to empty. A property's
account never comes from its `parent` field: `Property.parent` and `PropertySummary.parent` can be
`properties/N` for subproperties. It comes from the request or the response where that settles
it, otherwise from the cache map:
- a `properties` list whose whole filter is `parent:accounts/A` only returns A's properties, so
  each takes A;
- an `accountSummaries` item lists its own properties, so each takes the summary's `account`.

| Route | Kept |
|---|---|
| `accounts` list | accounts with an account-level allow, or with ≥1 allowed property |
| `accountSummaries` list | same accounts, judged from each summary; `propertySummaries[]` filtered to allowed properties |
| `properties` list | allowed properties |

### Property → account cache

`~/.config/ga-cli/allowlist-cache.json` (`constants.get_allowlist_cache_path()`):

```json
{ "principal": "<key>", "fetched_at": 1760000000,
  "properties": { "250400352": "123" }, "names": { "250400352": "Shop CH" },
  "account_names": { "123": "Client CH" } }
```

- Built from one paginated `accountSummaries.list` (pageSize 200). Each property maps to the
  `account` of the `AccountSummary` it sits in, not to its `parent`. The refresh goes through a
  **separate plain** `AuthorizedHttp(self.credentials, http=self.http)`, for example a second
  v1beta admin client built on it. It must not use `super().request`, because that method's
  401 retry calls `self.request` and re-enters the guard mid-refresh. It must not use `self.http`
  either, because that sends no auth header.
- `principal` = the service-account email, or a short SHA-256 of the OAuth refresh token. A
  mismatch counts as a miss, so switching login never reuses another identity's map. `ga auth
  login` / `logout` delete the file.
- TTL 1 hour (`ALLOWLIST_CACHE_TTL_SECONDS`). Only loaded when the guard is on and a check needs
  `account(P)`, or a list response needs filtering.
- An unknown property triggers **one** refresh per process. If it is still unknown, the request
  is denied ("not visible to these credentials or not on the allowlist"). The same rule applies
  when an `accounts` or `properties` list, or `ga allowlist show`, reads the whole map and a
  directly listed property is missing from it, e.g. one created and allowlisted since the cache
  was written.
- If the refresh itself fails (network, 401), the original error propagates (network/auth exit
  code). The guarded request is not sent, and a later call in the same process tries again.
- `properties create` adds a property the cache doesn't know yet. The refresh-once rule covers
  follow-up calls on it.

### Errors (R5)

`utils/errors.py`:
- `class AllowlistError(Exception)` with `resource` and `reason`.
- `classify_error`: checked **first** → `(5, "allowlist_error")`. Docstring exit-code table
  updated.
- `handle_error` JSON payload adds `"resource"` for `AllowlistError`:

```json
{"error": true, "exit_code": 5, "category": "allowlist_error",
 "resource": "properties/999", "message": "properties/999 is not on the allowlist (config: accounts 123). Run 'ga allowlist show' for the allowed properties; only the user can change the allowlist."}
```

The second sentence is for agents. Their usual reaction to an error is to try to fix it
(`ga auth login`, `ga config set …`). The message tells them to stop and ask instead.

### `ga allowlist show` (R7)

New `commands/allowlist_cmd.py`, registered in `main.py` as `allowlist`. Output follows
`resolve_output_format` (table in a terminal, JSON on a pipe):

```json
{ "enabled": true,
  "sources": { "config": {"accounts": ["123"], "properties": null},
               "env": null },
  "effective": { "accounts": ["123"],
                 "properties": [{"id": "250400352", "account": "123", "displayName": "Shop CH"}] },
  "cache": { "fetched_at": "2026-10-13T10:00:00Z", "age_seconds": 412 } }
```

It refreshes a stale cache. With the guard off it prints `{"enabled": false}` and makes no API
call. `ga auth status` gains `"allowlist": {"enabled": bool}`, read from config/env only (no
network).

### Docs

- `commands/agent_cmd.py`: an "Allowlist" section covering exit code 5 / `allowlist_error`, that the
  allowlist can't be changed non-interactively, and `ga allowlist show` to discover the allowed
  properties. The guide has **no exit-code section today**; the only table is the
  `classify_error` docstring. So add an "Errors and exit codes" section listing all of 1–5 with
  their categories, not only 5.
- README: setup, env-intersection semantics, the "not a security boundary" note, and the
  dedicated service-account pattern. Add `GA_CLI_ALLOWED_ACCOUNTS` / `GA_CLI_ALLOWED_PROPERTIES`
  to the "Environment Variables" table.

### Deferred

- Dry-run (`utils/dry_run.py`) sends no request, so it isn't checked. A follow-up can add a
  `"allowed"` hint.
- Read-only vs write allowlists, named contexts (profiles that bundle credentials, defaults and
  an allowlist), and display-name input for `-p` (`-p "Shop CH"`). These build on this cache later.

---

## Commands

```bash
uv run pytest                          # full suite
uv run pytest tests/test_allowlist.py tests/test_allowlist_guard.py tests/test_config_cmd.py tests/test_errors.py -q
uv run ruff check src/ tests/
GA_CLI_ALLOWED_PROPERTIES=250400352 uv run ga reports run -p 250400352 …   # live, read-only
```

## Project structure (files touched)

```
src/ga_cli/config/allowlist.py       → new: Allowlist, load_allowlist, env/file parsing
src/ga_cli/config/store.py           → UserConfig fields, VALID_CONFIG_KEYS
src/ga_cli/config/constants.py       → get_allowlist_cache_path, ALLOWLIST_CACHE_TTL_SECONDS
src/ga_cli/api/allowlist_guard.py    → new: AllowlistHttp, reference extraction, filters, cache
src/ga_cli/api/client.py             → _build helper; all 4 getters use AllowlistHttp
src/ga_cli/utils/errors.py           → AllowlistError, exit 5, payload "resource"
src/ga_cli/commands/config_cmd.py    → list parsing, TTY + confirm, setup keeps the allowlist
src/ga_cli/commands/allowlist_cmd.py → new: ga allowlist show
src/ga_cli/commands/auth_cmd.py      → allowlist field in status; login/logout clear cache
src/ga_cli/commands/agent_cmd.py, README.md, src/ga_cli/main.py
pyproject.toml                       → declare google-auth-httplib2 + httplib2 (imported directly)
tests/conftest.py                    → autouse: delenv GA_CLI_ALLOWED_ACCOUNTS / _PROPERTIES
tests/test_allowlist.py, tests/test_allowlist_guard.py, tests/test_allowlist_cmd.py (new);
tests/test_api_client.py, test_config_cmd.py, test_errors.py, test_auth_cmd.py (extended)
```

The `conftest.py` change keeps a developer's own `GA_CLI_ALLOWED_*` from leaking into the
suite, the same way `GA_CLI_CONFIG_DIR` is already isolated.

## Code style

Match the surrounding code: short docstrings, comments only where the *why* isn't obvious,
class-grouped pytest tests, nothing new to install. `google-auth-httplib2` and `httplib2` are
already in `uv.lock` through google-api-python-client. Because `allowlist_guard.py` imports them
directly, `pyproject.toml` declares them too. Expected guard test shape, using real
discovery-built clients over `googleapiclient.http.HttpMockSequence`, which records what it
was sent in `request_sequence`:

```python
class TestPropertyAllowlist:
    def test_property_not_on_allowlist_is_not_sent(self, guarded_admin, http_seq):
        with pytest.raises(AllowlistError) as exc:
            guarded_admin.properties().get(name="properties/999").execute()
        assert exc.value.resource == "properties/999"
        assert http_seq.request_sequence == []
```

## Testing strategy

- **TDD**, one layer at a time: `Allowlist` resolution → reference extraction → `AllowlistHttp`
  allow/deny → response filters → cache → CLI surface.
- `test_allowlist.py`: file only, env only, both (intersection), empty env = deny all, invalid ID,
  `accounts/` prefix normalisation, property-only source denies account-level.
- `test_allowlist_guard.py`: real clients for all 4 APIs built with `http=AllowlistHttp(...)` over a
  mocked inner http (v1alpha data discovery fed from `.api-snapshots/`). Cases: allowed/denied
  path, query `filter=parent:`, body `parent` on create, change history with/without body
  `property`, batch/funnel bodies, discovery passthrough (both URL shapes), unknown host denied,
  `%2F` in a path ID denied, route naming no account or property denied, directly listed
  property needs no cache, `properties list` on an allowed account with no properties returns
  empty, list filtering
  keeps `nextPageToken`, subproperty (`parent: properties/N`) mapped to its account, 401 →
  refresh → retry still guarded, cache miss → single refresh → deny, TTL expiry, principal
  mismatch, guard off = request sent unchanged.
- CLI via `CliRunner`: non-TTY `config set allowed_account_ids` → exit 1, file unchanged; TTY +
  confirm → saved; `config setup` keeps the allowlist; denied command → exit 5 with JSON payload
  on a pipe; `ga allowlist show` on and off.
- Existing tests keep passing. `test_api_client.py` assertions on `build(credentials=…)` change
  to `http=`.
- Live, read-only on 250400352: allowlisted alone, `reports run` works and `accounts list` /
  `account-summaries list` show only its account. Allowlisting another property, `reports run -p
  250400352` exits 5.

## Boundaries

- **Always:** fail closed when the allowlist check can't be completed; no request sent before
  the check; run `pytest` and `ruff` before each commit; byte-identical behaviour with no
  allowlist configured.
- **Ask first:** adding new exit codes beyond 5, changing existing output for users without an
  allowlist beyond the three additions in R1, making the guard default-on, any write-path live test,
  adding dependencies beyond declaring the two already-locked ones.
- **Never:** a CLI flag that bypasses or widens the allowlist; letting env widen the file allowlist;
  describing the guardrail as a security boundary; push to master directly.

## Success criteria

1. With no allowlist configured, the full existing suite passes unchanged, apart from the
   `test_api_client` build-call assertions and any test that snapshots `config get` or
   `auth status` output (R1 additions).
2. Every request built by the 4 clients to a property/account not on the allowlist raises
   `AllowlistError` before any bytes are sent. Tested per client.
3. `accounts list`, `account-summaries list` and `properties list` show only allowed items.
4. A denial exits 5. On a pipe, stderr carries `"category": "allowlist_error"` and `"resource"`.
5. `echo y | ga config set allowed_account_ids 1` (non-TTY) is refused, and the file is unchanged.
6. `GA_CLI_ALLOWED_ACCOUNTS` can narrow but not widen a file-configured allowlist.
7. `ga allowlist show` reports sources, effective properties and cache age.
8. Suite and ruff pass on Python 3.10, 3.12 and 3.13 in CI.

## Decisions

1. **Enforcement point:** HTTP layer (`AllowlistHttp`), not per command.
2. **Env vs file:** intersection; env can only narrow.
3. **Property-only allowlist:** no account-level calls on the parent account; list results filtered.
4. **Unknown routes, and routes naming no account or property:** denied (fail closed).
5. **Exit code:** 5, category `allowlist_error`.
6. **Delivery:** one PR on `feat/allowlist`, one commit per layer.
7. **Name:** "allowlist", not "scope". Here "scope" already means OAuth scopes
   (`has_scope()`, and the "insufficient authentication scopes" 403 → `auth_error`) and
   custom-dimension `--scope`. An agent seeing a "scope" error would likely run `ga auth login`.
   The category is `allowlist_error`, matching the other `*_error` categories. It also covers
   a malformed allowlist, not only a denied resource.
8. **Unreadable `config.json`:** if the file exists but isn't a valid JSON object, `ga` can't
   tell whether it holds an allowlist, so every API request is denied (exit 5), and `ga config`
   refuses to overwrite the file. This applies even to users who never set an allowlist, and is
   the one exception to R1. Before, the file loaded as empty defaults, which turned the guard off,
   and the next `ga config set` saved over it and dropped the allowlist. `config.json` is now
   written atomically, so a crash can't leave a truncated file.
