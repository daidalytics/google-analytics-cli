# Spec: Port the account/property allowlist (PR #33) to 0.6.0

Status: **Draft: for review**
Target version: 0.7.0
Date: 2026-10-15
Owner: @GunnarGriese, who is finalizing the work. @davidher-mann proposed it in #33 and won't
continue on it.

- PR: #33 `feat: account and property allowlist` by @davidher-mann, branch
  `davidher-mann:feat/allowlist` @ `84aed1e`, cut from 0.5.0 (`225822f`). The work moves to a
  branch on `origin`, and a new PR supersedes #33 (decision 2).
- Base it must land on: `origin/master` @ `8877860` (0.6.0 plus the plugin icon)
- The PR's own allowlist spec: `git show 84aed1e:SPEC.md`. **Its design still holds, except where
  this document changes it.** That covers the guard, reference extraction, response filters,
  cache, exit code 5, `ga allowlist show`, and decisions 1–8. This spec only covers what 0.6.0
  changes.
- Previous spec (agent distribution, profiles, audience exports; shipped in 0.6.0):
  `git show 7594078:SPEC.md`

---

## Objective

The goal is to land PR #33's allowlist on 0.6.0 without either side losing a guarantee.

The PR was built on 0.5.0. Since then, master shipped named profiles with per-profile config and
credentials, a gcloud ADC fallback, `ga audience-exports`, the in-repo agent skill with a
drift-checked command reference, and a separate `hint` field on errors. A trial merge
(`git merge pr-33` into `origin/master`) conflicts in 13 files.

The conflicts are mechanical. Three gaps in meaning are not, and **none of them shows up as a
conflict:**

1. **The allowlist would silently become per profile.** `get_config_path()` now resolves to the
   active profile's `config.json`. After a plain merge, `ga --profile other …` or
   `GA_CLI_PROFILE=other` reads a different allowlist, or none at all. That breaks the PR's
   R6 ("no flag can widen the allowlist").
2. **The cache file would land in the shared config root.** `get_allowlist_cache_path()` uses
   `get_config_dir()`, which is now the *global* root. Every profile would share one
   `allowlist-cache.json`. They would overwrite each other's entries because each has a
   different principal, and `ga --profile X auth logout` would delete the cache for every
   profile.
3. **ADC credentials are a new credential type the guard has never seen.** `principal_of()`
   only knows service-account emails and OAuth refresh tokens. A GCE credential reports
   `service_account_email == "default"` until it is refreshed.

There are also surfaces the PR couldn't know about: the new audience-exports endpoints, the
skill (`skills/ga-cli/`), and its generated `references/commands.md`. The generated reference's
drift test fails as soon as `ga allowlist show` exists.

### Requirements

The PR's R1–R7 carry over, with R1 and R6 amended. R8–R11 are new.

