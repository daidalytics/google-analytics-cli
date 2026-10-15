# Spec: Agent distribution, named profiles, and audience exports

Status: **Shipped in 0.6.0** (2026-10-14): #35 (profiles, ADC fallback, agent distribution) and
#36 (audience exports). #37 corrected the recommended ADC login. See Implementation Notes at the end.
Released in: **0.6.0** (tag `v0.6.0`, on PyPI)
Date: 2026-10-14

Previous spec (ResponseMetaData / Data Notes, shipped in 0.4.0) lives in git history at `83d793b`.

---

## Objective

This CLI covers far more of GA4 than an agent needs to get started, but getting an agent to
*use* it takes more steps than it should. Four gaps stand in the way:

1. **No zero-install path.** An agent has to install a Python tool before it can run a single
   command. `uvx google-analytics-cli` should just work.
2. **No skill packaging.** A tested GA skill exists, but only on the author's machine. It should
   install in one command, through `npx skills add` (Claude Code, Cursor, Codex) or the Claude
   Code `/plugin` flow.
3. **One identity at a time.** Switching between clients means logging out and back in, and
   re-setting the default property. A named profile (`--profile client-a`) should switch both at
   once. A gcloud ADC fallback should cover machines where nothing else is configured.
4. **One Data API gap: audience exports.** Exporting the users in an audience isn't possible yet.

This spec closes those four gaps.

**Non-goals:**
- A raw-JSON-only output mode (table and JSON output stay as they are).
- Dropping the OAuth flow.
- Porting to another language.

### Users

1. **Agent users** (Claude Code, Cursor, Codex) who want a working GA skill in one command, with no
   Python toolchain set up beforehand.
2. **Consultants working across several clients**, i.e. the author's own multi-client work. They
   need to switch *identity and target property together* with one flag, without logging in again.
3. **Scripts and agents that need full Data API coverage**, here exporting the users in an audience.

### Workstreams (shipped in this order)

| | Workstream | Why this order |
|---|---|---|
| **A** | Distribution: `uvx google-analytics-cli`, skill in-repo, Claude Code plugin manifests, README | Distribution is the main gap. A depends on nothing else. |
| **B** | Named profiles (credentials + defaults) and a gcloud ADC fallback | Changes the auth/config core, so it must land before C adds a new command group. |
| **C** | `ga audience-exports create/list/get/query` | Purely additive, and the least urgent. |

The skill and its generated command reference are updated at the end of **each** workstream, not
once at the end.

### Assumptions

