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

- [x] **T5 · Per-property session cache** — S · `79fb7b6`
- [x] **T6 · Wire `--continue` + expiry recovery** — M · `1442f53`

- [x] **CHECKPOINT** — 950 tests green · cache holds only session IDs + timestamps · `0o600`

## Phase 4 — Interactive + cost

- [x] **T7 · `--interactive` REPL** — M · `7b47b3a`
- [x] **T8 · Tri-state quota flag + `_display_chat_quota()`** — S · `328b37a`

- [x] **CHECKPOINT** — 967 tests green · `_display_quota()` untouched

## Phase 5 — Docs

- [x] **T9 · Agent guide, README, re-auth migration note, qualify `auth_cmd.py:47`** — M · `0045f64`

- [x] **FINAL** — 967 tests green · ruff clean · version bump and release **not** done
      (holding PyPI until GA officially supports the endpoint) · `.api-snapshots/` untouched

---

## Decisions made

- [x] Ship **visible with alpha caveats** — command appears in `--help`, `--describe` and docs
- [ ] Version bump to 0.3.0 — deferred; not publishing to PyPI until GA supports the endpoint

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

- **`analytics.chatbot.read` is not a sensitive scope.** Verified through a real `ga auth login`:
  it is granted without appearing as its own consent-screen checkbox and without being registered
  in the GCP consent screen (Testing mode). Easier to adopt than the existing `analytics.*` scopes.
- **Chat remains gated with a fully-scoped real credential** — re-confirmed after re-authentication
  with all 7 scopes: still `403` on the default property.
