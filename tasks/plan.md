# Implementation Plan: Account and property allowlist

Companion to [SPEC.md](../SPEC.md). Branch `feat/allowlist`, one PR, one commit per
task. Targets 0.6.0. Previous plan (output escaping and validation): `git show 225822f:tasks/plan.md`.

## Overview

Add an opt-in allowlist of accounts/properties, enforced in one place: a guarded
`AuthorizedHttp` (`AllowlistHttp`) that all 4 API clients send through. It blocks requests for
anything not on the allowlist before they're sent, filters the top-level list endpoints, and
denies anything it can't place. The CLI surface is small: config keys that can only be changed
interactively, `ga allowlist show`, and exit code 5 / `allowlist_error`.

## Architecture decisions

- **Pure logic first, HTTP last.** `config/allowlist.py` (resolution) and the reference
  extraction / route classification in `api/allowlist_guard.py` are pure functions with no I/O, so
  most of the behaviour is unit-tested without mocks. `AllowlistHttp.request` only wires them
  together.
- **One `_build` helper in `api/client.py`.** All 4 getters call
  `build(service, version, http=AllowlistHttp(creds, http=build_http()), …)`. With no allowlist
  configured, `AllowlistHttp` delegates straight to `AuthorizedHttp.request`, so 0.5.0 behaviour
  is unchanged (R1).
- **The cache lookup uses a separate plain `AuthorizedHttp`.** `accountSummaries.list` for the
  property → account map goes through `AuthorizedHttp(creds, http=self.http)`. It does not use
  `super().request`, whose 401 retry calls `self.request` and would re-enter the guard. The
  cache is lazy. It is only loaded when a check needs `account(P)` (a property listed directly
  in every source needs no lookup), or when a list response needs filtering.
- **`AllowlistError` is its own exception class** (not `RuntimeError`, not `OSError`), and
  `classify_error` checks it first. That keeps the "auth in message → auth_error" heuristic
  from catching it, and stops googleapiclient's `_retry_request` from retrying it.
- **Tests use real discovery-built clients** over `googleapiclient.http.HttpMockSequence` as
  the inner http, with mock credentials. This shows that the URIs googleapiclient actually
  produces (encoding, `{+name}` expansion, query params) are parsed correctly. v1alpha data
  discovery is served from `.api-snapshots/`.

## Dependency graph

```
T1 AllowlistError / exit 5 ──► T2 config/allowlist.py ─┬─► T3 reference extraction ─┐
                                                       ├─► T4 account cache ────────┴─► T5 AllowlistHttp ─► T6 list filtering
                                                       ├─► T7 config_cmd (TTY, setup keeps allowlist)
                                              T4 ──────┴─► T8 ga allowlist show / auth status / cache clear
                                                           all ─► T9 docs ─► T10 PR
```

T7 and T8 don't depend on the guard and can go in any order after their deps. They are
scheduled after Checkpoint A so the risky part (T3–T6) is proven first.

## Task list

### Phase 0: Branch

#### Task 0: Branch and commit spec + plan
**Acceptance criteria:**
- [ ] `feat/allowlist` created from master
- [ ] `docs: spec and plan for the allowlist` commit with SPEC.md and tasks/

**Scope:** XS · **Deps:** none

### Phase 1: Foundations (no network)

#### Task 1: `AllowlistError` and exit code 5
**Acceptance criteria:**
- [ ] `utils/errors.py::AllowlistError(resource, reason)`, a plain `Exception` subclass (not
      `RuntimeError`/`OSError`)
- [ ] `classify_error(AllowlistError(...)) == (5, "allowlist_error")`, checked before every
      other branch. The docstring exit-code table lists 5
- [ ] `handle_error` JSON payload adds `"resource"`. Terminal mode prints the message. The
      message ends with the "Run 'ga allowlist show' … only the user can change the allowlist"
      hint
- [ ] Existing classification tests unchanged

**Verification:** `uv run pytest tests/test_errors.py -q`

**Files:** `src/ga_cli/utils/errors.py`, `tests/test_errors.py` · **Scope:** XS · **Deps:** none

#### Task 2: Allowlist configuration and resolution
**Acceptance criteria:**
- [ ] `UserConfig` has `allowed_account_ids` / `allowed_property_ids: Optional[list[str]]`,
      read by `load_config` and listed in `VALID_CONFIG_KEYS`. Configs without them still load
- [ ] `config/allowlist.py`: `parse_ids()` accepts `123`, `accounts/123` and `properties/123`
      (whitespace and trailing commas tolerated) and rejects non-numeric entries with
      `AllowlistError`