1. **The skill already exists.** `~/.claude/skills-dev/ga-cli/` (SKILL.md + `references/{commands,
   fields,recipes}.md`, eval'd over two iterations) is the content to ship. It is *moved* into the
   repo, not rewritten. Its `evals/` folder is **not** shipped, because `npx skills add` copies the
   whole skill folder to users.
2. **The skill name stays `ga-cli`.** It has been eval'd under that name. A distinctive name is
   also less likely to collide in `~/.claude/skills/` with other Google Analytics skills that
   `npx skills add` might install alongside it.
3. **Plugin name is `google-analytics-cli`** (matching the repo and PyPI). **Marketplace name is
   `daidalytics`.** Install is `/plugin install google-analytics-cli@daidalytics`. In Claude Code
   the skill appears as `google-analytics-cli:ga-cli`.
4. **The marketplace lives in this repo.** There are no sibling CLIs to bundle yet, so a separate
   org-level marketplace repo is out of scope.
5. **gcloud ADC fallback is in scope.** CLAUDE.md already lists ADC in the auth priority, but
   `api/client.py` doesn't implement it (only SA → OAuth). This spec makes the docs true rather than
   deleting the claim.
6. **The default profile is the config root itself.** Existing installs keep working with **no
   migration**: same files, same env vars, same precedence.
7. **There is no sticky "active profile".** Selection is only per invocation (`--profile`) or per
   shell (`GA_CLI_PROFILE`). See Design B3.
8. **`--profile` is a root-level global option**, like `-q` and `--no-color`:
   `ga --profile client-a reports run …`. Accepting it anywhere in argv is an open question (Q1).
9. **Output stays as it is.** Table by default on a TTY, JSON otherwise. We don't add a
   raw-passthrough mode.
10. **No new runtime dependencies.** ADC uses `google.auth.default()`, which ships with `google-auth`
    (already a dependency).

→ Correct any of these now, or I'll proceed with them.

---

## Design — A. Distribution

### A1. `uvx google-analytics-cli` works

`uvx <pkg>` runs the executable **named after the package**. The PyPI package is
`google-analytics-cli`, but its only console script is `ga`, so `uvx google-analytics-cli` currently
fails with "package does not provide executable". The fix is to add a second entry point:

```toml
[project.scripts]
ga = "ga_cli.main:run"
google-analytics-cli = "ga_cli.main:run"   # NEW: makes `uvx google-analytics-cli` work
```

Side benefit: `pipx` and `uv tool install` now install both names. `google-analytics-cli` avoids the
`alias ga='git add'` collision that the README Troubleshooting section already warns about.

**Sequencing constraint:** `uvx google-analytics-cli` only works once a release carrying this entry
point is on PyPI. README text and skill instructions that rely on it must not be published (pushed
to `master`) before that release. Until then, the working form is
`uvx --from google-analytics-cli ga`.

### A2. The skill moves into the repo

```
skills/ga-cli/
├── SKILL.md                 # from ~/.claude/skills-dev/ga-cli/SKILL.md
└── references/
    ├── commands.md          # generated block + hand-written sections (see A3)
    ├── fields.md
    └── recipes.md
```

`skills/<name>/SKILL.md` is the layout that both `npx skills add` (vercel-labs/skills) and Claude
Code plugins discover by default. Neither tool cares that the repo is Python.

SKILL.md gains an **Invocation** section near the top, with this decision:

> Use `ga` if it is on PATH (`command -v ga`). Otherwise substitute `uvx google-analytics-cli` for
> `ga` in every command in this skill and its references. Auth and config live in
> `~/.config/ga-cli/` either way, so the two are interchangeable. If neither `ga` nor `uv` exists,
> tell the user to install one (`uv tool install google-analytics-cli` or
> `curl -LsSf https://astral.sh/uv/install.sh | sh`) and stop.

The instruction is a substitution rule, not a shell variable, because agents' shell state does not
persist between tool calls.

### A3. `references/commands.md` is generated and drift-checked

The command table in `commands.md` is produced from `ga --describe` (the existing
`~/.claude/skills-dev/ga-cli-workspace/gen_commands_ref.py`). The file also has hand-written
sections ("Short-flag collisions", "Things the schema won't tell you") that must survive
regeneration. So:

- The generated part sits between `<!-- BEGIN GENERATED: ga --describe -->` and
  `<!-- END GENERATED -->` markers. The generator rewrites only that span.
- The generator moves to `scripts/gen_skill_reference.py` (dev-only, like
  `scripts/check_api_changes.py`). It builds the schema **in-process** rather than shelling out to
  `ga`, so it uses the checked-out code and not whatever `ga` is on PATH.
- To support that, `utils/describe.py` factors a pure `build_cli_schema(app) -> dict` out of
  `handle_describe_all()`, which keeps its current print-and-exit behavior.
- A pytest drift check (`tests/test_skill.py`) fails when the committed generated block differs from
  a fresh render. The failure message names the fix:
  `python scripts/gen_skill_reference.py --write`. This runs in existing CI with **no workflow
  change**.

### A4. Claude Code plugin manifests

`.claude-plugin/plugin.json`:

```json
{
  "name": "google-analytics-cli",
  "version": "0.5.0",
  "description": "Google Analytics 4 skill for AI agents: reports, realtime, and GA4 admin via the ga CLI",
  "author": { "name": "Gunnar Griese", "url": "https://gunnargriese.com" },
  "homepage": "https://github.com/daidalytics/google-analytics-cli",
  "repository": "https://github.com/daidalytics/google-analytics-cli",
  "license": "MIT",
  "keywords": ["google-analytics", "ga4", "analytics", "cli"]
}
```

`.claude-plugin/marketplace.json`:

```json
{
  "name": "daidalytics",
  "owner": { "name": "Gunnar Griese" },
  "description": "Analytics CLIs and skills for AI agents",
  "plugins": [
    {
      "name": "google-analytics-cli",
      "source": "./",
      "description": "Google Analytics 4 skill for AI agents, driving the ga CLI"
    }
  ]
}
```

- Skills are picked up by the default `skills/` scan, so no `skills` field is needed.
- **`plugin.json` `version` must equal `pyproject.toml` `version`.** When a version is set, Claude
  Code only offers plugin updates on a version change, so a stale value would freeze users on old
  skill text. A pytest check enforces equality, and the CLAUDE.md release steps add
  `.claude-plugin/plugin.json` to the version-bump commit.
- Manual verification: `claude plugin validate .` (CI doesn't have `claude`, so pytest covers JSON
  shape, required fields, and version sync instead).

### A5. README

A new **"Use with AI agents"** section goes directly under the intro, ahead of Features:

```bash
# Run without installing (needs uv)
uvx google-analytics-cli --help

# Add the skill to Claude Code, Cursor, Codex, …
npx skills add daidalytics/google-analytics-cli
```

```
# Or as a Claude Code plugin
/plugin marketplace add daidalytics/google-analytics-cli
/plugin install google-analytics-cli@daidalytics
```

The existing "One-off execution (no install)" block is replaced by the uvx line. Profile and ADC
docs land with workstream B.

---

## Design — B. Named profiles and ADC fallback

### B1. A profile is a config namespace

```
~/.config/ga-cli/                     # config root (GA_CLI_CONFIG_DIR still overrides)
├── client_secret.json                # GLOBAL: OAuth client = the app's identity, shared by all
├── update-check.json                 # GLOBAL
├── config.json                       # ┐
├── credentials.json                  # │ the "default" profile: today's files, untouched
├── auth-method.json                  # │
├── chat-sessions.json                # ┘
└── profiles/
    └── client-a/
        ├── config.json               # default_property_id, default_account_id, output_format
        ├── credentials.json          # OAuth token, 0o600
        ├── auth-method.json          # SA key *path* + email (key file is not copied)
        └── chat-sessions.json        # chat --continue state is per identity
```

| File | Scope | Reason |
|---|---|---|
| `config.json`, `credentials.json`, `auth-method.json`, `chat-sessions.json` | per profile | identity and target property switch together |
| `client_secret.json` | global | one OAuth client authenticates many Google identities |
| `update-check.json` | global | it's about the installed binary, not a client |

Profile names must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`. That rejects `.`, `..`, `/`, and hidden
names, which guards against path traversal. `default` is reserved and means the root.

### B2. Selection

Precedence: `ga --profile NAME` > `GA_CLI_PROFILE` > `default`.

This is implemented as a Typer root-callback option with `envvar="GA_CLI_PROFILE"`, which calls
`set_active_profile()` before any command runs. Only the per-profile path getters in
`config/constants.py` change. Everything downstream (store, credentials, service_account,
chat_session) already goes through those getters and needs no edits.

**Profiles are created implicitly** on first write:

- `ga --profile client-a auth login [--service-account key.json]`
- `ga --profile client-a config set default_property_id 123`
- `ga --profile client-a config setup`

**A read against a non-existent named profile is an error, never a fallback.** It exits with code 2
(`auth_error`) and this message:

```
Profile 'clinet-a' does not exist. Known profiles: client-a, client-b, default.
Create it with: ga --profile clinet-a auth login
```

### B3. Why no sticky active profile

A `ga profiles use client-a` that persists to disk would be hidden global state. A later shell, or
an agent in a different session, would quietly run against the wrong client. The skill already
names this as the most dangerous failure ("a report against the wrong property looks exactly like
an answer"). `GA_CLI_PROFILE` covers the "work on one client all afternoon" case while staying
scoped to one shell.

### B4. Credential resolution

| Step | **Named profile** (`--profile X` / `GA_CLI_PROFILE=X`) | **Default profile** |
|---|---|---|
| 1 | `profiles/X/auth-method.json` service account | `GA_CLI_SERVICE_ACCOUNT` |
| 2 | `profiles/X/credentials.json` OAuth | `GOOGLE_APPLICATION_CREDENTIALS` (SA key) |
| 3 | **error**: "profile X has no credentials" | saved SA (`auth-method.json`) |
| 4 | | OAuth (`credentials.json`) |
| 5 | | **NEW:** `google.auth.default(scopes=OAUTH_SCOPES)`, i.e. gcloud ADC |
| 6 | | error (message lists all options, including ADC) |

- **A named profile never falls back.** It ignores `GA_CLI_SERVICE_ACCOUNT`,
  `GOOGLE_APPLICATION_CREDENTIALS`, the default profile, and ADC. A globally exported
  `GOOGLE_APPLICATION_CREDENTIALS` (common on GCP dev machines) must not silently override an
  explicitly chosen client.
- **Default-profile steps 1–4 are unchanged**, so existing users see byte-identical behavior. ADC is
  only reached where today the user gets "Not authenticated".
- **Behavior fix:** when `GOOGLE_APPLICATION_CREDENTIALS` points to a non-service-account file
  (e.g. `external_account` from Workload Identity Federation in GitHub Actions), today
  `validate_service_account_key()` raises `ValueError`. Instead, the CLI skips step 2 and lets
  step 5 handle it through `google.auth.default()`. That enables keyless CI.
- **ADC scope caveat.** gcloud *user* ADC ignores requested scopes unless it was created with them.
  On a 403 `ACCESS_TOKEN_SCOPE_INSUFFICIENT` while the active method is ADC, the error adds a
  hint with two logins (see the Implementation Note on #37): `gcloud auth application-default login --client-id-file=CLIENT_SECRET_JSON --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform`, or
  `gcloud auth application-default login --impersonate-service-account=SA_EMAIL`.
- `auth.credentials.has_scope()` returns `True` for ADC, because the scopes can't be determined
  (this matches the existing service-account rule).

### B5. Profile-aware command changes

| Command | Change |
|---|---|
| `ga --profile X …` | new global option (also `GA_CLI_PROFILE`) |
| `ga profiles list [-o json]` | **new.** Columns: name, active marker, auth method (`service-account` / `oauth` / `none`), SA email when known, default property. Offline: reads files only, makes no API calls. |
| `ga profiles delete NAME [--yes]` | **new.** Removes `profiles/NAME/` after confirmation. Refuses `default`. Never touches the SA key file the profile points to. |
| `ga auth status` | adds `profile` to table and JSON output; adds `adc` as a method |
| `ga auth login` / `logout` | write to or clear the active profile's files only |
| `ga config get/set/unset/reset/setup/path` | operate on the active profile; `path` prints the profile dir |

---

## Design — C. Audience exports

A new group, **`ga audience-exports`** (Data API v1beta, `properties.audienceExports`), is kept
separate from `ga audiences` (Admin API configuration) because the two APIs and their semantics
differ.

| Command | API | Notes |
|---|---|---|
| `create -p P --audience-id A --dimensions deviceId,userId [--wait] [--timeout 1800] [--dry-run]` | `create` → `Operation` | `--audience-id` accepts a numeric ID or `properties/P/audiences/A`. `dimensions` is required by the API and passed through unvalidated. Marked mutative (`--dry-run` support), because it creates a server resource and charges quota tokens. |
| `list -p P [-o]` | `list` (paginated via `paginate_all`) | Table: export ID, audience, state, rows, % complete, created. |
| `get -p P --export-id E [-o]` | `get` | |
| `query -p P --export-id E [--limit N] [--offset N] [-o]` | `query` | JSON: raw `QueryAudienceExportResponse`. Table: one column per exported dimension. |

- **New ID flags are long-only** (`--audience-id`, `--export-id`). The skill reference already
  spends a table on short-flag collisions (`-a` means `--account-id` in most groups but
  `--annotation-id` in annotations), so we don't add more.
- **`--wait`** polls `get` (10 s interval, backing off to 60 s) until `ACTIVE` (prints the export,
  exit 0), `FAILED` (prints `errorMessage`, exit 3), or `--timeout` (exit 3, "still CREATING —
  check with `ga audience-exports get`"). Progress (`percentageCompleted`) goes to stderr. Exports
  typically take ~15 min.
- **The skill tells agents not to use `--wait`**, because it outlives agent tool-call timeouts.
  Agents should `create`, report the export ID, and `get` later.
- **`query` on a non-ACTIVE export:** the API error maps to a friendly message ("export is still
  CREATING (42%) — try again later") instead of a raw 400.
- Scope: `analytics.readonly` is enough, so no re-authentication is needed.

---

## Commands

### New and changed user-facing commands

```bash
# A — distribution
uvx google-analytics-cli --help
uvx google-analytics-cli reports run -p 123 -m activeUsers -d date --end-date yesterday -o json
npx skills add daidalytics/google-analytics-cli
/plugin marketplace add daidalytics/google-analytics-cli
/plugin install google-analytics-cli@daidalytics

# B — profiles and ADC
ga --profile client-a auth login --service-account ~/keys/client-a.json
ga --profile client-a config set default_property_id 250400352
ga --profile client-a reports run -m sessions -d date -o json
GA_CLI_PROFILE=client-a ga reports run -m sessions -d date
ga profiles list -o json
ga profiles delete client-a --yes
ga auth status -o json                     # now includes "profile"
gcloud auth application-default login --client-id-file=CLIENT_SECRET_JSON --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform
ga reports run -p 123 -m sessions          # default profile, nothing configured → ADC

# C — audience exports
ga audience-exports create -p 123 --audience-id 456 --dimensions deviceId --dry-run
ga audience-exports create -p 123 --audience-id 456 --dimensions deviceId,userId -o json
ga audience-exports list -p 123 -o json
ga audience-exports get -p 123 --export-id 789 -o json
ga audience-exports query -p 123 --export-id 789 --limit 10000 --offset 0 -o json
```

### Dev commands

```bash
uv sync
uv run pytest
uv run pytest tests/test_profiles.py tests/test_audience_exports.py tests/test_skill.py -v
uv run ruff check src/ tests/ scripts/
uv run python scripts/gen_skill_reference.py --write    # after any command/flag change
uv build
claude plugin validate .                                 # manual, before release
uvx --from dist/google_analytics_cli-0.5.0-py3-none-any.whl google-analytics-cli --version
```

---

## Project Structure

```
.claude-plugin/
├── plugin.json                         # NEW (A4)
└── marketplace.json                    # NEW (A4)
skills/ga-cli/                          # NEW (A2), moved from ~/.claude/skills-dev/ga-cli
├── SKILL.md
└── references/{commands,fields,recipes}.md
scripts/
└── gen_skill_reference.py              # NEW (A3), dev-only
src/ga_cli/
├── main.py                             # MODIFY: --profile root option; register profiles + audience-exports
├── config/constants.py                 # MODIFY: active profile, get_profile_dir(), per-profile getters
├── api/client.py                       # MODIFY: profile-aware resolution + ADC step
├── auth/credentials.py                 # MODIFY: has_scope() ADC case
├── auth/service_account.py             # MODIFY: non-SA GOOGLE_APPLICATION_CREDENTIALS defers to ADC
├── commands/auth_cmd.py                # MODIFY: status shows profile and adc
├── commands/config_cmd.py              # MODIFY: path shows profile dir
├── commands/profiles.py                # NEW: list, delete
├── commands/audience_exports.py        # NEW: create, list, get, query
└── utils/describe.py                   # MODIFY: extract build_cli_schema()
tests/
├── conftest.py                         # MODIFY: reset active profile + client caches per test
├── test_profiles.py                    # NEW
├── test_api_client.py                  # MODIFY: resolution table + ADC
├── test_audience_exports.py            # NEW
└── test_skill.py                       # NEW: manifests, frontmatter, drift, command existence
pyproject.toml                          # MODIFY: google-analytics-cli script alias
README.md                               # MODIFY: agents section, profiles, ADC, env vars
CLAUDE.md                               # MODIFY (local only; gitignored): auth priority, release step
```

---

## Code Style

This follows existing conventions: module docstrings, `from __future__ import annotations`, path
getters in `constants.py`, and `require_options` / `get_effective_value` / `handle_error` in
commands. Profile selection lives with the paths, so callers don't change:

```python
# config/constants.py
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DEFAULT_PROFILE = "default"

_active_profile: str = DEFAULT_PROFILE


def set_active_profile(name: str | None) -> None:
    """Select the profile for this process. Called once from the root callback.

    Raises ValueError for names that could escape the profiles directory.
    """
    global _active_profile
    name = name or DEFAULT_PROFILE
    if not PROFILE_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid profile name: {name!r}")
    _active_profile = name


def get_profile_dir() -> Path:
    """Directory holding the active profile's auth and config files.

    The default profile *is* the config root, so installs that predate
    profiles keep working with no migration.
    """
    root = get_config_dir()
    if _active_profile == DEFAULT_PROFILE:
        return root
    return root / "profiles" / _active_profile


def get_credentials_path() -> Path:
    """Path to the active profile's stored OAuth credentials."""
    return get_profile_dir() / "credentials.json"


def get_client_secret_path() -> Path:
    """Path to the OAuth client secret. Global: one app identity for all profiles."""
    return get_config_dir() / "client_secret.json"
```

Conventions this encodes:

- **One choke point.** Only the path getters know about profiles. A file that should stay global
  calls `get_config_dir()`, and that choice is visible in the getter, not scattered across call
  sites.
- **Validation is a `ValueError` in core code.** The Typer callback converts it to
  `typer.BadParameter`. `constants.py` stays free of Typer.
- **New commands copy the shape of an existing sibling**: `audience_exports.py` mirrors
  `audiences.py` (option order, `try/except → handle_error`, `output()`), and `create` uses
  `handle_dry_run()` like `custom_dimensions.py`.

---

## Testing Strategy

Tests use `pytest` and `typer.testing.CliRunner`, grouped by class, with every API call mocked. The
existing `isolated_config_dir` autouse fixture already points `GA_CLI_CONFIG_DIR` at `tmp_path`.
Profile dirs nest under it for free. The fixture gains a reset of the active profile and a
`clear_client_cache()` call.

| File | Classes and key cases |
|---|---|
| `test_profiles.py` | `TestProfileSelection`: flag beats env beats default; invalid names (`..`, `a/b`, `.hidden`) rejected with exit 1. `TestProfilePaths`: per-profile vs global getters; default profile resolves to the root (**regression guard: zero migration**). `TestImplicitCreation`: `auth login` / `config set` create the dir; credentials file is `0o600`. `TestMissingProfile`: read on an unknown profile exits 2 and lists known profiles; does **not** touch default creds. `TestProfilesList` / `TestProfilesDelete`: offline listing, refuses `default`, confirmation, `--yes`, never deletes the SA key file. |
| `test_api_client.py` | `TestCredentialResolution`: parametrized over the B4 table. Named profile **ignores** `GOOGLE_APPLICATION_CREDENTIALS` and `GA_CLI_SERVICE_ACCOUNT` (the core safety test). Default profile steps 1–4 unchanged. ADC reached only when nothing else is configured (`google.auth.default` patched). Non-SA `GOOGLE_APPLICATION_CREDENTIALS` defers to ADC instead of raising. |
| `test_auth_cmd.py` | `status` JSON includes `profile`; `adc` method rendered; ADC 403 scope hint. |
| `test_audience_exports.py` | `TestCreate`: body shape, full-name vs numeric `--audience-id`, `--dry-run` payload, `--wait` → ACTIVE / FAILED / timeout (patch `time.sleep` and monotonic clock). `TestList` (pagination), `TestGet`, `TestQuery`: table columns from dimensions, JSON passthrough, non-ACTIVE friendly error. |
| `test_skill.py` | Manifests parse; required fields present; **`plugin.json` version == pyproject version**. SKILL.md frontmatter has `name == "ga-cli"` and a `description`. **Generated block in `commands.md` == fresh render.** Every `ga <group> <sub>` in a fenced code block across `skills/ga-cli/**/*.md` exists in `build_cli_schema()`, which guards against the `ga property-settings get` class of error from skill iteration 1. |
| `test_describe.py` | `build_cli_schema()` matches `--describe` output; new commands appear with the correct `mutative` flag. |

**Live verification** (manual, at each workstream checkpoint; not in CI):

- **A:** `uv build`, then run the built wheel through `uvx`, then `claude plugin validate .`, then
  `npx skills add ./ --list` from the repo root.
- **B:** OAuth default profile on `250400352` must show unchanged output. Then an SA-keyed named
  profile, an unknown profile, and ADC via `gcloud auth application-default login`. Per memory,
  live tests on `250400352` use activeUsers / sessions / key events, not revenue.
- **C:** `list`, `get`, and `query` on an existing export run freely. A live `create` charges quota
  tokens, so **ask first** before running one.

---

## Boundaries

**Always:**

- Run `uv run pytest` and `uv run ruff check src/ tests/ scripts/` before every commit.
- Mock every API call in tests. Patch `google.auth.default` and never let a test reach real ADC on
  the dev machine.
- Keep default-profile behavior byte-identical for existing users: same files, same env-var
  precedence, no migration step.
- Regenerate `skills/ga-cli/references/commands.md` in the same commit as any command or flag
  change. The drift test enforces this.
- Validate profile names before building any path from them.
- Write per-profile credential files with `0o600`, like the root ones.
- Keep `.claude-plugin/plugin.json` `version` in lockstep with `pyproject.toml`.

**Ask first:**

- Version bump, tag, release, or PyPI publish. This also gates the README uvx line (see A1
  sequencing).
- A live `audience-exports create` against a real property (consumes quota tokens).
- Adding any runtime dependency (none expected).
- Changing CI workflows (none expected; the drift check rides on pytest).
- Changing existing flags, short flags, or JSON output shapes.
- Deleting or moving anything under `~/.claude/skills-dev/` (copy into the repo; leave the source).
- Changing `ga agent guide` content. It overlaps the skill, but reconciling them is out of scope
  (Q4).

**Never:**

- Let a named profile fall back to another identity (env vars, default profile, or ADC). Wrong
  client data that looks right is worse than an error.
- Persist an "active profile" to disk.
- Put secrets, eval fixtures, or live property data under `skills/`. `npx skills add` copies that
  folder to every user.
- Copy or move a user's SA key file into the config dir. Profiles store the path, as today.
- Run `scripts/check_api_changes.py --update` as part of this work.

---

## Success Criteria

**A — Distribution**

1. After release, `uvx google-analytics-cli --version` prints `ga-cli 0.5.0` on a machine with no
   prior install. Before release, the same works against the locally built wheel.
2. `npx skills add daidalytics/google-analytics-cli --list` finds exactly one skill, `ga-cli`.
3. `/plugin marketplace add daidalytics/google-analytics-cli` followed by
   `/plugin install google-analytics-cli@daidalytics` installs, and the skill appears as
   `google-analytics-cli:ga-cli`. `claude plugin validate .` passes.
4. `tests/test_skill.py` fails if: a command is added without regenerating the reference, the skill
   names a non-existent command, or `plugin.json` and `pyproject.toml` versions diverge.
5. The README shows the uvx one-liner and both skill-install paths above the fold.

**B — Profiles and ADC**

6. `ga --profile client-a config set default_property_id X` followed by
   `ga --profile client-a reports run -m sessions` targets property X under client-a's credentials.
   The same report with no `--profile` still uses the default profile's property and identity.
7. With `GOOGLE_APPLICATION_CREDENTIALS` exported, `ga --profile client-a …` uses client-a's
   credentials, not the env var's.
8. `ga --profile typo reports run …` exits 2 with the known-profiles message and makes no API call.
9. On a machine with only gcloud ADC configured, `ga reports run` succeeds and `ga auth status`
   reports `adc`. With OAuth also configured, OAuth still wins.
10. Every pre-existing test passes unmodified, except `conftest.py` and assertions that newly
    include `profile` in `auth status` JSON.

**C — Audience exports**

11. `create --dry-run` prints the exact request body and makes no API call. `create` returns the
    operation and the export name. `--wait` exits 0 on ACTIVE and 3 on FAILED or timeout.
12. `query` renders one table column per exported dimension. `-o json` is the raw API response.
13. `ga --describe` lists all four commands, with `create` marked `mutative`.

**All**

14. `uv run pytest` and `uv run ruff check src/ tests/ scripts/` are green.
15. SKILL.md covers invocation (A2), profiles (never switch a profile the user didn't name), and
    audience exports (no `--wait` in agent sessions).

---

## Implementation Order

1. **A1** script alias. *Verify:* `uv build`; run `google-analytics-cli --version` from the built
   wheel via uvx.
2. **A3 prep:** extract `build_cli_schema()`. *Verify:* `test_describe.py` unchanged and green.
3. **A2 + A3:** move the skill in, add markers, port the generator, add `test_skill.py` drift and
   command-existence checks. *Verify:* pytest. The first run will likely flag stale commands in the
   draft; fix the skill text, not the test.
4. **A4 + A5:** manifests, version-sync test, README, CLAUDE.md release step. *Verify:*
   `claude plugin validate .` and `npx skills add ./ --list`.
   — **CHECKPOINT A** (human review; option to cut 0.4.1 here so the uvx line is live sooner)
5. **B1–B2:** active profile in `constants.py`, `--profile` root option, conftest reset.
   *Verify:* `TestProfileSelection` and `TestProfilePaths`; full suite green, which proves zero
   migration.
6. **B4:** resolution table + ADC + non-SA `GOOGLE_APPLICATION_CREDENTIALS`. *Verify:*
   `TestCredentialResolution`.
7. **B5:** `ga profiles list/delete`, `auth status` / `config path` changes, regenerate the
   reference, add the SKILL.md profiles section. *Verify:* tests, then live checks.
   — **CHECKPOINT B**
8. **C:** `audience_exports.py` (list/get → query → create → `--wait`), regenerate the reference,
   add the SKILL.md section. *Verify:* `test_audience_exports.py`, live list/get/query.
   — **CHECKPOINT C**, then ask about the 0.5.0 release.

Within A, steps 1 and 2 are independent. B5 and C are independent once B4 lands. Everything else
is sequential.

---

## Open Questions

1. ~~**`--profile` placement.**~~ **Resolved (2026-10-14): root-only.** The form is
   `ga --profile X reports run`, consistent with `-q` / `--no-color`, plus `GA_CLI_PROFILE`.
   SKILL.md teaches the placement. Revisit argv hoisting only if evals show agents misplacing the
   flag.
2. ~~**Update notice under uvx.**~~ **Resolved (2026-10-14): suppress it.** In a uvx ephemeral
   environment, "Run 'ga upgrade' to update" is wrong, because uvx keeps its cached version until
   `uvx google-analytics-cli@latest`. When `sys.prefix` is under uv's cache dir, the daily notice
   is skipped. Otherwise it is unchanged. Implemented as plan task O1.
3. **Export name from the create `Operation`.** *Partly resolved.* Google's "Audience export
   basics" guide shows the name in `Operation.response.name`, which is extraction path 1. Its
   sample is likely copied from v1alpha, so a live `create` (ask-first, because it charges quota)
   still needs to confirm it for v1beta. The `metadata` and `list` fallbacks stay in place
   regardless.
4. **`ga agent guide` vs the skill.** These are two hand-maintained agent references (825 lines of
   Python strings vs SKILL.md + references). Out of scope here. Later options are generating one
   from the other, or retiring `agent guide` in favor of the skill.
5. **Marketplace name `daidalytics`.** If an org-level marketplace with that name is ever created,
   it should list this plugin and the in-repo `marketplace.json` should be retired, rather than two
   marketplaces sharing a name on users' machines.

## Implementation Notes (2026-10-14)

**Rebased onto 0.5.0.** The lanes were first cut from a stale local `master` (0.4.0). They were then rebased onto `origin/master` @ `225822f` (v0.5.0), which shipped output escaping, pipe-aware JSON defaults, TSV compact output and order-by fixes. Upstream's spec for that work is at `git show 225822f:SPEC.md`. Two skill warnings became wrong in 0.5.0 (compact output on reports; colon fields in `--order-by`) and were rewritten. `plugin.json` now tracks 0.5.0.

These are deviations and findings recorded during implementation (`tasks/plan.md`, `tasks/todo.md`).
Each one is pinned by a test unless marked otherwise.

**A: Distribution**
- `.claude-plugin/plugin.json` `version` tracks the *current* package version (`0.4.0`) until the
  release commit bumps both. A4's `0.5.0` example was aspirational; `tests/test_plugin_manifest.py`
  enforces equality.
- **SKILL.md frontmatter must be strict YAML.** The draft's unquoted description contained `: `,
  so `npx skills add` reported "No skills found" for the whole repo. The description is now
  quoted, and `test_frontmatter_is_valid_for_strict_yaml_parsers` guards against a repeat.
- **uvx detection is broader than uvx alone.** The update-notice suppression (Q2) matches any env
  under uv's cache dir, so `uv run --with` / `--isolated` envs skip the notice too. That's
  harmless for dev use. `uv tool install`, pipx, and pip venvs are unaffected.

**B: Profiles and ADC**
- An invalid profile name exits **1** (bad input), not Click's 2, which this CLI reserves for auth
  errors. An explicit `--profile ""` is rejected, so an unset `"$CLIENT"` can't silently run as
  default. An empty `GA_CLI_PROFILE=` means default.
- An unknown profile exits 2 with `ProfileNotFoundError` on any command that resolves
  credentials. Two places degrade instead:
  - `ga auth status` reports `"authenticated": false` (exit 0) with the same message;
  - `ga config get/set` treat it as an empty, not-yet-created profile (writes create it).

  Neither can use another identity.
- Known profiles are listed `default` first, not alphabetically as in the B2 example.
- In the default profile, a corrupt or unrefreshable OAuth token does **not** fall back to ADC. It
  keeps today's "Not authenticated" error rather than silently switching Google identity.
- `ga config path` keeps its existing semantics: it prints the active profile's `config.json`
  path, not the directory.
- The ADC scope hint is a separate `"hint"` field in JSON errors. `ADC_LOGIN_COMMAND` requests
  read-only scopes, so admin writes and chat under ADC need extra scopes. The docs say so.
- **#37: the originally specified ADC login is blocked by Google.** Plain
  `gcloud auth application-default login --scopes=…analytics…` uses gcloud's built-in OAuth client,
  which Google now warns about and then blocks ("This app is blocked"). Live testing caught this;
  mocked tests couldn't. The hint, README and skill now recommend `--client-id-file=` with the
  user's own Desktop-app OAuth client (`ADC_LOGIN_COMMAND`), or
  `--impersonate-service-account=` (`ADC_IMPERSONATE_COMMAND`, which needs
  `roles/iam.serviceAccountTokenCreator`).
- `tests/conftest.py` makes `google.auth.default` raise and clears `GA_CLI_SERVICE_ACCOUNT` /
  `GOOGLE_APPLICATION_CREDENTIALS` for every test, so no test can reach a developer's real ADC
  or exported key.

**C: Audience exports**
- `create` without `--wait` outputs `{exportName, exportId, operation}`. If the `list` fallback
  for the name fails, it warns and still exits 0. The export exists, and a retry would charge
  quota again.
- `query` only looks up the export's state on a 4xx. 401/403 keep exit 2, and 5xx keeps exit 3.
- `--wait` ends on the first failed `get` (no retry). `--timeout` without `--wait` is ignored.
