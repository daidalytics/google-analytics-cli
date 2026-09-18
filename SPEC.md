# Spec: `ga reports chat` — GA4 Data API Chat Integration

Status: **Implemented — shipping in 0.3.0**
Target version: 0.3.0
API: `analyticsdata` v1alpha, revision `20260830` (GA announced by Google 2026-09-17)

---

## Objective

Expose the new `analyticsdata.properties.chat` method as a CLI command so users can ask
natural-language questions about a GA4 property and get answers rendered as prose and tables,
with multi-turn conversational context.

**Users:**
1. **Humans at a terminal** — ask ad-hoc questions without knowing metric/dimension API names.
   Want readable output and the ability to ask follow-ups.
2. **AI agents / scripts** — this CLI is deliberately agent-friendly (`ga agent guide`,
   `--describe`, `-o json`). Chat must be fully scriptable with explicit, reproducible state.

**Success looks like:** `ga reports chat "which pages lost the most traffic last week?"` returns a
useful answer in one command, and a follow-up question retains context.

### Assumptions

1. The `chat` method is available on properties the user already has access to — no separate
   allowlist or product enablement beyond the OAuth scope. **Confirmed 2026-09-18**, after
   Google's 2026-09-17 GA announcement for the endpoint.
2. Chat is a *read* operation. No `--dry-run` support (that helper is for mutative commands),
   no `--yes` confirmation.
3. `sessionId` is an opaque server-side handle. We never construct or parse it, only store and
   replay it.
4. Response `text` blocks may contain Markdown-ish formatting but we treat them as **plain text**
   for rendering safety (see Code Style).
5. Service-account auth for chat behaves like OAuth once the scope is present. **Unverified.**
6. The feature is alpha and may change; it is documented as alpha in help text.

---

## API Surface (from `.api-snapshots/analyticsdata_v1alpha.json`)

```
POST v1alpha/{+property}:chat        property: ^properties/[^/]+$
scope: https://www.googleapis.com/auth/analytics.chatbot.read     ← NEW
```

```jsonc
// ChatRequest
{ "userQuery": string,          // required
  "sessionId": string,          // optional — continues an existing conversation
  "returnPropertyQuota": bool } // optional

// ChatResponse
{ "sessionId": string,
  "blocks": [ { "text": string } | { "table": DataTable } ],
  "propertyQuota": { "tokensPerDay": QuotaStatus, "tokensPerHour": QuotaStatus } }

// DataTable
{ "headers": [ { "header": string, "dataType": string } ],
  "rows":    [ { "columns": [ { "value": string } ] } ] }
```

Notes that drive the design:
- `blocks` is an **ordered, heterogeneous** list. Order is meaningful — a text block usually
  introduces the table that follows it. Rendering must preserve order.
- `PropertyChatQuota` has only `tokensPerDay` / `tokensPerHour` — a **narrower** shape than the
  `PropertyQuota` that `_display_quota()` in `reports.py` handles today.
- Invalid session IDs are documented to **error**, not silently start a new session.

---

## Design Decisions

### 1. Placement: `ga reports chat`

All `analyticsdata` methods live under `reports` (`run`, `realtime`, `pivot`, `batch`, `funnel`,
`metadata`, `check-compatibility`). Chat joins them. No top-level `ga chat` — it would sit
confusingly next to `ga agent`, which is an unrelated static documentation group.

### 2. OAuth scope: add to defaults + pre-flight detection

`analytics.chatbot.read` is appended to `OAUTH_SCOPES`. **Existing stored credentials will not
have it** — a refresh token cannot gain scopes it was not granted. Every current user must re-run
`ga auth login`.

To avoid a bare 403, the command performs a **pre-flight scope check**: stored credentials record
their granted `scopes` (`credentials.py:45`), so we compare before making the request and fail with
an actionable message. A 403 from the API is also mapped to the same message as a backstop.