- [ ] `load_allowlist()` builds `config` and `env` sources (`GA_CLI_ALLOWED_ACCOUNTS`,
      `GA_CLI_ALLOWED_PROPERTIES`). A source counts as configured if either key is set. An empty
      key adds nothing, so a source whose keys are all empty denies everything
- [ ] `allows_property` / `allows_account` require **every** configured source. A
      property-only source allows no account-level calls. With no sources, the guard is off
- [ ] A property listed directly in every source resolves **without** an account lookup (the
      API takes the lookup as a lazy callable, or something similar)
- [ ] `visible_accounts(prop_map)` returns accounts with an account-level allow or at least one
      allowed property
- [ ] `tests/conftest.py` autouse fixture removes `GA_CLI_ALLOWED_ACCOUNTS` / `_PROPERTIES`

**Verification:** `uv run pytest tests/test_allowlist.py -q`. Cases: file only, env only,
intersection (env narrows, env can't widen), empty env, invalid ID, prefix normalisation,
property-only source, direct hit never calls the lookup.

**Files:** `src/ga_cli/config/allowlist.py` (new), `src/ga_cli/config/store.py`,
`tests/test_allowlist.py` (new), `tests/conftest.py` · **Scope:** S · **Deps:** T1

### Phase 2: The guard

#### Task 3: Reference extraction and route classification
**Acceptance criteria:**
- [ ] `extract_refs(uri, body) -> set[tuple[kind, id]]` collects references from the
      percent-decoded path, the URL-decoded query values (`filter=parent:accounts/123`) and,
      recursively, the JSON body strings that **start with** `accounts/N` or `properties/N`.
      `bytes`/`str`/`None` bodies are handled, and a non-JSON body adds nothing
- [ ] A path ID not followed by `/`, `:` or the end (e.g. `properties/123%2F..%2F999`) makes
      the request unverifiable, so it is denied
- [ ] `classify_route(method, uri) -> Route` recognises: discovery (`GET`
      `www.googleapis.com/discovery/v1/apis/…` and `…/$discovery/rest`), `accounts` list,
      `accountSummaries` list, `properties` list, `searchChangeHistoryEvents`, generic (GA
      hosts), and unknown host (denied)
- [ ] Table-driven tests over the URIs the real clients build. Capture them with
      `HttpMockSequence` for one representative call per command group (property get, data
      stream create, runReport, batchRunReports, runFunnelReport, chat, access bindings
      account+property, access report account+property, change history, properties
      create/list)

**Verification:** `uv run pytest tests/test_allowlist_guard.py -q -k "Extract or Route"`

**Files:** `src/ga_cli/api/allowlist_guard.py` (new), `tests/test_allowlist_guard.py` (new) ·
**Scope:** S · **Deps:** T2

#### Task 4: Property → account cache
**Acceptance criteria:**
- [ ] `constants.get_allowlist_cache_path()` and `ALLOWLIST_CACHE_TTL_SECONDS = 3600`
- [ ] `AllowlistCache.lookup(pid)` returns the account ID. It loads from disk when the principal
      matches and the entry is younger than the TTL. Otherwise it refreshes **once per process**
      through a separate plain `AuthorizedHttp(creds, http=inner)`, paginating
      `accountSummaries.list` with pageSize 200
- [ ] Each property maps to its enclosing `AccountSummary.account`, never to
      `propertySummaries[].parent`, which is `properties/N` for subproperties
- [ ] Still unknown after a refresh → `None` (the caller denies). A refresh that fails raises the
      original error, so `classify_error` gives network/auth
- [ ] Principal = service-account email, or `sha256(refresh_token)[:16]` for OAuth. A mismatch
      counts as a miss
- [ ] Written atomically (temp file + `os.replace`). A corrupt file counts as a miss
- [ ] Also stores display names, for `ga allowlist show`

**Verification:** `uv run pytest tests/test_allowlist_guard.py -q -k Cache`. Cases: fresh hit,
stale → refresh, miss → single refresh → None, second miss in the same process makes no second
call, principal mismatch, corrupt file, refresh failure propagates, subproperty mapped to its
account.

**Files:** `src/ga_cli/api/allowlist_guard.py`, `src/ga_cli/config/constants.py`,
`tests/test_allowlist_guard.py` · **Scope:** M · **Deps:** T1, T2

#### Task 5: `AllowlistHttp` enforcement and client wiring
**Acceptance criteria:**
- [ ] `AllowlistHttp(AuthorizedHttp).request` with no allowlist is a pure passthrough: same args to
      `super().request`, response untouched
- [ ] With an allowlist: passthrough routes are sent, and every extracted reference is checked. A
      denial raises `AllowlistError` and **nothing reaches the inner http**
- [ ] Special routes: `properties` list with `parent:accounts/A` is allowed if
      `allows_account(A)` or A has an allowed property, so an allowed account with no
      properties lists as empty. Change history is allowed if the account passes, or the body
      `property` is allowed and belongs to A
- [ ] A request with no references that isn't a top-level list route is denied. So is a
      request to an unknown host
- [ ] A property listed directly in every source is checked without loading the cache (assert
      no `accountSummaries` call)
- [ ] `**kwargs` (`redirections`, `connection_type`, `_credential_refresh_attempt`) are passed
      through. A 401 → refresh → retry is checked again and still sends nothing that isn't
      allowed
- [ ] `api/client.py::_build` is used by all 4 getters. `static_discovery=False` is kept for
      data v1alpha. `clear_client_cache` is unchanged
- [ ] `pyproject.toml` declares `google-auth-httplib2` and `httplib2`. `uv.lock` only gains
      the direct-dependency markers, no version changes
- [ ] `test_api_client.py` updated for `http=`. The rest of the suite passes unchanged

**Verification:** `uv run pytest tests/test_allowlist_guard.py tests/test_api_client.py -q`, then
the full suite. Per-client allow/deny tests using real built clients (admin v1beta, admin v1alpha,
data v1beta, data v1alpha).

**Files:** `src/ga_cli/api/allowlist_guard.py`, `src/ga_cli/api/client.py`, `pyproject.toml`,
`uv.lock`, `tests/test_allowlist_guard.py`, `tests/test_api_client.py` · **Scope:** M ·
**Deps:** T1, T3, T4

#### Task 6: List response filtering
**Acceptance criteria:**
- [ ] On a 2xx JSON response: `accounts` list keeps `visible_accounts`. `accountSummaries`
      keeps those accounts with `propertySummaries[]` filtered. `properties` list keeps allowed
      properties
- [ ] `nextPageToken` and every other top-level key are preserved. Non-2xx responses and non-JSON
      bodies are returned untouched
- [ ] Filters are idempotent: filtering an already filtered body changes nothing (the 401
      retry runs them twice). A property's account comes from the cache map, not `parent`
- [ ] `paginate_all` over a page that filters to empty still reaches the next page
- [ ] No filtering (and no cache load) when the guard is off

**Verification:** `uv run pytest tests/test_allowlist_guard.py -q -k Filter`. A CliRunner test of
`ga accounts list -o json` with an allowlist and a mocked two-page response.

**Files:** `src/ga_cli/api/allowlist_guard.py`, `tests/test_allowlist_guard.py` · **Scope:** S ·
**Deps:** T5

### Checkpoint A: guard works end to end
- [ ] `uv run pytest` and `uv run ruff check src/ tests/` pass
- [ ] Live, read-only, with `GA_CLI_ALLOWED_PROPERTIES=250400352`: `reports run -p 250400352`
      works. `accounts list` / `account-summaries list` show only its account.
      `properties get -p <another visible property>` exits 5 with `allowlist_error` on a pipe
- [ ] Live with `GA_CLI_ALLOWED_ACCOUNTS=<250400352's account>`: `accounts get` works, and the
      property-only allowlist above denies `accounts get` with exit 5
- [ ] Live: `reports funnel` (v1alpha, dynamic discovery) works when allowed
- [ ] Commits T1–T6 on the branch
- [ ] **Review with the human before Phase 3**

### Phase 3: CLI surface

#### Task 7: Allowlist keys in `ga config`
**Acceptance criteria:**
- [ ] `config set allowed_account_ids 123,accounts/456` stores `["123", "456"]`. Invalid IDs exit
      1, and the file is unchanged
- [ ] `set`/`unset` on allowlist keys, and `reset` while an allowlist key is set: with no TTY →
      `error("Allowlist settings can only be changed interactively")`, exit 1, file unchanged.
      With a TTY → shows old → new, then `questionary.confirm(default=False)`. Declining leaves
      the file unchanged
- [ ] `config setup` keeps the existing allowlist keys
- [ ] `config get` shows the lists (or `null` when unset, the one intended R1 addition).
      `config get allowed_account_ids` prints them comma-separated
- [ ] Other keys behave exactly as before

**Verification:** `uv run pytest tests/test_config_cmd.py -q` (monkeypatch `sys.stdin.isatty`
and `questionary.confirm`)

**Files:** `src/ga_cli/commands/config_cmd.py`, `src/ga_cli/config/store.py`,
`tests/test_config_cmd.py` · **Scope:** S · **Deps:** T2

#### Task 8: `ga allowlist show`, auth status, cache invalidation
**Acceptance criteria:**
- [ ] `commands/allowlist_cmd.py` with `show`, registered as `allowlist` in `main.py`. Output goes
      through `resolve_output_format`, in the shape given in SPEC (enabled, sources, effective
      properties with display names, cache age). With the guard off → `{"enabled": false}` and
      no API call
- [ ] A stale cache is refreshed. In table mode, a source/effective summary plus a property table
- [ ] `ga auth status` output gains `"allowlist": {"enabled": bool}` from config/env only, with no
      network call
- [ ] `ga auth login` / `logout` delete `allowlist-cache.json` (missing file is fine)
- [ ] `ga --describe` (root flag, `main.py`) lists `ga allowlist show`. `test_describe.py`'s
      group list includes `ga allowlist`

**Verification:** `uv run pytest tests/test_allowlist_cmd.py tests/test_auth_cmd.py -q`; live
`ga allowlist show | jq .effective`

**Files:** `src/ga_cli/commands/allowlist_cmd.py` (new), `src/ga_cli/main.py`,
`src/ga_cli/commands/auth_cmd.py`, `tests/test_allowlist_cmd.py` (new), `tests/test_auth_cmd.py`,
`tests/test_describe.py` · **Scope:** S · **Deps:** T2, T4

### Checkpoint B: feature complete
- [ ] Full suite and ruff pass
- [ ] Live: piping `echo y` into `ga config set allowed_account_ids 1` is refused. Setting it
      interactively in a real terminal works, and `ga allowlist show` reflects it
- [ ] Commits T7–T8 on the branch

### Phase 4: Docs and release prep

#### Task 9: Docs and spec status
**Acceptance criteria:**
- [ ] Agent guide (`agent_cmd.py`): an Allowlist section covering exit 5 / `allowlist_error`,
      `ga allowlist show`, that the allowlist can't be changed non-interactively (so the agent
      asks the user), and that list results may be filtered
