# TODO: `ga reports chat`

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md)

## Phase 1 — Foundation

- [ ] **T1 · Add chat scope + `has_scope()` helper** — S
  - Verify: `pytest tests/test_credentials.py tests/test_auth_cmd.py tests/test_service_account.py`
  - Files: `config/constants.py`, `auth/credentials.py`, `tests/test_credentials.py`
- [ ] **T2 · One-shot `ga reports chat QUERY` + text rendering + `--session-id`** — M
  - Verify: `pytest tests/test_reports_chat.py -k "OneShot or Validation or SessionFlags"`
  - Files: `commands/reports.py`, `tests/test_reports_chat.py`

- [ ] **CHECKPOINT** — `pytest` green · `ruff` clean · command reaches the API · no existing behaviour changed

## Phase 2 — Response contract

- [ ] **T3 · Render `DataTable` blocks in order (+ compact format)** — S
  - Verify: `pytest tests/test_reports_chat.py -k "Table or Rendering or Compact"`
- [ ] **T4 · Scope pre-flight + dual-cause 403 handler** — S
  - Verify: `pytest -k "Scope or Forbidden"` · **live 403 renders correctly in table and json**

- [ ] **CHECKPOINT** — live 403 legible in both formats · review with human

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
