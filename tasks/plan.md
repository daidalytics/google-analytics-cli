# Implementation Plan: Agent distribution, named profiles, and audience exports

Companion to [SPEC.md](../SPEC.md). Baseline: **997 tests passing** (7.85 s) on `master` @ `3be1a9a`.

## Overview

There are three workstreams from the spec: **A** (distribution), **B** (profiles + ADC), and
**C** (audience exports). This plan splits them into 14 tasks and arranges them for **parallel
execution by subagents in isolated git worktrees**. A, B, and C share almost no files, so each
becomes a *lane* on its own branch. Inside a lane, tasks run in parallel wherever file ownership
doesn't overlap. A fourth lane, **D**, adds skill and README docs for B and C once A's skill is in
the repo.

The critical path is four agent-steps long (`B1 → B2 → B4 → D1`), instead of 14 sequential tasks.

## Architecture Decisions

1. **Lanes = branches = PRs.** These are `feat/agent-distribution` (A), `feat/profiles` (B), and
   `feat/audience-exports` (C). Each is reviewable and revertable on its own. A merges first: it
   carries the skill that D needs, and it could ship alone as 0.4.1 so the `uvx` line goes live
   sooner.
2. **One agent per file-ownership set.** Tasks that edit the same file run in sequence inside a
   single agent (C1→C2→C3 all edit `audience_exports.py`). Tasks with disjoint files run as
   separate agents at the same time.