| # | Requirement |
|---|---|
| R1′ | Opt-in. With no allowlist configured, behaviour matches **0.6.0** (not 0.5.0), except for the PR's three intended additions and decision 8. |
| R6′ | An agent can't widen its allowlist through the CLI. That includes no flag, **`--profile` and `GA_CLI_PROFILE` included**, no non-interactive config change, and env that can only narrow. |
| R8 | **Global fence + per-profile narrowing** (decided 2026-10-15). The root `config.json` allowlist applies to every profile. A named profile's own allowlist keys only narrow it. |
| R9 | The property→account cache is per profile. |
| R10 | Credentials from gcloud ADC (the default profile's fallback) are guarded the same way, with a well-defined cache principal. |
| R11 | The agent-facing docs (skill, `ga agent guide`, README) explain the allowlist alongside profiles. On exit 5, agents stop and ask: no switching profile, no dropping env vars, no `auth login`. |

---

## Design changes

### D1. Allowlist sources across profiles (R6′, R8)

The PR has two sources, `config` and `env`, and a request must pass every configured source.
This spec keeps that rule and adds a third source:

| Source | Where | Applies to | Role |
|---|---|---|---|
| `config` | `<root>/config.json` (`allowed_account_ids`, `allowed_property_ids`) | **every** profile | the fence |
| `profile <name>` | `<root>/profiles/<name>/config.json`, same keys | only that named profile | narrows |
| `env` | `GA_CLI_ALLOWED_ACCOUNTS`, `GA_CLI_ALLOWED_PROPERTIES` | every profile | narrows, per session |

- **The default profile has only one file source.** Its `config.json` *is* the root file, so
  `config` and `profile` would be the same file. `load_allowlist()` must not count it twice.
- **What the global fence does:** `ga config set allowed_account_ids …` without `--profile` sets
  the fence for every profile. The confirmation must say so, e.g. `allowed_account_ids (all
  profiles): (not set) → 111, 222`. In a named profile it reads
  `allowed_account_ids (profile client-a, narrows the global allowlist): …`.
- **Reading the root file from a named profile.** `store.py` gains
  `load_config_at(path)`, or an equivalent `load_root_config()`, built on the existing
  path-keyed cache. The PR's `_config_error` global becomes per path as well, alongside
  `_cached_config_path`. Master already keys the config cache by path, so a single global error
  flag would leak between profiles.
- **Decision 8 covers both files.** If the root `config.json` is unreadable, every profile fails
  closed (exit 5), because it may hold the fence. If a named profile's `config.json` is
  unreadable, only that profile fails closed. `ga config` refuses to overwrite whichever file is
  unreadable.
- **Atomic save in the profile directory.** The PR's `save_config` runs
  `get_config_dir().mkdir()` and `mkstemp(dir=path.parent)`. On master it must create
  `config_path.parent`, the profile directory, as master's `save_config` already does. Otherwise
  the first `config set` in a new named profile fails.
- **Unknown named profile.** `resolve_credentials()` raises `ProfileNotFoundError` (exit 2)
  before `_build()` reaches `AllowlistHttp`, so a typo in `--profile` stays exit 2. That holds
  even with a broken allowlist. `ga --profile typo allowlist show` exits 2 the same way, like
  `config get` does on master.
- **Unchanged commands.** `config reset`, `unset` and `setup` follow the PR's rules, applied to
  the active profile's file: changing allowlist keys needs a TTY, and `setup` keeps them.
  `ga profiles delete` needs no TTY. A profile source only narrows, so deleting it can never
  get past the global fence or env.
- **Source labels** appear in `describe()`, in error messages and in `ga allowlist show`:
  `config`, `profile client-a`, `env`.

`ga allowlist show -o json` gains `profile` and a third key under `sources`:

```json
{ "enabled": true, "profile": "client-a",
  "sources": { "config": {"accounts": ["111", "222"], "properties": null},
               "profile": {"accounts": ["111"], "properties": null},
               "env": null },
  "effective": { "accounts": ["111"], "properties": [ … ] },
  "cache": { "fetched_at": "…", "age_seconds": 412 } }
```

The README and skill must state the consequence: **a profile's own allowlist protects against
mistakes, not against an agent that switches profile.** The fence, or env set by the launcher,
is what pins an agent.

### D2. Cache per profile (R9)

- `get_allowlist_cache_path()` → `get_profile_dir() / "allowlist-cache.json"`. It moves under the
  "Per-profile paths" block in `config/constants.py`, and the module docstring lists it as per
  profile.
- `ga auth login` and `ga auth logout` clear only the active profile's cache, which is what
  `delete_cache_file()` already does once the path is per profile. `ga profiles delete` removes
  the cache along with the directory.
- The in-process `_caches` map is keyed by `(cache path, principal)`, not principal alone.
  `main._select_profile()` already calls `clear_client_cache()` when the profile changes;
  `reset_caches()` must run there too. Several invocations share a process under `CliRunner`,
  which is how the tests run them.

### D3. ADC credentials (R10)

`principal_of()` rules. The cache is persisted only when a principal is known:

| Credential `resolve_credentials()` returns | Principal |
|---|---|
| Service-account key (env, `GOOGLE_APPLICATION_CREDENTIALS`, saved) | `service_account_email` |
| Stored OAuth token | `oauth:` + SHA-256(refresh token)[:16] |
| ADC `authorized_user` (gcloud user login, `--client-id-file`) | same OAuth rule (it has a `refresh_token`) |
| ADC impersonated (`--impersonate-service-account`) | target SA email (`service_account_email`) |
| ADC `external_account` with SA impersonation | that SA email |
| ADC `external_account` without impersonation | `None` |
| ADC Compute Engine before its first refresh (`"default"`) | `None` |

- **The email rule:** an "email" without `@` counts as unknown (`None`), the same check as
  `auth_cmd._adc_details`. With a `None` principal the map lives only in memory, so each
  process that needs a lookup makes one `accountSummaries` call. The guard is still fully
  enforced. This is documented as a known cost.
- **Token refresh isn't guarded.** Refreshing an ADC token (iamcredentials, STS, the metadata
  server) goes through `AuthorizedHttp`'s inner `Request(self.http)`, not through
  `AllowlistHttp.request`, so it is never denied as an "unexpected host". A test pins this.
