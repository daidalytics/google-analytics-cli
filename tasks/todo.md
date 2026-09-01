# TODO: `ga reports chat`

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md)

## Phase 1 — Foundation

- [x] **T1 · Add chat scope + `has_scope()` helper** — S · `4635915`
- [x] **T2 · One-shot `ga reports chat QUERY` + text rendering + `--session-id`** — M · `02d97aa`

- [x] **CHECKPOINT** — 912 tests green · ruff clean · command reaches the live API

## Phase 2 — Response contract

- [x] **T3 · Render `DataTable` blocks in order (+ compact format)** — S · `35291c0`
- [x] **T4 · Scope pre-flight + dual-cause 403 handler** — S · `9522959`

- [x] **CHECKPOINT** — 926 tests green · ruff clean · **both live 403 paths verified**
  - Token *without* the scope → pre-flight message, exit 2, no API call
  - Token *with* the scope → dual-cause message, exit 2 (feature still gated)
  - Structured JSON error confirmed on stderr in both cases

## Phase 3 — Sessions

- [ ] **T5 · Per-property session cache** — S · *parallelizable with T2–T4*
  - Verify: `pytest tests/test_chat_session.py` · file mode `0o600`
  - Files: `config/chat_session.py`, `config/constants.py`, `tests/test_chat_session.py`
- [ ] **T6 · Wire `--continue` + expiry recovery** — M
  - Verify: `pytest -k "Continue"` · property switch does not cross-contaminate

- [ ] **CHECKPOINT** — cache holds only session IDs + timestamps · deleting it degrades gracefully

## Phase 4 — Interactive + cost

- [ ] **T7 · `--interactive` REPL** — M
  - Verify: `pytest -k "Interactive"` · exits cleanly on `exit`, Ctrl-C, Ctrl-D
- [ ] **T8 · Tri-state quota flag + `_display_chat_quota()`** — S
  - Verify: `pytest -k "Quota"` · `pytest tests/test_reports.py` unchanged

- [ ] **CHECKPOINT** — full suite green · SPEC success criteria met or explicitly gate-blocked

## Phase 5 — Docs

- [ ] **T9 · Agent guide, README, re-auth migration note, qualify `auth_cmd.py:47`** — M
  - Verify: `pytest tests/test_agent_cmd.py tests/test_describe.py` · `ga agent guide --section reports | grep -i chat`

- [ ] **FINAL** — all criteria met · version bump and release **not** done (ask first) · `.api-snapshots/` untouched

---

## Decisions needed

- [ ] Ship **visible with alpha caveats** (assumed) or hidden until Google ungates? — affects T9
- [ ] Confirm version bump to 0.3.0 when ready to release

## Blocked / cannot verify

- `properties.chat` returns 403 for all properties — feature gated above property level
  (probed 2026-09-01, 0/6 properties, while `runReport` succeeded on the same property/token)
- **Q2** service-account support — untestable while gated; documented as unsupported for now
- **Q3** session TTL — unmeasurable; non-blocking, design relies on server rejection

---

## Empirical notes from implementation

- **Two distinct 403 messages exist**, confirmed live:
  - No chat scope → `"Request had insufficient authentication scopes."`
  - Scope present, feature gated → `"User does not have sufficient permissions for this property."`
  The pre-flight intercepts the first; the dual-cause handler explains the second.
- `click` 8.3: `Result.output` combines stdout **and** stderr; use `Result.stdout` to assert
  a stream stays pipeable.
