# Implementation Plan: `ga reports chat`

Companion to [SPEC.md](../SPEC.md). Reflects the live probe findings of 2026-09-01.

## Overview

Add `ga reports chat` to the GA CLI, wrapping `analyticsdata.properties.chat` (v1alpha, rev
`20260830`). Delivers one-shot natural-language queries, explicit and cached session threading, an
interactive REPL, and block-based rendering of text and table responses.

**Constraint that shapes everything below:** the endpoint is gated above the property level. Probing
returned `403 PERMISSION_DENIED` on 6/6 properties while `runReport` succeeded on the same property,
token and API version. We are therefore building against the **discovery contract, not observed
responses**. Every task is verified by mock-based tests (the project's existing norm — `conftest.py`
mocks all API calls) plus a live 403 check that exercises the real error path end to end.

## Architecture Decisions

1. **Scope pre-flight over bare 403.** `analytics.chatbot.read` is appended to `OAUTH_SCOPES`.
   Stored credentials record granted scopes (`credentials.py:45`), so we compare *before* the call
   and fail with a re-auth instruction. Confirmed necessary: the probe showed existing credentials
   carry exactly the six pre-0.3.0 scopes.

2. **403 handling is local, not shared.** SPEC's Boundaries mark shared helpers as "ask first", so
   chat gets a local `_handle_chat_403()` rather than modifying `errors.py`. It mirrors
   `handle_error`'s contract — structured JSON to stderr in json mode, Rich text otherwise, exit 2 —
   because the API cannot distinguish "no property access" from "chat not enabled" and the generic
   message must name both. If a second command ever needs this, promote it to `errors.py` then.

3. **`-o json` is a lossless passthrough.** Agents get the raw `ChatResponse`. This is also our
   field-diagnostic channel: since we cannot observe real responses, users who *do* have access can
   send us raw output to validate the renderer against.

4. **Renderer skips unknown block types rather than erroring.** Live discovery already exposes
   methods absent from our snapshot (`audienceLists`, `reportTasks`, `recurringAudienceLists`),
   so this surface is visibly still moving. A future `chart` block must not crash the command.

5. **No client-side session staleness check.** Whatever the TTL is, a client-side threshold could
   only discard sessions the server would have accepted. We let the server reject and recover.

## Dependency Graph

```
constants.py  (CHAT_SCOPE, OAUTH_SCOPES, get_chat_sessions_path)
   │
   ├── credentials.has_scope() ──┐
   │                             │
   └── config/chat_session.py    │
              │                  │
              │            T2 one-shot chat command
              │             (query → API → render)
              │                  │
              │                  ├── T3 DataTable rendering
              │                  ├── T4 scope pre-flight + 403 handler
              │                  ├── T7 REPL
              │                  └── T8 quota
              │                  │
              └──────────────── T6 --continue + expiry recovery
                                 │
                                T9 docs
```

Built bottom-up, but sliced so each task delivers a **complete working path** rather than a layer.

---

## Task List

### Phase 1: Foundation and first working path

---

## Task 1: Add the chat scope and a scope-inspection helper

**Description:** Register `analytics.chatbot.read` in `OAUTH_SCOPES` so `ga auth login` requests it,
and add `has_scope()` so commands can check what stored credentials actually carry. The probe
confirmed the OAuth flow grants this scope without any GCP consent-screen change for testing-mode
apps.

**Acceptance criteria:**
- [ ] `CHAT_SCOPE` constant defined and included in `OAUTH_SCOPES`
- [ ] `has_scope(scope: str) -> bool` returns False when credentials are absent or lack the scope,
      True when present; never raises
- [ ] Existing auth tests still pass unchanged

**Verification:**
- [ ] `pytest tests/test_credentials.py tests/test_auth_cmd.py tests/test_service_account.py`
- [ ] Manual: `ga auth login` consent screen lists the chatbot scope; afterwards
      `credentials.json` contains all seven scopes

**Dependencies:** None
**Files:** `src/ga_cli/config/constants.py`, `src/ga_cli/auth/credentials.py`,
`tests/test_credentials.py`
**Scope:** S