```
$ ga reports chat "top pages"
Error: Your saved credentials do not include the GA chat scope.
       Run 'ga auth login' to re-authenticate and grant it.
       (scope: https://www.googleapis.com/auth/analytics.chatbot.read)
```

Exit code 2 (`auth_error`), consistent with `classify_error()`.

> **Consent-screen caveat:** users bring their own GCP OAuth client. If their consent screen has an
> explicit scope list, they may need to add `analytics.chatbot.read` there. The setup docs in
> `auth_cmd.py:47` currently claim "No scopes need to be added manually" — that line needs review.

### 3. Session model: `--session-id`, `--continue`, `--interactive`

Three ways to thread context, in precedence order:

| Mechanism | Source of session ID | Use case |
|---|---|---|
| `--session-id ID` | Explicit flag | Scripts, agents, reproducible runs |
| `--continue` | Per-property cache on disk | Human follow-ups across invocations |
| `--interactive` | In-memory across REPL turns | Human conversation in one sitting |
| *(none)* | New session created by API | One-shot questions |

**Precedence:** `--session-id` beats `--continue`. Passing both is a `BadParameter` error, not a
silent win — ambiguity here is a user mistake worth surfacing.

**Cache design** (`~/.config/ga-cli/chat-sessions.json`, mode `0o600`):

```jsonc
{ "987654321": { "sessionId": "abc123", "updatedAt": "2026-09-01T10:00:00Z" } }
```

- **Keyed by property ID.** Switching properties must never resume the wrong conversation.
- Written after every successful call (one-shot and each REPL turn), so `--continue` picks up the
  most recent exchange regardless of how it happened.
- **Expiry handling:** if the API rejects the cached ID, clear that property's entry and tell the
  user plainly — never silently start a fresh session, which would produce a context-free answer
  to a follow-up question that looks like it worked.

```
$ ga reports chat --continue "break that down by country"
Error: The previous chat session has expired or is no longer valid.
       Starting fresh — re-run without --continue.
```

Naming note: `continue` is a Python keyword. The Typer parameter is `continue_session` with an
explicit `"--continue"` flag name. No `-c` short form — it means `--config` on `batch`/`funnel`.

### 4. Quota visibility

Chat is token-metered (`PropertyChatQuota` reports `tokensPerDay` / `tokensPerHour`), so it is
materially more expensive than a report. The flag is therefore **tri-state**:

```
--return-property-quota / --no-return-property-quota    default: None
```

- `None` in a one-shot call → `false`. Keeps scripted/agent output clean.
- `None` in `--interactive` → **`true`**. A user working through a multi-turn conversation should
  see consumption accumulate rather than discover it after hitting a limit.
- An explicit flag always wins, in both directions.

`PropertyChatQuota` is a narrower shape than the `PropertyQuota` handled by `_display_quota()`
(`reports.py:224`), which iterates five keys that do not exist here. Chat gets its own
`_display_chat_quota()` rather than reusing it.

In the REPL, quota renders once per turn as a dim single line:

```
[quota] tokens today: 1,240/10,000 · this hour: 180/1,000
```

### 5. Rendering

**`table` (default):** blocks rendered in order — text as wrapped prose, `DataTable` through the
existing `output()` table renderer. Session ID printed dimmed at the end so users can copy it.

```
Sessions grew 12% week over week, driven mainly by organic search.

┏━━━━━━━━━━━┳━━━━━━━━━┓
┃ pagePath  ┃ views   ┃
┡━━━━━━━━━━━╇━━━━━━━━━┩
│ /home     │ 4,210   │
│ /pricing  │ 1,884   │
└───────────┴─────────┘

Session: abc123
```

**`json`:** the raw `ChatResponse`, unmodified. Agents get `sessionId`, `blocks`, and
`propertyQuota` exactly as the API returned them. No transformation, no added keys.

**`compact`:** text blocks as plain lines; tables as tab-separated rows with a header row.
Session ID to stderr via `info()` so stdout stays pipeable.

---

## Commands

