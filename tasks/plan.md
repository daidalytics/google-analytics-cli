# Implementation Plan: Port the allowlist (PR #33) to 0.6.0

Companion to [SPEC.md](../SPEC.md). Baseline: **1460 tests passing** (8.7 s) on `master` @
`8877860`. The previous plan (0.6.0: distribution, profiles, audience exports) is in git history
at `29c1cb0:tasks/plan.md`.

## Overview

The work has two parts.

1. **One merge, done by the orchestrator.** Merge `origin/master` into the PR head, resolving
   the 13 conflicts per the spec's merge inventory. This step is strictly sequential, and
   everything else builds on it.
2. **Six parallel subagents for SPEC D1–D6.** After the merge, the work fans out to six
   agents in isolated git worktrees. Each agent owns a disjoint set of files.

After that come one integration-test agent, a review agent, and the human gate before anything
is pushed.

The critical path is four steps (`T1 merge → T2a → T2b → T8 integration`), not 11 sequential
tasks. Peak concurrency is 6 agents (wave 1).

## Architecture Decisions

1. **One branch, task branches off it.** The lane branch is `feat/allowlist` on `origin`
   (SPEC decision 2). It starts from `pr-33`, and `origin/master` is merged in, never rebased,
   so David's 5 commits keep their authorship. Each agent works on `task/<ID>-<slug>` cut from
   `feat/allowlist`, and the orchestrator merges each task branch back.
2. **The orchestrator does the merge itself (T1).** Merging isn't parallelizable, it carries
   the most judgment, and the orchestrator already holds the merge inventory. **The merge
   commit only resolves conflicts and gets the suite green.** No D1–D5 semantics go into it, so
   a review of it means one thing: did anything from either side get lost?
3. **One agent per file-ownership set.** T2a→T2b share semantics (the source model), so one
   agent runs them in sequence, as two commits. Every other wave-1 task gets its own agent. The
   one shared source file, `api/allowlist_guard.py`, is split **by function** between T3 and T4.
4. **New behaviour gets new test files.** Wave-1 agents don't append to
   `tests/test_allowlist_guard.py`, because parallel appends at end-of-file conflict. Each
   creates its own file and imports the PR's helpers (`guarded`, `_al`, `_resp`, `FakeCreds`,
   `A`/`AA`/`D`/`DA`) from `tests.test_allowlist_guard`. `tests/` is a package, so that works.