---

## Task 2: One-shot `ga reports chat QUERY` with text rendering

**Description:** The first complete path — a user asks a question and sees an answer. Registers the
command, resolves the property, validates input, calls `properties().chat()` via the existing
`get_data_alpha_client()`, renders `text` blocks, prints the session ID, and accepts
`--session-id` for explicit threading. Table blocks are deferred to Task 3.

**Acceptance criteria:**
- [ ] `ga reports chat "question"` sends `{"userQuery": ...}` and renders returned text blocks
- [ ] `--session-id` is passed through as `sessionId`; omitted when not supplied
- [ ] Response `sessionId` is surfaced so the user can resume
- [ ] `-o json` emits the raw `ChatResponse` with no keys added or removed
- [ ] Rejects: missing query, whitespace-only query, missing property ID
- [ ] Text renders with `markup=False` (a response containing `[bold]` must appear literally)

**Verification:**
- [ ] `pytest tests/test_reports_chat.py -k "OneShot or Validation or SessionFlags"`
- [ ] `ga reports chat --help` renders
- [ ] Manual: against a real property, confirm the request is well-formed (expect 403 until the
      feature is ungated — Task 4 makes that failure legible)

**Dependencies:** Task 1
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports_chat.py`
**Scope:** M

---

### Checkpoint: Foundation
- [ ] `pytest` fully green
- [ ] `ruff check src/ tests/` clean
- [ ] `ga reports chat "test"` reaches the API and returns a real response or a real 403
- [ ] No existing command's behaviour changed

---

### Phase 2: Complete the response contract

---

## Task 3: Render `DataTable` blocks

**Description:** Handle the second block type. Blocks render in document order — a text block
introducing the table that follows it must stay adjacent to it. Feeds rows through the existing
`output()` renderer so chat tables look like every other table in the CLI.

**Acceptance criteria:**
- [ ] `DataTable` headers/rows render as a Rich table, columns in API order
- [ ] Mixed text+table responses render in the order returned
- [ ] Ragged rows (fewer cells than headers) render blank cells instead of raising —
      mirrors `_transform_funnel_rows`' defensive indexing
- [ ] Blocks with neither `text` nor `table` are skipped silently
- [ ] `compact` emits tab-separated rows with a header line; session ID goes to stderr so stdout
      stays pipeable

**Verification:**
- [ ] `pytest tests/test_reports_chat.py -k "Table or Rendering or Compact"`
- [ ] Manual: `ga reports chat "..." -o compact | cut -f1` yields a clean column

**Dependencies:** Task 2
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports_chat.py`
**Scope:** S

---

## Task 4: Scope pre-flight and the dual-cause 403 handler

**Description:** Make both failure modes legible. Before calling, verify credentials carry the chat
scope and tell the user to re-authenticate if not. When the API returns 403 — which every user hits
today — explain that it means *either* missing property access *or* the feature not being enabled,
since the API's generic message cannot distinguish them, and point at `ga properties get` as the
diagnostic that can.

**Acceptance criteria:**
- [ ] Credentials lacking `CHAT_SCOPE` → exit 2 with a "run `ga auth login`" message, no API call
- [ ] A 403 from the API → exit 2, message naming both causes and suggesting
      `ga properties get -p ID`
- [ ] In `-o json`, both emit `{"error": true, "exit_code": 2, "category": "auth_error", ...}` to
      stderr, matching `handle_error`'s shape
- [ ] Non-403 errors still route through the standard `handle_error`

**Verification:**
- [ ] `pytest tests/test_reports_chat.py -k "Scope or Forbidden"`
- [ ] **Live check:** `ga reports chat "test"` against a real property produces the dual-cause
      message rather than a raw traceback — the one real end-to-end assertion available to us
- [ ] Live check with `-o json` emits parseable structured JSON on stderr

