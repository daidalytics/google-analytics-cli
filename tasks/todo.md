# TODO: Account and property allowlist

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md) · branch `feat/allowlist`

## Phase 0: Branch
- [x] T0 Create `feat/allowlist`; commit SPEC.md + tasks/

## Phase 1: Foundations (no network)
- [x] T1 `AllowlistError`, exit code 5 / `allowlist_error`, `resource` in the JSON payload, "ask the user" hint
- [x] T2 Allowlist config keys + `config/allowlist.py` (parse, sources, intersection, property-only rules, direct hit without lookup); conftest clears `GA_CLI_ALLOWED_*`

## Phase 2: The guard
- [x] T3 Reference extraction (decoded path, query, body) + route classification (discovery only; unknown host denied), tested against real-client URIs
- [x] T4 Property → account cache (TTL, principal, refresh once via a separate plain `AuthorizedHttp`, account from enclosing summary, atomic write)
- [x] T5 `AllowlistHttp` enforcement + `_build` helper for all 4 clients; 401 retry stays guarded; declare httplib2 deps
- [x] T6 Response filtering for accounts / accountSummaries / properties list (idempotent)
- [x] **Checkpoint A:** suite + ruff green · live allow/deny on 250400352 (property and account allowlist, funnel) · **review with the human**
  - [x] suite (1239) + ruff green
  - [x] live, read-only, on 487271032 / accounts/353535768 instead (250400352 isn't visible to the current login): property + account allowlist, funnel, change history, access bindings
  - [x] review with the human

## Phase 3: CLI surface
- [x] T7 `ga config` allowlist keys: list parsing, TTY + confirm, `setup`/`reset` keep the allowlist
- [x] T8 `ga allowlist show`, `auth status` allowlist field, login/logout clear the cache, `ga --describe` lists it
- [x] **Checkpoint B:** suite + ruff green · live non-TTY refusal + interactive set
  - [x] suite + ruff green
  - [x] live non-TTY refusal (`echo y | ga config set allowed_account_ids 1` → exit 1, file untouched)
  - [x] interactive set in a real terminal: set → `ga allowlist show` reflects it → unset → disabled

## Phase 4: Docs and release prep
- [x] T9 Agent guide Allowlist section + new "Errors and exit codes" section (1–5); README section + env vars; SPEC status → implemented
- [ ] T10 Push, open PR, CI green. **Merge only on the human's go**
- [ ] **Checkpoint: complete**