- **Skipping `with_scopes()` stays harmless.** `build(http=…)` skips it, but ADC credentials
  come from `google.auth.default(scopes=OAUTH_SCOPES)` and are already scoped. The PR's claim
  holds for the third credential type.
- **The ADC scope hint still works.** `_build()` resolves credentials through
  `_get_credentials()` → `resolve_credentials()`, so `_last_auth_method` is set as before.
  `AllowlistError` is never an `HttpError`, so the ADC scope hint and the allowlist hint can't
  both fire.

### D4. Errors: use master's `hint` field

Master added `error_hint()` and a rule: advice goes in a separate `"hint"` field (or on its own
line in text output), and *the message itself is never altered*. The PR instead appends
`ALLOWLIST_HINT` to the exception message. To align with master:

- `AllowlistError(resource, reason)`: the message is the reason only.
- `error_hint()` returns `ALLOWLIST_HINT` for an `AllowlistError`. `handle_error` already
  emits it as `"hint"` in JSON and as a second line in text.
- An allowlist that can't be loaded (an unreadable `config.json` or a malformed entry) raises
  `AllowlistConfigError`, a subclass, and gets `ALLOWLIST_CONFIG_HINT` instead: `ga allowlist
  show` fails the same way then, so the hint can't point at it (user, 2026-10-27).
- `classify_error`: `AllowlistError` is still checked first and returns `(5, "allowlist_error")`.
  The payload keeps `"resource"`.

```json
{"error": true, "exit_code": 5, "category": "allowlist_error", "resource": "properties/999",
 "message": "properties/999 is not on the allowlist (config: accounts 111, 222 | profile client-a: accounts 111)",
 "hint": "Run 'ga allowlist show' for the allowed properties; only the user can change the allowlist."}
```

### D5. Audience exports

These endpoints are covered by the generic guard and need no per-command code. Tests pin each
one, because the endpoints didn't exist when the PR was tested:

| Call | What's checked |
|---|---|
| `create` | `parent=properties/P`, and the body's `audience: properties/P2/audiences/A`. A P2 that isn't allowed is denied, even with an allowed `-p`. |
| `list` (also the fallback `create` uses to find the export name), `get`, `--wait` polling | path `properties/P/audienceExports…` |
| `query` | path `properties/P/audienceExports/E:query`. The body (`offset`/`limit`) holds no refs. |
| `create --dry-run` | sends nothing, so it isn't checked. This is the same deferral as the PR's other dry runs. |

### D6. Docs (R11)