**Dependencies:** Tasks 1, 2
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports_chat.py`
**Scope:** S

---

### Checkpoint: Response contract complete
- [ ] `pytest` green, `ruff` clean
- [ ] Live 403 renders the intended message in table **and** json formats
- [ ] Review with human before building session machinery

---

### Phase 3: Session persistence

---

## Task 5: Per-property session cache

**Description:** Standalone persistence module backing `--continue`. Keyed by property ID so
switching properties never resumes the wrong conversation. Corruption-tolerant: a malformed file
returns `None` rather than breaking an unrelated command.

**Acceptance criteria:**
- [ ] `save()` / `load()` / `clear()` round-trip a session ID per property ID
- [ ] Missing file, empty file, and malformed JSON all return `None` without raising
- [ ] File created `0o600`, matching credential-handling conventions
- [ ] `clear()` removes only the target property, leaving others intact
- [ ] Stores only session ID and timestamp — never query or response content

**Verification:**
- [ ] `pytest tests/test_chat_session.py`
- [ ] Manual: `stat -f "%Sp" ~/.config/ga-cli/chat-sessions.json` shows `-rw-------`

**Dependencies:** Task 1 (path constant only) — otherwise independent, parallelizable with 2–4
**Files:** `src/ga_cli/config/chat_session.py`, `src/ga_cli/config/constants.py`,
`tests/test_chat_session.py`
**Scope:** S

---

## Task 6: Wire `--continue` with expiry recovery

**Description:** Connect the cache to the command. Every successful call records its session ID;
`--continue` replays the one for that property. A rejected session must fail loudly — silently
starting fresh would answer a follow-up question without its context and *look* like it worked.

**Acceptance criteria:**
- [ ] `--continue` sends the cached session ID for that property
- [ ] Cache is written after every successful call, one-shot and REPL alike
- [ ] `--session-id` together with `--continue` → `BadParameter`
- [ ] A rejected session clears that property's entry and errors with a clear message; it never
      silently starts a new session
- [ ] `--continue` with no cached session errors actionably
- [ ] Switching `-p` does not cross-contaminate sessions

**Verification:**
- [ ] `pytest tests/test_reports_chat.py -k "Continue"`
- [ ] Manual: two successive invocations with `--continue` reuse one session ID; a `-p` switch
      starts a distinct one

**Dependencies:** Tasks 2, 5
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports_chat.py`
**Scope:** M

---

### Checkpoint: Sessions
- [ ] `pytest` green, `ruff` clean
- [ ] Cache file contains only session IDs and timestamps — verified by inspection
- [ ] Deleting the cache mid-flow degrades gracefully

---

### Phase 4: Interactive use and cost visibility

---

## Task 7: `--interactive` REPL

**Description:** Multi-turn conversation in one process, threading the session ID in memory across
turns. Uses `questionary.text()`, consistent with `reports build`. Must exit cleanly on every
documented path — a hung REPL is worse than no REPL.

**Acceptance criteria:**
- [ ] Loops until `exit`, `quit`, or empty input; `Ctrl-C` and `Ctrl-D` also exit cleanly
- [ ] Session ID threads automatically between turns and is printed once on exit
- [ ] A positional query, if given, becomes the first turn
- [ ] `-o json` with `--interactive` emits one JSON object per turn (JSON Lines)
- [ ] An error mid-conversation ends the REPL with the session ID preserved in the cache

**Verification:**
- [ ] `pytest tests/test_reports_chat.py -k "Interactive"`
- [ ] Manual: `ga reports chat -i`, three turns, exit each documented way

**Dependencies:** Tasks 2, 6
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports_chat.py`
**Scope:** M

---

## Task 8: Tri-state quota flag and chat quota rendering

**Description:** Chat is token-metered, so consumption should be visible where it accumulates.
Defaults on in the REPL, off for one-shot calls so scripted output stays clean. Needs its own
renderer: `PropertyChatQuota` exposes only `tokensPerDay`/`tokensPerHour`, whereas
`_display_quota()` (`reports.py:224`) iterates five keys that do not exist on this type.

**Acceptance criteria:**
- [ ] `--return-property-quota` / `--no-return-property-quota` with `None` default
- [ ] Resolves to `True` in `--interactive`, `False` one-shot; an explicit flag wins either way
- [ ] `_display_chat_quota()` renders `tokensPerDay` and `tokensPerHour` and tolerates either being
      absent
- [ ] REPL prints one dim quota line per turn
- [ ] `_display_quota()` is left untouched

**Verification:**
- [ ] `pytest tests/test_reports_chat.py -k "Quota"`
- [ ] `pytest tests/test_reports.py` — confirms the shared quota path is unchanged

**Dependencies:** Tasks 2, 7
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports_chat.py`
**Scope:** S

