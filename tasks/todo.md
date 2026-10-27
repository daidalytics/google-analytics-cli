# TODO: Port the allowlist (PR #33) to 0.6.0

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md) · baseline 1460 tests green
on `master` @ `8877860`. Previous checklist (0.6.0): `git show 29c1cb0:tasks/todo.md`.

Legend: `∥` = runs in parallel with its siblings, each in its own worktree agent.

## Wave 0 (orchestrator)

- [x] **T0** · Stash SPEC/tasks, refresh `pr-33` (still `84aed1e`?), `git switch -c feat/allowlist pr-33` (XS)
      · `pr-33` unchanged at `84aed1e`; SPEC + plan stashed and copied to the scratchpad
- [x] **T1** · `git merge origin/master`: resolve per the merge inventory, minimum edits to go green, no D1–D5 semantics (L) · `70fe947`
      · 13 conflicts; 1660 tests green (1460 master + 200 PR); ruff and drift check clean
      · enabling edits: `save_config` creates the profile dir; `store.reset_cache()`; conftest resets store + allowlist caches; `allowlist` field added once in `_auth_status()`; 4 exact-dict status asserts gain it; `commands.md` regenerated
      · `commands.md` ends with a blank line (already on master); `git diff --check` flags it only because the file is new relative to the PR branch

- [x] **CHECKPOINT M** · review agent on `git show --remerge-diff HEAD` · fix findings · report to human (not a gate)
      · review agent: no regression ≥80 confidence (it had no shell, so it checked the merged files against the inventory)
      · orchestrator read the remerge diff itself: both sides kept in every hunk; the PR's "Run 'ga auth login'" status hint dropped on purpose (master had already removed it)

## Wave 1 (6 agents in parallel)

- [x] ∥ **T2a → T2b** · Profile-aware sources (M) → CLI surface: scope text, `allowlist show` profile, status (M) (one agent, two commits) · `22d57a6`, `dde0a95`
      · the agent stopped before committing T2b; the orchestrator checked the staged work against the T2b contract, ran the full suite in the worktree and committed it
- [x] ∥ **T3** · Per-profile cache file + in-process cache keyed by path + reset on profile switch (M) · `3413b52`
      · orchestrator follow-up `7333211`: `test_profiles.py` lists the cache among the per-profile paths
- [x] ∥ **T4** · `principal_of()` for ADC credentials; ADC through `_build()`; refresh not guarded (S) · `888922d`
- [x] ∥ **T5** · Allowlist advice moves into the `hint` field (XS) · `6461630`
- [x] ∥ **T6** · Audience-exports guard tests (S, test-only) · `82f9429`; no guard gap reported
- [x] ∥ **T7** · SKILL.md, `ga agent guide`, README (M) · `8a3dc56`
      · the agent stopped before committing; the orchestrator read the diff, spot-checked its claims against the merged CLI (invalid profile name exits 1 as plain text, unknown profile exits 2, hint text, root allowlist enabled under a named profile) and committed it

- [x] Merge back, full suite after each, `commands.md` never drifted · 1771 tests green, ruff clean
      · actual order T5 → T3 → T6 → T4 → T2 → T7 (T4 committed after T3 had merged; their `allowlist_guard.py` functions don't overlap and the merge was clean)
      · merges `ae46c0c`, `07aa973`, `f779520`, `f6f438f`, `0d62a5b`, `23a3f36`

## Wave 2

- [x] ∥ **T8** · Cross-slice integration tests (S) · `cba7573`, merge `6febb6e`; 15 tests, 1786 green
      · four injected bugs (no reset on profile switch, root cache, root fence ignored in a named profile, hint in the message) each fail their tests; no bug found
      · "nothing sent" uses property allowlists: an account allowlist makes one `accountSummaries` lookup before denying, so that test asserts the lookup is the only request
- [x] ∥ Review agent on `origin/master...feat/allowlist` · no finding ≥ 80 confidence (R6′/R8 widening routes, fail-closed paths, D2 cache, D3 principal, R1′ passthrough, merge damage)
- [x] ∥ Orchestrator docs-vs-behaviour check against a scratch config dir · every README / SKILL.md / `agent guide` claim checked holds
      · offline run: a throwaway service-account key whose `token_uri` points at a dead local port, so a request that passes the guard fails locally
      · root fence under `--profile` and `GA_CLI_PROFILE`; a profile and env only narrow; empty env allows nothing; unreadable root blocks every profile, an unreadable profile file only that one; non-TTY `config set/unset/reset` refused; `auth logout` clears only its profile's cache; audience-exports create blocked (also via `--audience-id properties/P/…`), `--dry-run` sends nothing; `allowlist show` JSON and table match the T2b contract; `profiles delete` needs no TTY
      · nit, not changed: for an unreadable `config.json` the exit-5 `hint` still says to run `ga allowlist show`, which exits 5 in that state too
      · the first run's proxy-only sandbox leaked ~5 token requests for the fake service account to `oauth2.googleapis.com` (httplib2 ignores proxies without PySocks); all rejected, no GA API call; fixed before the rerun

- [ ] **CHECKPOINT W** · suite + ruff + drift green · live read-only check (**ask first**, which property) · **human review**
      · [x] suite (1786), ruff, drift green
      · [x] live read-only check on 250400352 (user re-authenticated as gunnar.griese.gg@gmail.com, OAuth, default profile), env-only allowlist so `config.json` stayed untouched:
        allowed `reports run` returns rows · `-p 123456789` exits 5 with `resource` + `hint` · `allowlist show` resolves 250400352 → account 143775840 via a live `accountSummaries` · property-only allowlist denies `accounts get -a 143775840` · `GA_CLI_ALLOWED_ACCOUNTS=143775840` filters `accounts list` 35 → 1 and allows the report
      · [ ] human review

## Wave 3 (orchestrator, ask first)

- [ ] Push `feat/allowlist` to `origin`; open the new PR crediting @davidher-mann and #33
- [ ] Close #33 with a link and thanks
- [ ] Local `CLAUDE.md`: SPEC B4 pointer, allowlist convention, architecture tree
- [ ] SPEC status + this checklist updated once PR CI passes