3. **Contracts before fan-out.** Wherever a downstream task consumes an upstream function, that
   signature is fixed in this plan (see [Interface contracts](#interface-contracts)). A downstream
   agent can then be briefed before the upstream code exists.
4. **Generated files are never hand-merged.** `skills/ga-cli/references/commands.md` (generated
   block) is resolved by re-running `scripts/gen_skill_reference.py --write` after every merge.
5. **`plugin.json` version tracks the *current* `pyproject.toml` version (`0.4.0`) until release.**
   SPEC A4's example shows `0.5.0`, but the version-sync test requires equality, so both are bumped
   together in the release commit.
6. **Subagents never touch live APIs.** All tests are mocked. Live checks (real property, `uvx`
   from PyPI, `claude plugin validate`, `npx skills add`, gcloud ADC) happen at checkpoints, run by
   the orchestrator or the human.

## Dependency Graph

```
                      ┌─ A1  alias + plugin manifests ─────────────────┐
                      ├─ A2  build_cli_schema() ── A3  skill in repo ──┼─▶ CHECKPOINT A ─▶ PR A ─┐
                      ├─ A4  README "Use with AI agents" ──────────────┘                         │
 Wave 0 (orchestr.) ──┤                                                                          │
 spec commit,         ├─ B1  profile foundation ─┬─ B2  credential resolution + ADC ─ B4  status/path/hint ─┐
 lane branches        │                          └─ B3  ga profiles list/delete ─────────────────────────────┤
                      │                                                                ─▶ CHECKPOINT B ─────┤
                      └─ C1  list+get ─ C2  query ─ C3  create+--wait ─▶ CHECKPOINT C ─────────────────────┤
                                                                                                            ▼
                                                                          D1 profiles docs  ∥  D2 exports docs
                                                                          (both need A3 on master)
                                                                                  │
                                                                           FINAL CHECKPOINT
```

## Execution Schedule

| Wave | Runs in parallel | Agents | Blocked on |
|---|---|---|---|
| **0** | Orchestrator: commit SPEC + plan, cut 3 lane branches, resolve Q1/Q2 | 0 | human go-ahead |
| **1** | **A1** · **A2→A3** (one agent) · **A4** · **O1** · **B1** · **C1→C2→C3** (one agent, long-running) | 6 | Wave 0 |
| — | Merge A → **CHECKPOINT A** (+ review agent); merge B1 into `feat/profiles` | | Wave 1 A tasks, B1 |
| **2** | **B2** · **B3** (C lane still running) | 2 | B1 merged |
| **3** | **B4** | 1 | B2 merged |
| — | **CHECKPOINT B** · **CHECKPOINT C** (+ review agent each) | | |
| **4** | **D1** · **D2** | 2 | PR A on `master`; B/C lanes rebased onto it |
| — | **FINAL CHECKPOINT**, then ask about 0.5.0 release | | |

Peak concurrency is 6 agents (wave 1). **O1** (spec Q2, the uvx update notice) was approved and
runs in wave 1, because it owns `upgrade_cmd.py` exclusively.

## File Ownership

A task may edit only the files listed for it. Shared hotspots and how merges resolve them:

| File | Edited by | Merge rule |
|---|---|---|
| `src/ga_cli/main.py` | B1 (root callback), B3 (+1 import, +1 `add_typer`), C1 (+1 import, +1 `add_typer`) | separate hunks; keep both registrations |
| `README.md` | A4 (new top section), D1 (auth/profiles/env vars), D2 (features + command table) | distinct sections |
| `skills/ga-cli/SKILL.md` | A3 (creates), D1 (after "Orient before you query"), D2 (after "Mutations") | fixed insertion anchors |
| `skills/ga-cli/references/commands.md` | A3, D1, D2 | **regenerate, never hand-merge** |
| `src/ga_cli/utils/errors.py` | B2 (`ProfileNotFoundError` classification), B4 (ADC scope hint) | sequential (B4 after B2) |
| `src/ga_cli/auth/{credentials,service_account}.py` | B1 (mkdir target only), B2 (resolution logic) | sequential |
| `tests/conftest.py` | **B1 only** | other agents must not edit; report the need instead |
| `pyproject.toml` | **A1 only** | |
| `tests/test_describe.py` | **A2 only** | C3 puts its `--describe` assertions in `test_audience_exports.py` |
| `CLAUDE.md` | **orchestrator only**, in the main checkout | it is gitignored, so it doesn't exist in worktrees |

## Interface Contracts

These are fixed now so dependent agents can be briefed in parallel:

```python
# B1 → B2, B3, B4   (src/ga_cli/config/constants.py)
DEFAULT_PROFILE = "default"
def set_active_profile(name: str | None) -> None: ...   # ValueError on invalid name
def get_active_profile() -> str: ...
def is_named_profile() -> bool: ...                     # active != "default"
def get_profile_dir() -> Path: ...                      # root for default, root/profiles/<n> otherwise
def get_profiles_root() -> Path: ...                    # root/profiles
def list_profiles() -> list[str]: ...                   # ["default", *sorted existing dirs]
def profile_exists(name: str) -> bool: ...              # "default" always True

# B2 → B4   (src/ga_cli/api/client.py, src/ga_cli/utils/errors.py)
AuthMethod = Literal["service-account", "oauth", "adc"]
def resolve_credentials() -> tuple[Credentials, AuthMethod]: ...  # _get_credentials() wraps this
class ProfileNotFoundError(RuntimeError): ...           # classify_error → (2, "auth_error")

# A2 → A3   (src/ga_cli/utils/describe.py)
def build_cli_schema(typer_app: typer.Typer) -> dict: ...  # == json.loads(`ga --describe`)

# A3 → D1, D2   (scripts/gen_skill_reference.py)
#   python scripts/gen_skill_reference.py            # print generated block
#   python scripts/gen_skill_reference.py --write    # rewrite span between markers
#   python scripts/gen_skill_reference.py --check    # exit 1 on drift
#   markers: <!-- BEGIN GENERATED: ga --describe --> … <!-- END GENERATED -->
```

## Subagent Protocol

Every task agent gets this preamble in its brief:

1. You are in an isolated git worktree. First run
   `git switch -c task/<ID>-<slug> <lane-branch>`.
2. The worktree has **no `CLAUDE.md`** (it is gitignored). Read
   `/Users/gunnargriese/Desktop/python3/agent-cli/google-analytics-cli/CLAUDE.md` for project
   conventions. Then read the SPEC sections named in your task and the files you own.
3. Edit **only** the files in your task's ownership list. If you must touch another file, stop
   and report why rather than editing it.
4. Write the failing tests first, then implement. Never hit a live API; mock every call. Patch
   `google.auth.default` in any test that could reach it.
5. Before committing, run `uv run pytest` (the **full** suite) and
   `uv run ruff check src/ tests/ scripts/`. Both must be green.
6. Commit once per task with a conventional message ending in the `Co-Authored-By` trailer. **Do
   not push and do not open a PR.**
7. Report: branch, commit SHA(s), test count, any deviation from SPEC/plan with the reason, and
   any finding that bears on an Open Question.

The orchestrator (main session):

- Merges task branches into the lane branch.
- Regenerates `commands.md` on conflict.
- Checks each task's `git diff --stat` against its ownership list before merging.
- Runs the full suite after every merge.
- Runs the checkpoints.

---

## Task List

### Lane A: Distribution (`feat/agent-distribution`)

#### A1: Packaging metadata (console-script alias + Claude Code plugin manifests)

**Description:** Add the `google-analytics-cli` entry point so `uvx google-analytics-cli` works
(SPEC A1). Add `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (SPEC A4) with a
test that keeps `plugin.json`'s version equal to the package version.

**Acceptance criteria:**
- [ ] `console_scripts` entry points include both `ga` and `google-analytics-cli` → `ga_cli.main:run`.
- [ ] Both manifests parse and carry the SPEC A4 fields. Plugin `name == "google-analytics-cli"`,
      marketplace `name == "daidalytics"`, `source == "./"`.
- [ ] A test fails if `plugin.json` `version` ≠ `importlib.metadata.version("google-analytics-cli")`.
      Use metadata rather than a TOML parse, because there is no `tomllib` on 3.10.

**Verification:**
- [ ] `uv run pytest tests/test_plugin_manifest.py -v`, plus the full suite and ruff.
- [ ] `uv build && uvx --from dist/*.whl google-analytics-cli --version` prints `ga-cli 0.4.0`.

**Dependencies:** None · **Wave:** 1 · **Scope:** S

**Files:** `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`tests/test_plugin_manifest.py`

#### A2: Extract `build_cli_schema()` from `--describe`

**Description:** Factor a pure `build_cli_schema(app) -> dict` out of `handle_describe_all()`, so
the skill generator and tests can build the schema in-process (SPEC A3).
`handle_describe_all()` keeps its exact print-and-exit behavior.

**Acceptance criteria:**
- [ ] `build_cli_schema(app)` equals `json.loads` of `ga --describe` stdout.
- [ ] `ga --describe` output is byte-identical to before.

**Verification:** `uv run pytest tests/test_describe.py -v`, plus the full suite and ruff.

**Dependencies:** None · **Wave:** 1 (same agent as A3, runs first) · **Scope:** XS

**Files:** `src/ga_cli/utils/describe.py`, `tests/test_describe.py`

#### A3: Skill in repo, with generated reference and guard tests

**Description:**
- Copy `~/.claude/skills-dev/ga-cli/{SKILL.md,references/}` to `skills/ga-cli/`. **Leave the
  source untouched, and skip `evals/` and `.DS_Store`.**
- Wrap the generated part of `references/commands.md` in markers.
- Port `~/.claude/skills-dev/ga-cli-workspace/gen_commands_ref.py` to
  `scripts/gen_skill_reference.py`, implementing the A2→A3 contract.
- Add the SKILL.md **Invocation** section (SPEC A2: the `ga` → `uvx google-analytics-cli`
  substitution rule).
- Add `tests/test_skill.py`.

**Acceptance criteria:**
- [ ] `test_skill.py` covers three cases:
  - Frontmatter `name == "ga-cli"` and `description` present.
  - The generated block in the committed file equals a fresh render (drift).
  - Every `ga <group> <sub>` in a fenced code block under `skills/ga-cli/` exists in
    `build_cli_schema()`.
- [ ] The existence check passes. When it flags stale commands in the draft skill, **fix the skill
      text, never weaken the test**, and list each fix in the report.
- [ ] `skills/ga-cli/` contains no secrets, no evals, and no live property data beyond what the
      draft already documents as an example.

**Verification:**
- [ ] `uv run pytest tests/test_skill.py -v`, plus the full suite and `ruff check … scripts/`.
- [ ] `uv run python scripts/gen_skill_reference.py --check` exits 0.

**Dependencies:** A2 · **Wave:** 1 · **Scope:** M

**Files:** `skills/ga-cli/SKILL.md`, `skills/ga-cli/references/{commands,fields,recipes}.md`,
`scripts/gen_skill_reference.py`, `tests/test_skill.py`

#### A4: README "Use with AI agents" section

**Description:** Add the SPEC A5 section directly under the README intro: the uvx one-liner,
`npx skills add`, and the two `/plugin` commands. Replace the "One-off execution (no install)"
block with the uvx line. The orchestrator separately edits `CLAUDE.md`, which agents can't see:
it adds `.claude-plugin/plugin.json` to release step 1–2 and fixes the auth-priority line.

**Acceptance criteria:**
- [ ] The section appears before "Features", with commands exactly as in SPEC A5.
- [ ] The old `uvx --from git+…` block is gone, and there's no duplicate install path.

**Verification:** Read the rendered markdown and check that the commands match the SPEC
character-for-character. Full suite stays green (docs-only).

**Dependencies:** None (names fixed by SPEC) · **Wave:** 1 · **Scope:** XS

**Files:** `README.md`

### Checkpoint A

- [ ] A1–A4 merged into `feat/agent-distribution`; full suite green; ruff clean.
- [ ] Orchestrator runs:
  - `uv build`
  - `uvx --from dist/*.whl google-analytics-cli --version`
  - `claude plugin validate .`
  - `npx skills add ./ --list`, which shows exactly `ga-cli`
- [ ] A `feature-dev:code-reviewer` agent reviews the lane diff in parallel with the live checks.
- [ ] **Human review.** Decide: open PR A now, and whether to cut **0.4.1** (ask-first) so the
      uvx line is live before B and C land.

---

### Lane B: Profiles and ADC (`feat/profiles`)

#### B1: Profile foundation (selection, paths, implicit creation)

**Description:** Implement the B1→ contract in `constants.py`. Add the root-callback
`--profile` option (`envvar="GA_CLI_PROFILE"`; invalid name → `typer.BadParameter`, exit 1).
Route the four per-profile getters (`credentials`, `config`, `auth-method`, `chat-sessions`)
through `get_profile_dir()`, keeping `client_secret` and `update-check` global. Change the four
writers to `mkdir(parents=True)` the *profile* dir, so first write creates the profile. Extend
`conftest.py` to reset the active profile and call `clear_client_cache()` per test.

**Acceptance criteria:**
- [ ] Precedence is flag > `GA_CLI_PROFILE` > `default`. Names `..`, `a/b`, `.hidden`, and the
      empty string are rejected.
- [ ] The default profile resolves every getter to the root, and **all 997 existing tests pass
      unchanged**. That proves zero migration.
- [ ] `ga --profile x config set default_property_id 1` creates
      `profiles/x/config.json`. Credential files written into a profile are `0o600`.

**Verification:** `uv run pytest tests/test_profiles.py -v`, plus the full suite and ruff.

**Dependencies:** None · **Wave:** 1 · **Scope:** M (8 files, but most edits are one line)

**Files:** `src/ga_cli/config/constants.py`, `src/ga_cli/main.py`, `src/ga_cli/config/store.py`,
`src/ga_cli/config/chat_session.py`, `src/ga_cli/auth/credentials.py` (mkdir only),
`src/ga_cli/auth/service_account.py` (mkdir only), `tests/conftest.py`, `tests/test_profiles.py`

#### B2: Credential resolution, ADC fallback, and the missing-profile error

**Description:** Implement the SPEC B4 table behind
`resolve_credentials() -> (creds, method)`:
- A named profile uses only its own SA, then its own OAuth, then raises `ProfileNotFoundError` or
  "no credentials". It ignores env vars and never reaches ADC.
- The default profile keeps steps 1–4 unchanged, then tries `google.auth.default(scopes=…)`.
- A non-SA `GOOGLE_APPLICATION_CREDENTIALS` defers to ADC instead of raising.
- `has_scope()` returns `True` for ADC.
- `classify_error` maps `ProfileNotFoundError` to exit 2.

**Acceptance criteria:**
- [ ] Parametrized `TestCredentialResolution` covers every B4 row. A named profile with
      `GOOGLE_APPLICATION_CREDENTIALS` *and* `GA_CLI_SERVICE_ACCOUNT` exported still uses the
      profile's credentials.
- [ ] An unknown named profile exits 2 with the SPEC B2 message (lists known profiles) and builds
      no API client.
- [ ] ADC is reached only when nothing else is configured. A configured OAuth still wins.
      `google.auth.default` is patched in every test.

**Verification:** `uv run pytest tests/test_api_client.py tests/test_service_account.py tests/test_credentials.py -v`, plus the full suite and ruff.

**Dependencies:** B1 · **Wave:** 2 · **Scope:** M

**Files:** `src/ga_cli/api/client.py`, `src/ga_cli/auth/service_account.py`,
`src/ga_cli/auth/credentials.py`, `src/ga_cli/utils/errors.py`, `tests/test_api_client.py`

#### B3: `ga profiles list` / `ga profiles delete`

**Description:** Add a new `profiles` command group (SPEC B5).
- `list` works offline. It reads files only and shows name, active marker, method
  (`service-account`/`oauth`/`none`), SA email when known, and default property. It supports
  table and JSON.
- `delete NAME [--yes]` confirms, refuses `default`, removes `profiles/NAME/`, and never touches
  the SA key the profile points to.
- Register the group in `main.py`.

**Acceptance criteria:**
- [ ] `list -o json` makes no API call or credential refresh and marks the active profile (flag
      or env).
- [ ] `delete default` exits 1. `delete` without `--yes` prompts. The SA key file still exists
      after deleting a profile that pointed to it.

**Verification:** `uv run pytest tests/test_profiles_cmd.py -v`, plus the full suite and ruff.

**Dependencies:** B1 (parallel with B2) · **Wave:** 2 · **Scope:** S

**Files:** `src/ga_cli/commands/profiles.py`, `src/ga_cli/main.py` (registration only),
`tests/test_profiles_cmd.py`

#### B4: Profile- and ADC-aware `auth status`, `config path`, and ADC scope hint

**Description:**
- `ga auth status` (table + JSON) adds `profile` and reports `adc` via `resolve_credentials()`.
- `ga auth login` / `logout` affect only the active profile. The B1 paths already do this; this
  task adds tests that prove it.
- `ga config path` prints the active profile dir.
- On a 403 `ACCESS_TOKEN_SCOPE_INSUFFICIENT` while the method is `adc`, the error appends the
  SPEC B4 `gcloud … --scopes=…` hint.

**Acceptance criteria:**
- [ ] `auth status -o json` includes `"profile"`, and `"method": "adc"` when ADC is active.
- [ ] `logout` under `--profile x` leaves the root `credentials.json` intact.
- [ ] The scope hint appears only for `adc` + `ACCESS_TOKEN_SCOPE_INSUFFICIENT`, not for other
      403s or other methods.

**Verification:** `uv run pytest tests/test_auth_cmd.py tests/test_config_cmd.py tests/test_errors.py -v`, plus the full suite and ruff.

**Dependencies:** B2 · **Wave:** 3 · **Scope:** M

**Files:** `src/ga_cli/commands/auth_cmd.py`, `src/ga_cli/commands/config_cmd.py`,
`src/ga_cli/utils/errors.py`, `tests/test_auth_cmd.py`, `tests/test_config_cmd.py`

### Checkpoint B

- [ ] B1–B4 merged into `feat/profiles`; full suite green; ruff clean.
- [ ] Live checks (orchestrator, ask-first):
  - The default OAuth profile on `250400352` (activeUsers/sessions only) gives output identical
    to `master`.
  - An SA-keyed named profile works.
  - `--profile typo` exits 2.
  - The human checks ADC, which needs `gcloud auth application-default login`.
- [ ] A review agent reviews the lane diff, focusing on the "named profile never falls back"
      invariant.
- [ ] **Human review.**

---

### Lane C: Audience exports (`feat/audience-exports`), one agent running C1→C2→C3

#### C1: `ga audience-exports list` / `get`

**Description:** Create `commands/audience_exports.py`, mirroring `audiences.py`'s shape, against
`get_data_client()` (v1beta), and register it in `main.py`.
- `list -p P` paginates via `paginate_all`. The table shows export ID (parsed from `name`),
  audience display name, state, rows, % complete, and created.
- `get -p P --export-id E` (long-only flag).

**Acceptance criteria:**
- [ ] `list` follows `nextPageToken`. The table extracts the numeric ID from
      `properties/P/audienceExports/E`.
- [ ] `get` calls `properties/P/audienceExports/E`. `-o json` is raw passthrough.

**Verification:** `uv run pytest tests/test_audience_exports.py -v`, plus the full suite and ruff.

**Dependencies:** None · **Wave:** 1 · **Scope:** S

**Files:** `src/ga_cli/commands/audience_exports.py`, `src/ga_cli/main.py` (registration only),
`tests/test_audience_exports.py`

#### C2: `ga audience-exports query`

**Description:** `query -p P --export-id E [--limit N] [--offset N]`. JSON output is the raw
`QueryAudienceExportResponse`. The table has one column per dimension, taken from
`audienceExport.dimensions`. A 400/FAILED_PRECONDITION on a non-ACTIVE export maps to "export is
still CREATING (N%) — try again later".

**Acceptance criteria:**
- [ ] `limit`/`offset` are sent as strings (int64 in the API) only when provided.
- [ ] Table columns follow the export's dimension order. An empty `audienceRows` renders the
      standard empty-table output.
- [ ] A non-ACTIVE export error gives the friendly message with a non-zero exit, not a raw API
      dump.

**Verification:** Same as C1.

**Dependencies:** C1 · **Wave:** 1 (same agent) · **Scope:** S

**Files:** same as C1 (minus `main.py`)

#### C3: `ga audience-exports create` with `--dry-run` and `--wait`

**Description:** `create -p P --audience-id A --dimensions d1,d2`.
- `--audience-id` accepts a numeric ID or a full `properties/P/audiences/A` name.
- `--dry-run` uses `handle_dry_run()`, which makes the command appear as `mutative` in
  `--describe`.
- `--wait [--timeout 1800]` polls `get` (10 s backing off to 60 s; progress to stderr) and exits
  0 on ACTIVE, 3 on FAILED (`errorMessage`), or 3 on timeout.
- Export name extraction (SPEC Q3) tries `Operation.response.name`, then `Operation.metadata`,
  then falls back to `list` (newest `beginCreatingTime` for that audience). All three paths are
  mocked.

**Acceptance criteria:**
- [ ] `--dry-run` prints the exact body (`audience`, `dimensions:[{dimensionName}]`) and builds no
      client. `--describe` marks `create` mutative; assert this in `test_audience_exports.py`,
      not `test_describe.py`.
- [ ] `--wait` handles ACTIVE, FAILED, and timeout with the exit codes above. `time.sleep` and
      the clock are patched, so there are no real sleeps.
- [ ] Every name-extraction path, including the `list` fallback, is covered.

**Verification:** Same as C1.

**Dependencies:** C2 · **Wave:** 1 (same agent) · **Scope:** M

**Files:** same as C2

### Checkpoint C

- [ ] C1–C3 merged into `feat/audience-exports`; full suite green; ruff clean.
- [ ] Live: `list`/`get`/`query` against an existing export. A live `create`, which resolves Q3 by
      showing the real Operation shape, is **ask-first** because it charges quota tokens.
- [ ] A review agent reviews the lane diff.
- [ ] **Human review.**

---

### Lane D: Skill and README for B and C (after PR A is on `master`)

The orchestrator first rebases `feat/profiles` and `feat/audience-exports` onto `master`, so A3's
skill, generator, and drift test are present. D1 runs on `feat/profiles` and D2 on
`feat/audience-exports`, in parallel.

#### D1: Profiles and ADC in the skill and README

**Description:**
- **SKILL.md:** add a "Profiles" section after "Orient before you query":
  - Put `--profile` before the group, or use `GA_CLI_PROFILE`.
  - **Never pick or switch a profile the user didn't name.** Run `ga profiles list -o json` and
    ask.
  - An unknown profile exits 2.
- **README:** profiles and ADC under Setup; add a `GA_CLI_PROFILE` row to the env-var table and
  `ga profiles` to the command table.
- Regenerate `commands.md`.

**Acceptance criteria:**
- [ ] `gen_skill_reference.py --check` passes, and `test_skill.py` passes, including the
      existence check for every new `ga profiles …` example.
- [ ] The SKILL.md "Orient before you query" block includes `ga profiles list -o json`.

**Verification:** Full suite (includes `test_skill.py`) and ruff.

**Dependencies:** A3 on `master`, B3, B4 · **Wave:** 4 · **Scope:** S

**Files:** `skills/ga-cli/SKILL.md`, `skills/ga-cli/references/commands.md`, `README.md`

#### D2: Audience exports in the skill and README

**Description:**
- **SKILL.md:** add an "Audience exports" section after "Mutations":
  - Run `create` with `--dry-run` first.
  - **Never use `--wait` in an agent session.** It outlives tool timeouts. Report the export ID
    and `get` later.
  - Run `query` only once the export is ACTIVE.
- **`recipes.md`:** one recipe.
- **README:** a Data API feature bullet and an `audience-exports` command-table row.
- Regenerate `commands.md`.

**Acceptance criteria:**
- [ ] The drift check and the command-existence test pass.
- [ ] The skill states the no-`--wait` rule and the dry-run-first rule explicitly.

**Verification:** Full suite and ruff.

**Dependencies:** A3 on `master`, C3 · **Wave:** 4 · **Scope:** S

**Files:** `skills/ga-cli/SKILL.md`, `skills/ga-cli/references/{commands,recipes}.md`, `README.md`

### Final Checkpoint

- [ ] PRs B and C are each green on CI (3.10 / 3.12 / 3.13).
- [ ] Whichever merges second regenerates `commands.md` after rebasing.
- [ ] SPEC Success Criteria 1–15 each map to a named test or a recorded live check.
- [ ] SPEC.md living updates: status, resolved Q3, and any deviations.
- [ ] **Ask** about the 0.5.0 bump. The release commit bumps `pyproject.toml` **and**
      `.claude-plugin/plugin.json`.

---

### Optional

#### O1: Update notice under uvx (SPEC Q2), approved, runs in wave 1 on `feat/agent-distribution`

**Description:** If `sys.prefix` is inside uv's cache dir (an ephemeral `uvx` env), suppress the
daily "Run 'ga upgrade'" notice.

**Acceptance criteria:**
- [ ] The notice is suppressed under a mocked uvx prefix and unchanged otherwise.

**Dependencies:** None · **Wave:** any (sole owner) · **Scope:** XS

**Files:** `src/ga_cli/commands/upgrade_cmd.py`, `tests/test_upgrade_cmd.py`

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Worktrees lack gitignored files (`CLAUDE.md`, `.venv`) | Med | The protocol points agents to the absolute `CLAUDE.md` path. `uv run` builds a venv on first use (one-off cost). |
| An agent edits outside its ownership list and causes surprise conflicts | Med | The orchestrator checks `git diff --stat` against ownership before every merge, and the protocol says "stop and report". |
| `_active_profile` or cached API clients leak between tests | High | B1 owns the `conftest.py` reset and `clear_client_cache()`. B2's resolution tests also clear explicitly. |
| A dev machine's real gcloud ADC leaks into tests via `google.auth.default` | High | Protocol rule 4 (always patch it), plus a B2 test asserting it's patched in the resolution suite. |
| The draft skill references commands or flags that no longer exist | Med | Expected. A3's existence test surfaces them, and A3 fixes the text. |
| The real `create` Operation shape is unknown (Q3) | Med | C3 implements all three extraction paths. A live create at Checkpoint C (ask-first) confirms which one is real. |
| `commands.md` conflicts across lanes | Low | Generated span; regenerate, never hand-merge. |
| `plugin.json` version drifts at release | Med | The version-sync test, plus a CLAUDE.md release-step update. |
| B1 is the widest task (8 files) and sits on the critical path | Med | Most edits are one-line mkdir and getter changes. It starts in wave 1 with no dependencies, so it finishes while A and C are still running. |

## Open Questions

All resolved on 2026-10-14:

1. ~~Spec Q1, `--profile` placement~~ → **root-only** (`ga --profile X …`). There is no argv
   hoisting.
2. ~~Spec Q2, uvx update notice~~ → **suppress it**. **O1 runs in wave 1.**
3. ~~Commit permission for wave 0~~ → **granted.** Commits are local only. Nothing is pushed
   until a PR is approved.
