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

- [x] **FINAL** — 969 tests green · ruff clean · version bump and release proceeding
      (Google announced GA for the chat endpoint via the v1alpha Data API, 2026-09-17)

---

## Decisions made

- [x] Ship **visible with alpha caveats** — command appears in `--help`, `--describe` and docs
- [x] Version bump to 0.3.0 — proceeding now that Google has confirmed GA (2026-09-17)

## Verified working (2026-09-18)

- `properties.chat` now succeeds end-to-end on a live, real property (previously 403 for all
  properties, probed 2026-09-01, 0/6). One-shot query, table rendering, `--return-property-quota`,
  and `--continue` session threading all confirmed live against real GA4 data.
- Found and fixed a real bug during live testing: a rejected, manually-typed `--session-id`
  was unconditionally clearing the per-property session cache and blaming `--continue` in the
  error message, even when `--continue` was never used — see `743c828`.
- `tokensPerHour` quota is scoped **per-property** and exhausts within roughly 5-10 chat turns;
  not a bug, just a tight budget to keep in mind when testing.

## Still unverified

- **Q2** service-account support — chat was only tested with OAuth; documented as unsupported
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
- **Chat was gated with a fully-scoped real credential as of 2026-09-01** — re-confirmed after
  re-authentication with all 7 scopes: still `403` on the default property at that time. Google
  announced GA for the endpoint on 2026-09-17, and it was live-verified working end-to-end the
  next day.