| File | Change |
|---|---|
| `skills/ga-cli/SKILL.md` | New "Allowlist" section, next to "Profiles". On exit 5 / `allowlist_error`, report the `resource` and ask the user. Don't switch `--profile`, unset `GA_CLI_ALLOWED_*`, run `ga auth login`, or try `config set` to get around it. `ga allowlist show -o json` lists what may be used. |
| `skills/ga-cli/references/commands.md` | Regenerate with `uv run python scripts/gen_skill_reference.py --write`. `tests/test_skill.py::TestGeneratedReference` fails until this is done. |
| `commands/agent_cmd.py` | Keep the PR's "Allowlist" and "Errors and exit codes" sections, and add the profile rule from D1. Check the exit-code table against 0.6.0: an invalid profile name exits 1, an unknown profile exits 2. |
| `README.md` | Merge the PR's Allowlist section into master's README. The cache path becomes per profile. Add the global/profile rule, and add `--profile` to the "not a security boundary" list next to `GA_CLI_CONFIG_DIR`. The env table gets both `GA_CLI_ALLOWED_*` vars next to `GA_CLI_PROFILE`. |
| `CLAUDE.md` (gitignored: a local edit, not part of the PR) | Point "SPEC.md B4" at `git show 7594078:SPEC.md` (B4). Add one convention line: allowlist enforced at the HTTP layer (`AllowlistHttp`), exit 5, sources config ∩ profile ∩ env. |
| `SPEC.md`, `tasks/plan.md`, `tasks/todo.md` | Conflict on both sides. Resolve to this spec and to the port plan and checklist (phases 2 and 3). |

---

## Merge inventory

Conflicts from `git merge origin/master` on `pr-33`:

| File | Resolution |
|---|---|
| `src/ga_cli/config/store.py` | Master's path-keyed cache + PR's fields, `ConfigFileError`, atomic save. `_config_error` per path, `load_config_at` (D1), mkdir of the profile dir. |
| `src/ga_cli/api/client.py` | Master's `resolve_credentials()` + docstring, PR's `_build()` and `get_allowlist_cache()`. All 4 getters use `_build()`. |
| `src/ga_cli/commands/auth_cmd.py` | Master's single `_auth_status()`. Add `"allowlist": {"enabled": …}` once there, so every branch gets it: authenticated, not authenticated, unknown profile. `delete_cache_file()` after SA login, OAuth login and logout. |
| `src/ga_cli/commands/config_cmd.py` | Both: master's `_require_existing_profile()` + PR's TTY, confirm and readable-config checks. Confirmation text names the scope (D1). |
| `src/ga_cli/main.py` | Register both `profiles` and `allowlist`. `_select_profile` also calls `reset_caches()` (D2). |
| `src/ga_cli/utils/errors.py` | Master's hint machinery + PR's `AllowlistError` / exit 5, moved to `hint` (D4). |
| `README.md`, `SPEC.md`, `tasks/plan.md`, `tasks/todo.md` | D6 |
| `tests/test_api_client.py` | Master's build assertions (`test_builds_admin_client`, `test_builds_data_client`, ~L252–319) change from `credentials=` to `http=` with an `AllowlistHttp`. All of master's `resolve_credentials` tests are kept. |
| `tests/test_auth_cmd.py`, `tests/test_config_cmd.py` | Keep both sides. PR status tests are rewritten for the single `_auth_status()` shape (includes `profile`). |

These merge cleanly but still need edits:

- `config/constants.py`: per-profile cache path (D2).
- `config/allowlist.py`: the profile source (D1).
- `api/allowlist_guard.py`: `principal_of` (D3) and the `_caches` key (D2).
- `tests/conftest.py`: the PR's `store._config_error = None` becomes a reset of the per-path
  error state. Also add `reset_caches()`, so tests don't share in-process cache state.
- `pyproject.toml` / `uv.lock`: keep the PR's two declared deps on top of master's version.

---

## Commands