---

### Checkpoint: Feature complete
- [ ] Full `pytest` green, `ruff check src/ tests/` clean
- [ ] Every SPEC.md success criterion either met or explicitly blocked on the API gate
- [ ] Review with human before documentation

---

### Phase 5: Documentation

---

## Task 9: Document the command and the re-auth migration

**Description:** Close the loop on SPEC Q5. Every existing user must re-run `ga auth login`, and
the current claim that no scopes need manual setup is conditionally wrong — true for testing-mode
apps (as the probe confirmed), wrong once an app is in production.

**Acceptance criteria:**
- [ ] `ga agent guide` documents chat under its reports section, including alpha/limited-availability status
- [ ] README documents the command alongside `funnel`/`pivot`
- [ ] `auth_cmd.py:47`'s "no scopes need to be added manually" is qualified for production-mode apps
- [ ] Help text states chat is alpha with limited availability
- [ ] Release note tells existing users to re-authenticate

**Verification:**
- [ ] `pytest tests/test_agent_cmd.py tests/test_describe.py`
- [ ] `ga agent guide --section reports | grep -i chat`
- [ ] `ga --describe | jq '.. | select(.name? == "chat")'` shows the command

**Dependencies:** Tasks 2–8
**Files:** `src/ga_cli/commands/agent_cmd.py`, `src/ga_cli/commands/auth_cmd.py`, `README.md`
**Scope:** M

---

### Checkpoint: Ready for review
- [ ] All acceptance criteria met
- [ ] `pytest` and `ruff` green
- [ ] Version bump and release **not** performed — ask first (SPEC Boundaries)
- [ ] `.api-snapshots/` left untouched — that is the api-watch workflow's territory

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Cannot verify against the live API — chat is gated | **High** | Build to the discovery contract; mocks derived from the schema; `-o json` stays lossless so an entitled user's raw output can validate the renderer later. Live-verify the 403 path, which we *can* exercise. |
| Rendering assumptions unproven — Markdown in `text`, wide tables, long answers | **Med** | `markup=False` prevents the worst failure; tables reuse the existing renderer's width handling; unknown block types skipped, not fatal |
| Scope change forces re-auth for **every** existing user | **Med** | Pre-flight check with an actionable message (Task 4); release note (Task 9). Confirmed by probe: current credentials carry only the six old scopes. |
| Alpha surface still shifting | **Med** | Discovery already exposes three methods missing from our snapshot. Renderer tolerates unknown block types; do not hard-code block enums. |
| 403 message is generic and indistinguishable from real permission errors | **Med** | Dual-cause message naming both possibilities plus a concrete diagnostic command — never assert a single cause |
| Chat token quota exhausts quietly | **Low** | Quota on by default in the REPL (Task 8); `429` observed on demo properties during probing |
| `--continue` resumes the wrong conversation after a property switch | **Low** | Cache keyed by property ID; explicit test |

## Parallelization

- **Task 5 is independent** of Tasks 2–4 (only needs Task 1's path constant) and can run alongside them.
- Tasks 2 → 3 → 4 are strictly sequential; 6 → 7 → 8 likewise.
- Task 9 needs everything else finished.

## Open Questions

1. **Ship visible or hidden?** The plan assumes **visible with alpha caveats** — the command appears
   in `--help` and returns the dual-cause 403 for users without access. The alternative is hiding it
   until Google ungates. Flagging because it affects Task 9's scope, not the code.
2. **Verify the renderer how, eventually?** If access opens, the fastest validation is
   `-o json` output from one real call diffed against our mock fixtures. Worth keeping the probe
   scripts around for that.
3. **Version bump to 0.3.0** is out of scope here per SPEC Boundaries — confirm when ready to release.