5. **Contracts before fan-out.** Every function one agent writes and another reads is fixed below
   in [Interface Contracts](#interface-contracts), so dependent agents can be briefed up front.
6. **Generated files are never hand-merged.** `skills/ga-cli/references/commands.md` is
   regenerated with `scripts/gen_skill_reference.py --write` after every merge that changes the
   CLI schema.
7. **Subagents never touch live APIs, push, or open PRs.** Live checks, pushes, the new PR and
   closing #33 are done by the orchestrator, and only after asking.
8. **`CLAUDE.md` is gitignored.** Agents in worktrees can't see it, so they read it from the
   main checkout. Editing it is a local orchestrator step (wave 3) and isn't part of the PR.

## Dependency Graph

```
 W0  T0 branch setup ── T1 merge origin/master (orchestrator) ── CHECKPOINT M (review agent)
                                                                        │
            ┌───────────────┬──────────────┬──────────────┬─────────────┼──────────────┐
 W1         ▼               ▼              ▼              ▼             ▼              ▼
     T2a sources ─▶ T2b CLI   T3 cache/profile  T4 ADC principal  T5 hint field  T6 audience-   T7 docs
     (D1, agent α)            (D2, agent β)     (D3, agent γ)     (D4, agent δ)  exports tests  (D6, agent ζ)
                                                                                 (D5, agent ε)
            └───────────────┴──────────────┴──────────────┴─────────────┴──────────────┘
                                                   │  merge back: T5, T4, T3, T6, T2, T7
                                                   ▼
 W2              T8 integration tests (agent)  ∥  review agent  ∥  orchestrator docs-vs-behaviour check
                                                   │
                                          CHECKPOINT W (human gate)
                                                   │
 W3          orchestrator, ask-first: push origin · new PR · close #33 · local CLAUDE.md
```

## Execution Schedule

| Wave | Runs in parallel | Agents | Blocked on |
|---|---|---|---|
| **0** | T0 setup → T1 merge (orchestrator, main checkout) | 0 | plan approval |
| — | **CHECKPOINT M**: review agent on the merge resolution; orchestrator fixes findings | 1 | T1 |
| **1** | **T2a→T2b** (one agent) · **T3** · **T4** · **T5** · **T6** · **T7** | 6 | Checkpoint M |
| — | Orchestrator merges task branches; full suite after each | | all of wave 1 |
| **2** | **T8** integration tests · **review agent** · orchestrator docs-vs-behaviour check | 2 | wave 1 merged |
| — | **CHECKPOINT W**: live read-only check (ask first) · **human review** | | wave 2 |
| **3** | Orchestrator: push · `gh pr create` · close #33 · local `CLAUDE.md` · SPEC status | 0 | human go-ahead |

## File Ownership (wave 1)

A task may edit only the files listed for it. If it needs another file, it stops and reports
instead of editing.

| File | Owner | Notes |
|---|---|---|
| `src/ga_cli/config/store.py` | T2a | T1 has already added the profile-dir mkdir and `reset_cache()` |
| `src/ga_cli/config/allowlist.py`, `tests/test_allowlist.py` | T2a | |
| `src/ga_cli/commands/config_cmd.py`, `src/ga_cli/commands/allowlist_cmd.py` | T2b | |
| `tests/test_config_cmd.py`, `tests/test_allowlist_cmd.py`, `tests/test_auth_cmd.py` | T2b | |
| `src/ga_cli/config/constants.py`, `src/ga_cli/main.py` | T3 | |
| `src/ga_cli/api/allowlist_guard.py` | **T3**: `_caches`, `cache_for`, `reset_caches`, `delete_cache_file` · **T4**: `principal_of` | split by function; orchestrator merges both |
| `tests/test_allowlist_cache_profiles.py` (new) | T3 | |
| `tests/test_allowlist_adc.py` (new) | T4 | |
| `src/ga_cli/utils/errors.py`, `tests/test_errors.py` | T5 | |
| `tests/test_allowlist_audience_exports.py` (new) | T6 | test-only; a guard bug gets reported, not fixed |
| `skills/ga-cli/SKILL.md`, `src/ga_cli/commands/agent_cmd.py`, `tests/test_agent_cmd.py`, `README.md` | T7 | |
| `tests/conftest.py`, `tests/test_allowlist_guard.py`, `tests/test_api_client.py`, `skills/ga-cli/references/commands.md`, `SPEC.md`, `tasks/*` | **orchestrator only** | |

## Interface Contracts

These are fixed now so all wave-1 agents can be briefed at once:

```python
# T1 (store.py, conftest.py)
def reset_cache() -> None: ...            # store: forget all cached config/error state (conftest calls it)
# conftest autouse also: delenv GA_CLI_ALLOWED_ACCOUNTS / _PROPERTIES; allowlist_guard.reset_caches()

# T2a → T2b, T7, T8   (config/store.py, config/allowlist.py)
def get_root_config_path() -> Path: ...    # get_config_dir() / "config.json"; == get_config_path() in default
def load_config_at(path: Path) -> UserConfig: ...       # path-keyed cache, same parsing as load_config()
def config_error(path: Path | None = None) -> str | None: ...   # None → active profile's config.json
AllowlistSource.name in {"config", f"profile {name}", "env"}   # "config" = root file, all profiles
def load_allowlist() -> Allowlist: ...     # config ∩ profile ∩ env; default profile: one file source
def is_allowlist_configured() -> bool: ... # root, profile or env set; unreadable root/profile counts as set

# T2b → T7, T8   (ga allowlist show -o json)
{"enabled": bool, "profile": str,
 "sources": {"config": {...} | None, "profile": {...} | None, "env": {...} | None}, ...}
# a "profile" key is present only for a named profile; unknown named profile → exit 2

# T3 → T8   (config/constants.py, api/allowlist_guard.py, main.py)
def get_allowlist_cache_path() -> Path: ...   # get_profile_dir() / "allowlist-cache.json"
def cache_for(credentials, http) -> AllowlistCache: ...   # keyed by (get_allowlist_cache_path(), principal)
def reset_caches() -> None: ...               # also called from main._select_profile on a profile change

# T4   (api/allowlist_guard.py)
def principal_of(credentials) -> str | None: ...   # SPEC D3 table; an "email" without "@" → None

# T5 → T7, T8   (utils/errors.py)
class AllowlistError(Exception): resource: str; reason: str   # str(err) == reason (no hint appended)
def error_hint(err) -> str | None: ...     # ALLOWLIST_HINT for AllowlistError; ADC hint unchanged
```

## Subagent Protocol

Every wave-1 and wave-2 agent is launched with `isolation: "worktree"`, and its brief starts
with these rules:

1. **Branch:** You are in an isolated git worktree. First run
   `git switch -c task/<ID>-<slug> feat/allowlist`.
2. **Read first:**
   - `/Users/gunnargriese/Desktop/python3/agent-cli/google-analytics-cli/CLAUDE.md` (gitignored,
     so it isn't in your worktree).
   - The SPEC sections named in your task.
   - The contracts in `tasks/plan.md`.
   - The files you own.
3. **Ownership:** Edit **only** the files in your task's ownership list. If you need another
   file, stop and report why instead of editing it.
4. **Tests:**
   - Write the failing tests first, then implement.
   - Never call a live API; mock everything.
   - `google.auth.default` is already patched to raise by conftest. Tests that need ADC set their
     own return value.
5. **Before committing:** run `uv run pytest` (the **full** suite),
   `uv run ruff check src/ tests/ scripts/` and
   `uv run python scripts/gen_skill_reference.py --check`. All must pass. Docs agents: if
   `--check` fails, report it; don't regenerate.
6. **Commit:** one commit per task ID (T2 makes two), with a conventional message ending in the
   `Co-Authored-By` trailer. **Don't push, and don't open a PR.**
7. **Report:**
   - Branch and commit SHA(s).
   - Test count.
   - Every deviation from SPEC or the plan, with the reason.
   - Any guard bug or contract problem you found but didn't fix.

The orchestrator (main session):

- Launches all wave-1 agents in a single message, so they run concurrently.
- Checks each task's `git diff --stat feat/allowlist...task/<ID>` against its ownership list
  before merging it.
- Merges in the order T5, T4, T3, T6, T2, T7, and runs the full suite after each merge.
- Regenerates `commands.md` if the drift check fails.
- Fixes cross-task issues in its own follow-up commits.

---

## Task List

### Wave 0: Orchestrator

#### T0: Branch setup

**Description:** Get the main checkout onto `feat/allowlist` without losing the uncommitted
SPEC and plan.

**Acceptance criteria:**
- [ ] `SPEC.md`, `tasks/plan.md` and `tasks/todo.md` are copied to the scratchpad, then
      `git stash push -- SPEC.md tasks/` is run. `pr-33` has its own versions of these files, so
      `git switch` would refuse otherwise.
- [ ] `git fetch origin` and `git fetch origin pull/33/head:pr-33` are run, and `pr-33` is still
      `84aed1e`. If David pushed since, stop and ask.
- [ ] `git switch -c feat/allowlist pr-33` is run, and `git log -1` shows David's `84aed1e`.

**Verification:** `git status` is clean, and `git stash list` shows the stash.

**Dependencies:** plan approval · **Scope:** XS

#### T1: Merge `origin/master` into `feat/allowlist`

**Description:** Run `git merge origin/master` and resolve every conflict per the SPEC
[merge inventory](../SPEC.md#merge-inventory). Then make the **minimum** edits needed for a
green suite: no D1–D5 semantics. `SPEC.md` and `tasks/*` resolve to the stashed versions.

**Acceptance criteria:**
- [ ] Every conflict is resolved, and every side's behaviour is kept:
  - master's `resolve_credentials()`, `_require_existing_profile()`, profile-aware
    `_auth_status()`, the hint machinery, and `profiles` / `audience-exports` registration;
  - the PR's `_build()` in all 4 getters, `AllowlistError`/exit 5, TTY-only allowlist changes,
    atomic save, and decision 8.
- [ ] These enabling edits are in the merge commit:
  - `save_config` creates `config_path.parent`.
  - `store.reset_cache()` exists, and conftest calls it, deletes `GA_CLI_ALLOWED_*` from the
    environment and calls `reset_caches()`.
  - The master build assertions in `test_api_client.py` change to `http=` with an
    `AllowlistHttp`.
  - `"allowlist": {"enabled": …}` is added once, in `_auth_status()`.
  - `commands.md` is regenerated.
- [ ] Run `git show --remerge-diff HEAD` and review it. Hunks resolved in favour of one side are
      listed in the commit message body.

**Verification:**
- [ ] `git diff --check HEAD~1` passes, and `grep -rn '^<<<<<<<\|^>>>>>>>' src tests` finds
      nothing.
- [ ] `uv run pytest`: record the count. It should be ≥ 1460 plus the PR's tests.
- [ ] `uv run ruff check src/ tests/ scripts/` passes, and `gen_skill_reference.py --check`
      passes.

**Dependencies:** T0 · **Scope:** L (merge; one sitting) · **Commit:**
`Merge origin/master (0.6.0) into feat/allowlist`

### Checkpoint M: merge review, before the fan-out

- [ ] Launch a `feature-dev:code-reviewer` agent on `git show --remerge-diff HEAD` and the
      merge inventory. Its question: *was behaviour from either side lost or altered?* Focus
      areas:
  - credential resolution order;
  - unknown-profile exit 2;
  - all 4 getters guarded;
  - `classify_error` ordering;
  - `config setup` keeping the allowlist;
  - conftest isolation.
- [ ] The orchestrator fixes confirmed findings in a follow-up commit. The full suite stays
      green.
- [ ] Report to the human. **This is not a gate:** wave 1 starts unless you say stop.

### Wave 1: six parallel agents

#### T2a: Profile-aware allowlist sources (SPEC D1, core) · agent α, commit 1

**Description:**
- Add a third source: the root `config.json` applies to every profile, and a named profile's
  `config.json` narrows it.
- The default profile has a single file source.
- Error state is tracked per path, so an unreadable root file fails every profile closed and an
  unreadable profile file fails only that profile.

**Acceptance criteria:**
- [ ] `load_allowlist()` with the root file + `--profile X` file + env is the intersection, with
      source names per the contract. In the default profile, the root file counts once.
- [ ] An unreadable root `config.json` makes `load_allowlist()` raise `AllowlistError` while a
      named profile is active. An unreadable profile file affects only that profile.
- [ ] `get_root_config_path`, `load_config_at` and `config_error(path)` exist per the contract.
      `reset_cache()` clears all of the new state.

**Verification:** `uv run pytest tests/test_allowlist.py tests/test_profiles.py -q`, plus the
full suite and ruff.

**Dependencies:** Checkpoint M · **Scope:** M

**Files:** `src/ga_cli/config/store.py`, `src/ga_cli/config/allowlist.py`,
`tests/test_allowlist.py`

#### T2b: CLI surface for profile sources (SPEC D1, CLI) · agent α, commit 2

**Description:** The confirmation text names the scope ("all profiles" vs "profile X, narrows
the global allowlist"). `ga allowlist show` gains `profile` and `sources.profile`. `ga --profile
typo allowlist show` exits 2. `auth status` reports `enabled: true` in a named profile when only
the root file is set.

**Acceptance criteria:**
- [ ] TTY `config set allowed_account_ids` in default vs `--profile X` shows the right scope
      line, and writes the right file. A new profile's directory is created.
- [ ] `allowlist show -o json` matches the T2b contract in default and named profiles. An
      unknown profile exits 2 before any network call.
- [ ] `ga --profile X auth status -o json` shows `allowlist.enabled == true` with only the root
      allowlist set.

**Verification:**
`uv run pytest tests/test_config_cmd.py tests/test_allowlist_cmd.py tests/test_auth_cmd.py -q`,
plus the full suite and ruff.

**Dependencies:** T2a (same agent) · **Scope:** M

**Files:** `src/ga_cli/commands/config_cmd.py`, `src/ga_cli/commands/allowlist_cmd.py`,
`tests/test_config_cmd.py`, `tests/test_allowlist_cmd.py`, `tests/test_auth_cmd.py`

#### T3: Per-profile cache (SPEC D2) · agent β

**Description:**
- `allowlist-cache.json` moves into the profile directory.
- The in-process caches are keyed by `(path, principal)`.
- `_select_profile` resets them on a profile change.
- `auth login` / `logout` clear only the active profile's cache.

**Acceptance criteria:**
- [ ] `get_allowlist_cache_path()` is `profiles/X/allowlist-cache.json` under `--profile X`, and
      the root file in default. The constants docstring lists it as per profile.
- [ ] `ga --profile X auth logout` (CliRunner) deletes X's cache and leaves the root cache file
      in place.
- [ ] Two CliRunner invocations in one process under different profiles with the same principal
      don't share an in-memory map: the second refetches or loads its own file.

**Verification:** `uv run pytest tests/test_allowlist_cache_profiles.py -q`, plus the full suite
and ruff.

**Dependencies:** Checkpoint M · **Scope:** M

**Files:** `src/ga_cli/config/constants.py`, `src/ga_cli/api/allowlist_guard.py` (only
`_caches` / `cache_for` / `reset_caches` / `delete_cache_file`), `src/ga_cli/main.py`,
`tests/test_allowlist_cache_profiles.py`

#### T4: ADC cache principal (SPEC D3) · agent γ

**Description:** `principal_of()` follows the SPEC D3 table. Unknown principals mean no disk
cache. ADC credentials are guarded through `_build()`, and their token refresh isn't routed
through the guard.

**Acceptance criteria:**
- [ ] There is one test per D3 table row. They use real `google.auth` credential classes where
      they can be built offline (impersonated, external_account), and stubs otherwise.
- [ ] With `google.auth.default` patched to return impersonated credentials, `get_admin_client()`
      is built on `AllowlistHttp`. A 401 → refresh → retry calls the inner http for the token,
      and doesn't raise `AllowlistError`.
- [ ] A `None` or `"default"` principal writes no cache file, and denials are still enforced.

**Verification:** `uv run pytest tests/test_allowlist_adc.py -q`, plus the full suite and ruff.

**Dependencies:** Checkpoint M · **Scope:** S

**Files:** `src/ga_cli/api/allowlist_guard.py` (only `principal_of`),
`tests/test_allowlist_adc.py`

#### T5: Allowlist advice in the `hint` field (SPEC D4) · agent δ

**Description:** `AllowlistError`'s message is the reason only. `error_hint()` returns
`ALLOWLIST_HINT` for it, so `handle_error` prints it as `"hint"` in JSON and as a second line in
text output.

**Acceptance criteria:**
- [ ] `str(AllowlistError("properties/9", "x"))` is `"x"`. The JSON payload has `category`,
      `resource` and `hint`, and the message has no hint appended.
- [ ] In text mode the hint is on its own line. The ADC scope hint behaviour and its tests are
      unchanged.
- [ ] `classify_error` still checks `AllowlistError` first.

**Verification:** `uv run pytest tests/test_errors.py -q`, plus the full suite and ruff. If any
other test file asserts the hint inside a message, report it; don't edit it.

**Dependencies:** Checkpoint M · **Scope:** XS

**Files:** `src/ga_cli/utils/errors.py`, `tests/test_errors.py`

#### T6: Audience-exports guard coverage (SPEC D5) · agent ε

**Description:** Pin every audience-exports endpoint against the guard, using real `D`
(`analyticsdata` v1beta) clients built with `guarded()` from `tests.test_allowlist_guard`.

**Acceptance criteria:**
- [ ] Each row of the SPEC D5 table has an allowed case and a denied case. Denied cases assert
      `request_sequence == []`.
- [ ] `create` is denied when its body names `properties/P2/audiences/A` and P2 isn't allowed,
      even with an allowed `-p`. `create --dry-run` sends nothing (CliRunner).
- [ ] If any case exposes a guard gap, the passing cases are committed and the gap is reported
      with a minimal repro. No `xfail`, and no guard edits.

**Verification:** `uv run pytest tests/test_allowlist_audience_exports.py -q`, plus the full
suite and ruff.

**Dependencies:** Checkpoint M · **Scope:** S

**Files:** `tests/test_allowlist_audience_exports.py`

#### T7: Agent and user docs (SPEC D6) · agent ζ

**Description:** Write from the SPEC and the contracts above, not from the code, which other
agents are changing at the same time.

**Acceptance criteria:**
- [ ] `SKILL.md` gets an "Allowlist" section right after "Profiles". On exit 5, report the
      `resource` and ask the user. Don't switch `--profile`, unset `GA_CLI_ALLOWED_*`, run
      `auth login` or try `config set`. Use `ga allowlist show -o json` to see what's allowed.
- [ ] `ga agent guide` keeps the PR's "Allowlist" and "Errors and exit codes" sections, adds the
      profile rule, and matches 0.6.0 exit codes: invalid profile name 1, unknown profile 2.
- [ ] The README describes the global fence + profile narrowing and the per-profile cache path,
      and adds `--profile` to the "not a security boundary" list. The env table lists both
      `GA_CLI_ALLOWED_*` vars next to `GA_CLI_PROFILE`.

**Verification:** `uv run pytest tests/test_skill.py tests/test_agent_cmd.py -q` (skill
commands must exist), plus the full suite. Read the rendered README section.

**Dependencies:** Checkpoint M · **Scope:** M

**Files:** `skills/ga-cli/SKILL.md`, `src/ga_cli/commands/agent_cmd.py`,
`tests/test_agent_cmd.py`, `README.md`

### Wave 2: after all wave-1 branches are merged

#### T8: Cross-slice integration tests · agent

**Description:** Write end-to-end CliRunner tests that cross task boundaries, which no
single wave-1 agent could write. They cover SPEC success criteria 3, 5, 7 and 8.

**Acceptance criteria:**
- [ ] With a root allowlist, `GA_CLI_PROFILE=X ga reports run -p <outside>` and
      `ga --profile X reports run …` exit 5. The JSON has `category`, `resource` and `hint`, and
      nothing is sent.
- [ ] With a root allowlist and a narrower profile allowlist, a property allowed by the root
      but not by the profile exits 5 under X and is allowed in default.
- [ ] A lookup under X writes `profiles/X/allowlist-cache.json` and no root cache. A blocked
      `audience-exports create` under X exits 5.

**Verification:** `uv run pytest tests/test_allowlist_integration.py -q`, plus the full suite and
ruff.

**Dependencies:** wave 1 merged · **Scope:** S

**Files:** `tests/test_allowlist_integration.py`

### Checkpoint W: final gate before pushing

- [ ] All task branches are merged. The full suite, ruff and the drift check pass.
- [ ] A `feature-dev:code-reviewer` agent reviews `git diff origin/master...feat/allowlist`
      (focus: SPEC R1′, R6′, R8–R11; fail-closed paths). It runs in parallel with T8.
- [ ] Orchestrator docs-vs-behaviour check. Run the CLI against a scratch `GA_CLI_CONFIG_DIR`
      and check what SKILL.md and the README claim, offline:
  - `allowlist show` with the guard off;
  - `--profile typo allowlist show` exits 2;
  - a non-TTY `config set allowed_*` is refused;
  - `auth status` has the `allowlist` field.
- [ ] **Live read-only check: ask first, including which property.** The stored login gets 403
      on 250400352, and other properties belong to real clients. Skip it if there's no suitable
      property, and record that.
- [ ] **Human review of the branch.** Ask before any push.

### Wave 3: orchestrator, after the human go-ahead

- [ ] `git push -u origin feat/allowlist`, then `gh pr create`. The description credits
      @davidher-mann and #33 and states the 0.6.0 deltas (SPEC D1–D6). **Ask first.**
- [ ] Close #33 with a comment linking the new PR and thanking David. **Ask first.**
- [ ] Edit the local, gitignored `CLAUDE.md`:
  - point "SPEC.md B4" at `git show 7594078:SPEC.md`;
  - add the allowlist convention line;
  - add the new module to the architecture tree.
- [ ] Update the SPEC status and `tasks/todo.md` once CI on the PR passes.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The merge silently drops behaviour from one side | High | Merge commit has no new semantics; both suites must pass; review agent on `--remerge-diff` before fan-out |
| T3 and T4 both edit `allowlist_guard.py` | Med | Function-level ownership, merged back one after the other with the suite after each |
| T7 docs drift from what T2/T5 implement | Med | T7 writes from fixed contracts; Checkpoint W runs the CLI to check the doc claims |
| T6 exposes a guard gap mid-wave | Med | T6 reports and doesn't patch; orchestrator fixes in a follow-up commit after T3/T4 merge |
| In-process caches leak across profiles or tests | Med | T1 conftest resets `store` and `allowlist_guard` state; T3 keys caches by path |
| David pushes to `pr-33` mid-work | Low | T0 checks the head SHA; work moves to `origin`, so later fork pushes don't affect us |
| No accessible property for the live check | Low | Ask first; the mocked suite covers the guard; skipping is recorded |

## Open Questions

- **Live check property.** Which property, if any, may be used for the read-only live check at
  Checkpoint W? This is asked at the checkpoint, not now.