```bash
# Work branch on top of the PR head (pr-33 is fetched locally already).
# Stash or move the uncommitted SPEC.md first: pr-33 has its own SPEC.md, so the switch refuses.
git fetch origin && git fetch origin pull/33/head:pr-33
git switch -c feat/allowlist pr-33      # David's 5 commits keep his authorship
git merge origin/master                 # resolve per the merge inventory, then follow-up commits

uv run pytest                                         # full suite
uv run pytest tests/test_allowlist.py tests/test_allowlist_guard.py tests/test_allowlist_cmd.py \
  tests/test_profiles.py tests/test_api_client.py tests/test_auth_cmd.py tests/test_config_cmd.py -q
uv run ruff check src/ tests/ scripts/
uv run python scripts/gen_skill_reference.py --check

# Ask first: publishes the branch and opens the superseding PR
git push -u origin feat/allowlist
gh pr create --base master --title "feat: account and property allowlist" \
  --body "Supersedes #33 by @davidher-mann (his commits are kept), finalized on 0.6.0. …"
gh pr close 33 --comment "Continued in #<new>, with your commits kept. Thanks, David!"
```

## Project structure (beyond the PR's file list)

```
src/ga_cli/config/allowlist.py      → profile source; load_allowlist reads root + profile + env
src/ga_cli/config/store.py          → per-path config error, load_config_at, profile-dir mkdir
src/ga_cli/config/constants.py      → allowlist cache path moves to per-profile
src/ga_cli/api/allowlist_guard.py   → principal_of (ADC), _caches keyed by (path, principal)
src/ga_cli/utils/errors.py          → AllowlistError hint via error_hint()
src/ga_cli/main.py                  → reset_caches() on profile switch
skills/ga-cli/SKILL.md, skills/ga-cli/references/commands.md
tests/test_allowlist_cache_profiles.py, test_allowlist_adc.py,
  test_allowlist_audience_exports.py, test_allowlist_integration.py   → new (D2, D3, D5, cross-slice)
```

Task breakdown, file ownership and the parallel schedule are in [tasks/plan.md](tasks/plan.md).

## Code style

Same as the PR's and master's specs: short docstrings, comments only for a non-obvious *why*,
class-grouped pytest tests, no new dependencies. The source list is the only structural change:

```python
def load_allowlist() -> Allowlist:
    """Build the effective allowlist: root config ∩ named profile's config ∩ env."""
    root = get_config_dir() / "config.json"
    files = [("config", root)]
    if is_named_profile():
        files.append((f"profile {get_active_profile()}", get_config_path()))
    sources = [_file_source(name, path) for name, path in files]
    sources.append(_source("env", os.environ.get(ENV_ACCOUNTS), os.environ.get(ENV_PROPERTIES),
                           (ENV_ACCOUNTS, ENV_PROPERTIES)))
    return Allowlist(tuple(s for s in sources if s is not None))
```

## Testing strategy

The approach is TDD for each design change. The PR's guard tests stay as they are, run against
real discovery-built clients over a mocked HTTP layer. New cases:

- **D1 profiles:**
  - With a global fence, `ga --profile X` and `GA_CLI_PROFILE=X` can't reach outside it (exit 5,
    nothing sent).
  - A named profile's keys narrow the fence.
  - The default profile has one file source, not two.
  - A corrupt root `config.json` blocks a named profile (exit 5).
  - A corrupt named-profile `config.json` blocks only that profile.
  - An unknown profile is exit 2 before the guard.
  - `config set` in a new named profile creates the directory and saves atomically.
  - Confirmation text names the scope.
- **D2 cache:**
  - The path is under the profile directory.
  - `ga --profile X auth logout` leaves the root cache file.
  - A profile switch inside one process doesn't reuse another profile's in-memory cache.