- [ ] Agent guide: a new "Errors and exit codes" section with codes 1–5 and their categories.
      The guide has none today. Keep it in sync with the `classify_error` docstring
- [ ] README: setup (config + env), the intersection rule, property-only semantics, the
      "guardrail, not a security boundary" note (env-only is advisory, TTY can be faked), and
      the dedicated service-account pattern. Both env vars added to "Environment Variables"
- [ ] SPEC.md status → "Implemented: pending release". `tasks/todo.md` all checked
- [ ] `test_agent_cmd.py` still passes (update it if it snapshots the guide)

**Files:** `src/ga_cli/commands/agent_cmd.py`, `README.md`, `SPEC.md`, `tasks/todo.md` ·
**Scope:** S · **Deps:** T1–T8

#### Task 10: Open the PR
**Acceptance criteria:**
- [ ] Branch pushed and PR opened against master, each commit mapped to a task
- [ ] CI green on 3.10, 3.12 and 3.13
- [ ] **Merge only after the human says so.** No version bump or release in this PR

**Deps:** T9

### Checkpoint: complete
- [ ] All SPEC success criteria (1–8) met
- [ ] PR green and ready for review

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `build(http=…)` behaves differently from `build(credentials=…)` (timeouts, discovery fetch for v1alpha data) | High | `build_http()` is what googleapiclient uses internally. T5 runs the full suite, and Checkpoint A exercises `reports funnel` live |
| googleapiclient encodes the path or query in a form the extractor misses, so a reference is missed | High | T3 tests the URIs real clients build, not hand-written strings. With no extractable reference, a request is denied |
| False positive: a report filter value starting with `properties/N` is denied | Low | Accepted fail-closed behaviour, documented in SPEC. The message names the resource |
| An extra `accountSummaries` call slows the first allowlisted command, or users with many properties need several pages | Low | 1 h TTL on disk, pageSize 200, refresh at most once per process |
| A stale cache maps a moved property to its old account | Low | TTL. `ga allowlist show` displays the cache age. Login/logout clear it |
| `config setup` / `reset` wipe the allowlist | Med | T7 covers both explicitly |
| An agent bypasses the guard (edits the file, `GA_CLI_CONFIG_DIR`, direct API calls, a fake TTY via `script`) | Med | Not addressed, by design. Docs state "not a security boundary" and give the service-account pattern. The exit-5 message tells the agent to ask the user |
| A 401 retry re-enters `AllowlistHttp.request`, or the cache refresh goes through the guard | Med | The refresh uses a separate plain `AuthorizedHttp`. Check and filters are idempotent. T5 has a 401 → retry test |
| Percent-encoded path segments (`%2F`) hide a second property from the extractor | Low | The path is decoded before extraction, and an ID with an unexpected terminator is denied (T3) |
| Subproperties have `parent: properties/N`, so a `parent`-based lookup gets the account wrong | Low | The account always comes from the enclosing `AccountSummary` (T4, T6) |

## Open questions

- The account ID of test property 250400352, needed for the account-allowlist live checks. Look it
  up with `ga properties get -p 250400352` at Checkpoint A.