```bash
# One-shot
ga reports chat "how many users did we have last week?"
ga reports chat "top landing pages" -p 987654321 -o json

# Explicit session (scripts, agents)
ga reports chat "top pages last week"                  # prints Session: abc123
ga reports chat "now break that down by country" --session-id abc123

# Cached session (humans)
ga reports chat "top pages last week"
ga reports chat --continue "now break that down by country"

# Interactive REPL
ga reports chat --interactive
ga reports chat -i --continue        # resume the cached conversation in the REPL

# Quota
ga reports chat "..." --return-property-quota
```

### Signature

```
ga reports chat [QUERY]
  -p, --property-id TEXT        Property ID (numeric). Falls back to default_property_id.
      --session-id TEXT         Continue a specific chat session.
      --continue                Continue this property's most recent session.
  -i, --interactive             Start a multi-turn REPL.
      --return-property-quota / --no-return-property-quota
                                Show chat token quota. Defaults on in --interactive,
                                off for one-shot calls.
  -o, --output [table|json|compact]
```

**Validation:**
- `QUERY` required unless `--interactive`. Missing → `BadParameter`.
- `QUERY` with `--interactive` → allowed; used as the first turn.
- `--session-id` + `--continue` → `BadParameter`.
- Empty/whitespace-only `QUERY` → `BadParameter` (don't spend quota on a blank request).

### REPL behaviour

- Prompt via `questionary.text()`, consistent with `reports build`.
- `exit`, `quit`, empty input, Ctrl-C, and Ctrl-D all end the session cleanly.
- Session ID printed once on exit, not after every turn.
- Each turn re-renders through the same block renderer as one-shot.
- `-o json` + `--interactive` → each turn emits one JSON object (JSON Lines).

### Dev commands (unchanged)

```bash
pytest                          # Run tests
pytest tests/test_reports_chat.py -v
ruff check src/ tests/          # Lint
uv sync                         # Install dependencies
uv build                        # Build wheel + sdist
```

---

## Project Structure

```
src/ga_cli/
├── commands/reports.py         # MODIFY — add chat_cmd + block renderer
├── config/
│   ├── constants.py            # MODIFY — CHAT_SCOPE, OAUTH_SCOPES, get_chat_sessions_path()
│   └── chat_session.py         # NEW — per-property session cache
├── auth/credentials.py         # MODIFY — has_scope() helper
└── commands/agent_cmd.py       # MODIFY — document chat in the agent guide

tests/
├── test_reports_chat.py        # NEW — command behaviour, rendering, validation
└── test_chat_session.py        # NEW — cache read/write/clear/scoping
```

Rationale for `config/chat_session.py`: it is persisted state under the config directory,
matching `config/store.py`. It is not credentials, so it does not belong in `auth/`.

---

## Code Style

Follows existing `reports.py` conventions: module-level `_`-prefixed helpers, `try/except
typer.BadParameter: raise / except Exception: handle_error(e)`, `resolve_output_format()`,
`get_effective_value()` + `require_options()`.

```python
def _render_chat_blocks(blocks: list[dict], effective_format: str) -> None:
    """Render ChatResponse blocks in order: text as prose, tables as tables."""
    for block in blocks:
        text = block.get("text")
        if text:
            # markup=False: response text is model-generated and may contain
            # square brackets that Rich would otherwise parse as style tags.
            console.print(text, markup=False)
            continue

        table = block.get("table")
        if not table:
            continue

        headers = [h.get("header", "") for h in table.get("headers", [])]
        rows = []
        for row in table.get("rows", []):
            cells = row.get("columns", [])
            rows.append({
                name: cells[i].get("value", "") if i < len(cells) else ""
                for i, name in enumerate(headers)
            })

        if rows:
            output(rows, effective_format, columns=headers, headers=headers)
```

**Conventions this encodes:**
- `markup=False` on all API-sourced text — a response containing `[bold]` must not be
  interpreted as Rich markup.
- Defensive index guarding (`i < len(cells)`) matching `_transform_funnel_rows`, since alpha
  responses may return ragged rows.
- Blocks with neither `text` nor `table` (future block types) are skipped, not errors.

---

## Testing Strategy

`pytest` + `typer.testing.CliRunner`, class-based grouping, all API calls mocked via
`unittest.mock.patch`. `conftest.py`'s autouse `isolated_config_dir` keeps the session cache in
`tmp_path`. **No real API calls.**

`tests/test_reports_chat.py`:

| Class | Cases |
|---|---|
| `TestChatOneShot` | text-only response; mixed text+table; table renders headers and values; `-o json` passes the raw response through unchanged |
| `TestChatValidation` | missing query; empty/whitespace query; `--session-id` + `--continue` together; missing property ID |
| `TestChatSessionFlags` | `--session-id` is sent in the request body; no session flag omits `sessionId`; response `sessionId` is printed |
| `TestChatContinue` | `--continue` reads the cache; cache is written after a successful call; cache is per-property; expired session clears the entry and errors |
| `TestChatScope` | credentials missing the scope → exit 2 with actionable message; 403 from API → same message |
| `TestChatQuota` | `--return-property-quota` sets the request field and renders `tokensPerDay`/`tokensPerHour` |
| `TestChatInteractive` | REPL loops until `exit`; threads `sessionId` between turns; Ctrl-C exits cleanly |

`tests/test_chat_session.py`: round-trip save/load; missing file returns `None`; corrupt JSON
returns `None` rather than raising; `clear()` removes only the target property; file mode is `0o600`.

Also update `tests/test_api_diff.py` expectations if it asserts on the v1alpha method list.

---

## Boundaries

**Always:**
- Run `pytest` and `ruff check src/ tests/` before committing.
- Mock every API call in tests.
- Render API-sourced text with `markup=False`.
- Key session state by property ID.
- Print the session ID so users can resume without `--continue`.

**Ask first:**
- Adding any dependency (nothing new should be needed).
- Changing `OAUTH_SCOPES` beyond the single documented chat scope.
- Modifying shared helpers (`output()`, `handle_error()`, `_display_quota()`) rather than adding
  chat-specific ones.
- Bumping the version or tagging a release.

**Never:**
- Silently start a new session when a requested one is invalid.
- Write chat state outside the config directory.
- Send the user's query anywhere except the GA API.
- Cache or log response content to disk (only the session ID is persisted).
- Commit `.api-snapshots/` changes as part of this feature — those are the API-watch workflow's.

---

## Success Criteria

1. `ga reports chat "how many users last week?"` returns a rendered answer against a real property.
2. A follow-up via `--session-id` demonstrably retains context (answer references the prior turn).
3. `--continue` resumes the last conversation for that property across two separate invocations.
4. Switching `-p` between calls does not cross-contaminate sessions.
5. `-o json` output validates against the `ChatResponse` schema with no added or removed keys.
6. A user with pre-0.3.0 credentials gets the re-auth message, not a raw 403.
7. After `ga auth login`, the same command succeeds.
8. `--interactive` handles ≥3 turns and exits cleanly on `exit`, Ctrl-C, and Ctrl-D.
9. An expired `--continue` session produces a clear error and clears the cache.
10. `pytest` and `ruff check src/ tests/` pass; new code covered by the table above.
11. `ga reports chat --help` and `ga agent guide` both document the command.

---

## Implementation Order

1. **Scope plumbing** — `CHAT_SCOPE` in constants, append to `OAUTH_SCOPES`, `has_scope()` in
   `credentials.py`. *Verify:* existing auth tests pass; manual `ga auth login` grants the scope.
2. **Session cache** — `config/chat_session.py` + `test_chat_session.py`. Standalone, no CLI
   dependency. *Verify:* `pytest tests/test_chat_session.py`.
3. **One-shot command** — `chat_cmd` with `--session-id`, block renderer, all three output
   formats, scope pre-flight. *Verify:* `TestChatOneShot`, `TestChatValidation`, `TestChatScope`.
4. **`--continue`** — wire the cache in, expiry handling. *Verify:* `TestChatContinue`.
5. **REPL** — `--interactive`. *Verify:* `TestChatInteractive`.
6. **Quota + docs** — `--return-property-quota` (chat-specific renderer for the narrower quota
   shape), `agent_cmd.py` guide entry, README. *Verify:* full `pytest` + `ruff`.

Steps 1–2 are independent and could be done in parallel; 3 depends on both.

---

## Empirical Findings (probed 2026-09-01)

Probed live against `analyticsdata` v1alpha with `gunnar.griese.gg@gmail.com` and OAuth client
`daidalytics-ga-cli`.

| Finding | Result |
|---|---|
| `analytics.chatbot.read` grantable | **Yes** — granted without registering it on the consent screen (Testing-mode apps request scopes dynamically) |
| `chat` in live discovery | **Yes** — alongside undocumented-in-snapshot `audienceLists`, `reportTasks`, `recurringAudienceLists` |
| `chat` callable | **No** — `403 PERMISSION_DENIED` on 6/6 properties |
| `runReport` on the same property, token and API version | **Yes** — `totalUsers = 99` |

The 403 is therefore **not** a scope problem, **not** an account-access problem (the caller owns
the properties), and **not** an API-enablement problem (`v1alpha runReport` succeeds through the
same client). Denial is uniform across owned properties, a Firebase-linked property, and the
public GA Demo Account — so the gate sits **above the property level**: a closed preview,
allowlist, or account/region entitlement.

**Consequence for error handling:** the API returns the *generic* Data API permission message
(*"User does not have sufficient permissions for this property"*), identical to a real access
failure. The CLI therefore **cannot distinguish** "you lack property access" from "chat is not
enabled for your account". The error text must name both possibilities rather than asserting one.

```
Error: The GA4 chat API refused this request (403).
       This means either:
         - your account lacks access to property {id}, or
         - the chat feature is not enabled for your account.
       Chat is an alpha feature with limited availability.
       Verify access with:  ga properties get -p {id}
```

If `ga properties get` succeeds, the cause is the second — which is the useful diagnostic we can
offer without the API distinguishing them for us.

## Open Questions

1. ~~Is chat generally available?~~ **Answered: no.** See *Empirical Findings*. What remains is
   whether there is a public path to access (allowlist form, product tier, region) — needed for
   the docs, not for the code.
2. **Do service accounts work with chat?** Still unknown and now **untestable** — a service
   account would hit the same account-level gate, so a 403 would be uninformative. Default to
   documenting service accounts as unsupported for chat until proven otherwise.
3. **Session lifetime.** Unmeasurable while chat is gated. Non-blocking: see below.
4. **Can the feature be verified at all before release?** All tests will be mock-only, which
   matches the project's "no real API calls" norm — but block rendering is designed against the
   schema rather than against observed responses. Unknowns: whether `text` carries Markdown,
   typical table widths, and whether block types beyond `text`/`table` appear in practice.
Questions 1–2 are answerable with one manual call against a real property once the scope is
granted — worth doing before step 3 rather than guessing at error paths.

Question 3 does **not** block: whatever the TTL turns out to be, the right design is to make no
client-side staleness judgement and let the server reject a stale ID, because a client-side
threshold could only ever discard sessions the server would have accepted. The number is worth
knowing for documentation, not for control flow.

### Resolved

- **Q4 — Quota defaults.** Resolved: default on in `--interactive`, off for one-shot. See
  *Design Decision 4*.
- **Q5 — Scope documentation.** Resolved: yes. `auth_cmd.py:47` ("No scopes need to be added
  manually") must be revised, since users running their own GCP consent screen may need to add
  `analytics.chatbot.read` explicitly. The 0.3.0 release notes must carry a migration note telling
  existing users to re-run `ga auth login`. Both are part of implementation step 6.