- **D3 ADC:**
  - The principal table, one test per row.
  - An impersonated credential's refresh isn't denied.
  - `"default"` / `None` principal → no cache file written, and the guard is still enforced.
  - ADC credentials go through `_build()` as `AllowlistHttp`.
- **D4:** JSON error has `category`, `resource` and `hint`. In text mode the hint is on its own
  line, and the message has no hint appended.
- **D5:** every row of the audience-exports table, with `request_sequence == []` on deny.
- **R1′:** master's full suite passes. The only test edits are the build-call assertions and the
  `auth status` / `config get` additions.
- **Docs:** `test_skill.py` drift check passes after regeneration.
- **Live:** read-only only, and **ask first** which property. The PR author's test property
  (353535768 / 487271032) isn't ours. The stored login gets 403 on 250400352, and the other
  properties belong to real clients.

## Boundaries

- **Always:**
  - Fail closed.
  - Never send a request before the check.
  - Run the suite, ruff (`src/ tests/ scripts/`) and `gen_skill_reference.py --check` before
    each commit.
  - Keep David's five commits intact, with his authorship: merge `origin/master` into the
    branch, don't rebase or squash it.
  - Each follow-up commit passes on its own.
- **Ask first:**
  - Pushing the branch to `origin`.
  - Opening the new PR, and closing #33 or commenting on it.
  - Any live API call, and which property.
  - Guard semantics beyond D1–D4.
  - Changing 0.6.0 output beyond R1′.
  - Version bump or release.
- **Never:**
  - Push to David's fork.
  - Force-push `feat/allowlist` once it is on `origin`.
  - Let `--profile`, `GA_CLI_PROFILE` or env widen the fence.
  - Call the allowlist a security boundary.
  - Push to `master` directly.

## Success criteria

1. `feat/allowlist` contains `origin/master` with no conflict markers, and CI passes on Python
   3.10, 3.12 and 3.13 with ruff clean.
2. With no allowlist, 0.6.0 behaviour is unchanged apart from R1′. Master's suite passes with
   only the listed assertion edits.
3. With a root allowlist, a request outside it under any profile (flag or env) exits 5, and
   nothing is sent.
4. A named profile's allowlist narrows the fence for that profile only.
5. Each profile has its own `allowlist-cache.json`. Logging out of one leaves the others intact.
6. ADC-authenticated requests are guarded. The principal follows D3, and an ADC token refresh
   isn't blocked.
7. Denied audience-export calls are never sent.
8. Exit-5 JSON carries `category`, `resource` and `hint`.
9. The skill drift check passes, and SKILL.md, `ga agent guide` and the README document the
   allowlist with profiles.
10. A new PR from `origin/feat/allowlist` credits #33 and @davidher-mann, and its description
    reflects 0.6.0: the R1′ baseline, the sources table and the per-profile cache. #33 is closed
    with a link to it.

## Decisions

1. **Global fence + per-profile narrowing** (user, 2026-10-15). `--profile` can't widen it,
   which keeps R6. A per-profile-only allowlist would let a profile switch escape it.
2. **A branch on `origin` and a new PR** (user, 2026-10-16). This replaces the 2026-10-15
   choice to update #33 in place, which was made before we knew David won't continue.
   `feat/allowlist` starts from the PR head and merges master into it, following the repo's
   "Merge master into feat/…" pattern. That keeps David's commits and authorship. The work
   then doesn't depend on a fork nobody maintains.
3. **The cache is per profile**, because credentials are per profile.
4. **An unknown principal means no disk cache**, never a shared placeholder key.
5. **The allowlist advice goes in `hint`**, following master's rule that the message is never
   altered.
6. **`profiles delete` needs no TTY.** A profile source only narrows.

## Open questions

1. Should `ga profiles list` show whether each profile has its own allowlist? Deferred, because
   it changes 0.6.0 output.
2. Should a named profile's `config set allowed_*` warn about IDs outside the global fence?
   Deferred, because the check can need account lookups, i.e. network calls, during a config
   change.
