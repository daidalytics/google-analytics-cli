# Implementation Plan: GA CLI Feature Parity

Gap analysis against the GTM CLI reference implementation. Each workstream is independent and can be executed in parallel unless noted otherwise.

**Testing convention:** All tests use `typer.testing.CliRunner`, `unittest.mock.patch`, class-based grouping (`class TestXxx:`), and the `isolated_config_dir` autouse fixture from `conftest.py`. Every workstream that touches Python code **must** have a corresponding test file with full coverage before it is considered complete.

---

## WS-1: Self-Update / Upgrade Command

**Goal:** Add `ga upgrade` with `--check` and `--force` flags, plus a daily background update notification.

### Files to create
- `src/ga_cli/commands/upgrade_cmd.py`
- `tests/test_upgrade_cmd.py`

### Files to modify
- `src/ga_cli/main.py` — register `upgrade_app`
- `src/ga_cli/config/constants.py` — add `get_update_check_path()` helper
- `pyproject.toml` — add `packaging` dependency (for version comparison)

### Implementation details

#### 1. Version check logic (`upgrade_cmd.py`)
```
def _check_pypi_version() -> str | None:
```
- `GET https://pypi.org/pypi/ga-cli/json` using `urllib.request` (no new dependency)
- Parse `info.version` from JSON response
- Compare against `ga_cli.__version__` using `packaging.version.parse()`
- Return the latest version string, or `None` on error (network timeout 5s)

#### 2. `ga upgrade --check`
- Call `_check_pypi_version()`
- If newer version exists: print `"Update available: {current} → {latest}. Run 'ga upgrade' to install."`
- If up-to-date: print `"ga-cli {current} is the latest version."`

#### 3. `ga upgrade` (default)
- Call `_check_pypi_version()`, abort if already latest
- Detect package manager: check if running inside a `pipx` venv, or fall back to pip
- Run `subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "ga-cli"])` (or `pipx upgrade ga-cli`)
- Print success/failure message

#### 4. `ga upgrade --force`
- Same as default but pass `--force-reinstall` to pip

#### 5. Daily update notification
- Store last-check timestamp in `~/.config/ga-cli/update-check.json` (`get_update_check_path()`)
- In `main.py`'s `main()` callback, after command dispatch, call a non-blocking check:
  - Read timestamp file; skip if checked within last 24 hours
  - Run the PyPI check; if newer version, print a dim stderr notice: `"A new version of ga-cli is available (v{latest}). Run 'ga upgrade' to update."`
  - Write new timestamp
- Must not slow down normal commands — wrap in try/except, timeout after 2s

### Tests (`tests/test_upgrade_cmd.py`)

All tests use `CliRunner` and mock external calls. Follow class-based grouping.

#### Class: `TestCheckPypiVersion`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_returns_latest_version` | `urllib.request.urlopen` → JSON with `info.version = "1.0.0"` | Returns `"1.0.0"` |
| `test_returns_none_on_network_error` | `urlopen` raises `URLError` | Returns `None` |
| `test_returns_none_on_timeout` | `urlopen` raises `socket.timeout` | Returns `None` |
| `test_returns_none_on_invalid_json` | `urlopen` returns invalid JSON body | Returns `None` |

#### Class: `TestUpgradeCheck`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_check_up_to_date` | `_check_pypi_version` → same as `__version__` | Exit 0, stdout contains "latest version" |
| `test_check_update_available` | `_check_pypi_version` → higher version string | Exit 0, stdout contains "Update available" with both versions |
| `test_check_network_failure` | `_check_pypi_version` → `None` | Exit 1, stderr contains error about checking for updates |

#### Class: `TestUpgradeRun`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_upgrade_runs_pip` | `_check_pypi_version` → higher version, `subprocess.run` → success | `subprocess.run` called with `["pip", "install", "--upgrade", "ga-cli"]` args |
| `test_upgrade_skips_when_latest` | `_check_pypi_version` → same as `__version__` | Exit 0, "already up to date" in stdout, `subprocess.run` NOT called |
| `test_upgrade_force_flag` | `subprocess.run` → success | `subprocess.run` called with `--force-reinstall` in args |
| `test_upgrade_pip_failure` | `subprocess.run` returns returncode=1 | Exit 1, error message shown |
| `test_upgrade_detects_pipx` | Mock `shutil.which("pipx")` → truthy, `subprocess.run` → success | `subprocess.run` called with `["pipx", "upgrade", "ga-cli"]` |

#### Class: `TestDailyUpdateCheck`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_skips_when_checked_recently` | Write timestamp file with `time.time()` (< 24h ago), mock `urlopen` | `urlopen` NOT called |
| `test_runs_when_stale` | Write timestamp file > 24h ago, `_check_pypi_version` → higher version | Stderr contains update notice |
| `test_runs_when_no_timestamp_file` | No timestamp file exists, `_check_pypi_version` → same version | Timestamp file created on disk, no update notice |
| `test_does_not_block_on_error` | `urlopen` raises exception | Command still completes with exit 0, no traceback |
| `test_writes_timestamp_after_check` | `_check_pypi_version` → any value | Timestamp file exists and contains recent timestamp |

---

## WS-2: Shell Completions Command

**Goal:** Expose Typer's built-in shell completion generation via `ga completions`.

### Files to create
- `src/ga_cli/commands/completions_cmd.py`
- `tests/test_completions_cmd.py`

### Files to modify
- `src/ga_cli/main.py` — register `completions_app`

### Implementation details

Typer has `--install-completion` and `--show-completion` built in, but they don't match the GTM CLI's `completions bash|zsh|fish` pattern. Create a thin wrapper:

#### `completions_cmd.py`
```python
completions_app = typer.Typer(name="completions", help="Generate shell completions")

@completions_app.command("bash")
def bash_cmd():
    """Generate bash completion script."""
    # Use typer/click's shell_complete to generate bash script
    # Output to stdout so users can redirect: ga completions bash > ~/.bash_completion.d/ga

@completions_app.command("zsh")
def zsh_cmd():
    ...

@completions_app.command("fish")
def fish_cmd():
    ...
```

Under the hood, use `click.shell_completion.get_completion_class(shell)` and call `source()` to get the completion script, or shell out to `_GA_COMPLETE={shell}_source ga` via environment variable.

### Tests (`tests/test_completions_cmd.py`)

#### Class: `TestCompletionsBash`
| Test | Assert |
|------|--------|
| `test_bash_outputs_completion_script` | Exit 0, stdout contains `_ga_completion` or `_GA_COMPLETE` (bash-specific marker) |
| `test_bash_output_is_valid_shell` | Stdout does not contain Python tracebacks or error strings |

#### Class: `TestCompletionsZsh`
| Test | Assert |
|------|--------|
| `test_zsh_outputs_completion_script` | Exit 0, stdout contains `compdef` or `_ga` (zsh-specific marker) |
| `test_zsh_output_is_valid_shell` | Stdout does not contain Python tracebacks or error strings |

#### Class: `TestCompletionsFish`
| Test | Assert |
|------|--------|
| `test_fish_outputs_completion_script` | Exit 0, stdout contains `complete -c ga` or `_GA_COMPLETE` (fish-specific marker) |
| `test_fish_output_is_valid_shell` | Stdout does not contain Python tracebacks or error strings |

#### Class: `TestCompletionsNoArgs`
| Test | Assert |
|------|--------|
| `test_no_args_shows_help` | Exit 0, stdout contains "bash", "zsh", "fish" as available subcommands |

---

## WS-3: Global `--quiet` and `--no-color` Flags

**Goal:** Add `--quiet`/`-q` and `--no-color` global flags available on every command.

### Files to modify
- `src/ga_cli/main.py` — add global options to `main()` callback, store in a module-level state
- `src/ga_cli/utils/output.py` — check quiet state before printing info/warn/success messages; apply no-color to Rich console

### Files to create
- `tests/test_quiet_nocolor.py`

### Implementation details

#### 1. Global state (`main.py`)
Add to the `main()` callback:
```python
@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
):
```
- Store `quiet` and `no_color` in a simple module-level dict or the Typer context (`ctx.obj`)
- Prefer context: `ctx.ensure_object(dict)["quiet"] = quiet`

#### 2. Quiet mode (`output.py`)
- Add `_quiet = False` module-level flag and a `set_quiet(val: bool)` setter (called from `main()`)
- Gate `info()`, `warn()`, and `success()` behind `if not _quiet`
- `error()` should NEVER be suppressed

#### 3. No-color mode (`output.py`)
- If `--no-color` is passed, reinitialize `console` and `err_console` with `no_color=True`
- Rich already respects `NO_COLOR` env var natively, so the flag just needs to force it on

### Tests (`tests/test_quiet_nocolor.py`)

All tests mock `get_admin_client` to return a mock with sample accounts data so we have a real command to exercise the global flags against.

#### Class: `TestQuietFlag`
| Test | Invocation | Assert |
|------|-----------|--------|
| `test_quiet_suppresses_info` | `ga accounts list --quiet` (mock API) | Exit 0, stderr does NOT contain `Info:` messages |
| `test_quiet_suppresses_success` | `ga auth login --quiet` (mock login) | Exit 0, stderr does NOT contain `OK` messages |
| `test_quiet_suppresses_warn` | Trigger a warning path with `--quiet` | Stderr does NOT contain `Warning:` |
| `test_quiet_does_not_suppress_errors` | `ga accounts list --quiet` (mock API raises Exception) | Exit 1, stderr DOES contain `Error:` |
| `test_quiet_does_not_suppress_data_output` | `ga accounts list --quiet -o json` (mock API) | Stdout DOES contain JSON account data |
| `test_quiet_short_flag` | `ga accounts list -q` (mock API) | Same behavior as `--quiet` |

#### Class: `TestNoColorFlag`
| Test | Invocation | Assert |
|------|-----------|--------|
| `test_no_color_removes_ansi_codes` | `ga accounts list --no-color` (mock API) | Stdout does NOT contain ANSI escape sequences (`\x1b[`) |
| `test_no_color_env_var` | Set `NO_COLOR=1`, run `ga accounts list` (mock API) | Stdout does NOT contain ANSI escape sequences |
| `test_color_present_by_default` | `ga accounts list` (mock API, force TTY) | Stdout or stderr contains Rich markup/ANSI codes |

#### Class: `TestQuietAndNoColorCombined`
| Test | Invocation | Assert |
|------|-----------|--------|
| `test_both_flags_together` | `ga accounts list --quiet --no-color` (mock API) | No info on stderr, no ANSI in stdout, data still present |

---

## WS-4: `accounts update` Command

**Goal:** Add `ga accounts update --account-id <id> --name <new-name>` using the Admin API's `updateAccount` method.

### Files to modify
- `src/ga_cli/commands/accounts.py` — add `update_cmd`
- `tests/test_accounts.py` — add `TestAccountsUpdate` class

### Implementation details

#### `update_cmd` in `accounts.py`
```python
@accounts_app.command("update")
def update_cmd(
    account_id: str = typer.Option(..., "--account-id", "-a", help="Account ID (numeric)"),
    name: Optional[str] = typer.Option(None, "--name", help="New display name"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Output format"),
):
```
- Call `admin.accounts().patch(name=f"accounts/{account_id}", body={"displayName": name}, updateMask="displayName")`
- Output the updated account object
- Require at least one update field (`--name`), error if none given

#### Admin API reference
- Method: `analyticsadmin.accounts.patch`
- `updateMask` parameter: comma-separated field names to update
- Body: `Account` resource with updated fields

### Tests (in `tests/test_accounts.py`)

Add to the existing `_mock_admin_client` helper:
```python
# accounts().patch().execute()
mock_client.accounts.return_value.patch.return_value.execute.return_value = (
    account_patch_result or {}
)
```

#### Class: `TestAccountsUpdate`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_update_name_table_output` | `admin.accounts().patch().execute()` → updated account dict | Exit 0, new name in output, `patch` called with correct `name`, `body`, `updateMask` args |
| `test_update_name_json_output` | Same as above, add `-o json` | Exit 0, `"displayName"` in JSON output |
| `test_update_requires_account_id` | No mocks needed | Exit != 0, error mentions `--account-id` |
| `test_update_no_fields_given` | No mocks needed (or minimal) | Exit != 0 or error message says "at least one update field required" |
| `test_update_api_error` | `patch().execute()` raises `Exception("Permission denied")` | Exit 1, "Permission denied" in output |
| `test_update_respects_config_output_format` | Mock `get_effective_value` → `"json"` | JSON output produced without explicit `-o` flag |

---

## WS-5: Quick Install Script

**Goal:** Add an `install.sh` for `curl -fsSL ... | bash` onboarding.

### Files to create
- `install.sh` (project root)
- `tests/test_install_script.sh` (shell-based smoke tests)

### Implementation details

The script should:
1. Detect OS (macOS / Linux) — warn and exit on unsupported platforms
2. Check for `pipx` first (preferred), fall back to `pip`
   - If neither found, check for `uv` and use `uv tool install`
3. Run `pipx install ga-cli` (or equivalent)
4. Verify installation: `ga --version`
5. Print success message with next steps

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Detect platform
# 2. Find installer (pipx > uv tool > pip)
# 3. Install ga-cli
# 4. Verify and print instructions
```

Keep it under 80 lines.

### Tests (`tests/test_install_script.sh`)

Basic shell-based smoke tests (run via `bash tests/test_install_script.sh`):

| Test | How | Assert |
|------|-----|--------|
| `test_script_is_valid_bash` | `bash -n install.sh` | Exit 0 (syntax valid) |
| `test_script_has_set_euo_pipefail` | `grep "set -euo pipefail" install.sh` | Match found |
| `test_script_detects_platform` | `grep -q "uname" install.sh` | Match found |
| `test_script_checks_pipx` | `grep -q "pipx" install.sh` | Match found |
| `test_script_checks_uv` | `grep -q "uv" install.sh` | Match found |

---

## WS-6: README Enhancements

**Goal:** Update README.md with missing documentation sections.

### Files to modify
- `README.md`

### Sections to add

#### 1. Compact output format
Add to the "Output formats" section:
```markdown
ga accounts list --output compact  # Minimal ID + name output
```

#### 2. CI/CD Integration example
Add a new `## CI/CD Integration` section with a GitHub Actions example:
```yaml
jobs:
  ga-report:
    runs-on: ubuntu-latest
    steps:
      - name: Install GA CLI
        run: pip install ga-cli

      - name: Export daily report
        run: |
          echo '${{ secrets.GA_SERVICE_ACCOUNT_KEY }}' > /tmp/sa-key.json
          ga auth login --service-account /tmp/sa-key.json
          ga reports run -p ${{ vars.GA_PROPERTY_ID }} \
            --metrics sessions,users --dimensions date \
            --start-date 7daysAgo -o json > report.json
          rm /tmp/sa-key.json
```

#### 3. Environment Variables section
Document all supported env vars in a table:
| Variable | Description |
|----------|-------------|
| `GA_CLI_SERVICE_ACCOUNT` | Path to service account key file |
| `GOOGLE_APPLICATION_CREDENTIALS` | Standard GCP credential path (fallback) |
| `GA_CLI_CONFIG_DIR` | Override config directory |
| `GA_CLI_CLIENT_ID` | OAuth client ID (dev override) |
| `GA_CLI_CLIENT_SECRET` | OAuth client secret (dev override) |
| `NO_COLOR` | Disable colored output |

#### 4. Global Options section
```markdown
## Global Options
--help, -h      Show help
--version, -v   Show version
--quiet, -q     Suppress non-essential output (after WS-3)
--no-color      Disable colored output (after WS-3)
```

#### 5. Privacy statement
Add a `## Privacy` section:
> GA CLI stores authentication credentials locally on your machine. No data is sent to any third party — all communication is directly between your machine and Google's APIs.

#### 6. Shell completions section (after WS-2)
```markdown
## Shell Completions
ga completions bash > ~/.bash_completion.d/ga
ga completions zsh > ~/.zsh/completions/_ga
ga completions fish > ~/.config/fish/completions/ga.fish
```

### Tests

No automated tests for README content. **Verification checklist:**
- [ ] All internal links resolve (no broken anchors)
- [ ] Code blocks have correct language tags
- [ ] All commands listed are actually implemented
- [ ] No references to flags/features from WS-1–5 until those are merged

---

## WS-7: Update Agent Guide

**Goal:** Keep `ga agent guide` in sync with new features.

### Files to modify
- `src/ga_cli/commands/agent_cmd.py`

### Files to create
- `tests/test_agent_guide.py`

### Sections to add/update in `AGENT_GUIDE`

1. **Upgrade command** — document `ga upgrade --check`
2. **Global flags** — add `--quiet` and `--no-color` to the quick reference card
3. **accounts update** — add to the Accounts section
4. **Environment variables** — add `GOOGLE_APPLICATION_CREDENTIALS` and `NO_COLOR` references
5. **Shell completions** — mention for agents that set up environments

**Dependency:** Execute after WS-1 through WS-4 are merged.

### Tests (`tests/test_agent_guide.py`)

#### Class: `TestAgentGuide`
| Test | Invocation | Assert |
|------|-----------|--------|
| `test_guide_prints_content` | `ga agent guide` | Exit 0, stdout contains `"# AI Agent Guide"` |
| `test_guide_documents_upgrade` | `ga agent guide` | Stdout contains `"ga upgrade"` |
| `test_guide_documents_quiet_flag` | `ga agent guide` | Stdout contains `"--quiet"` |
| `test_guide_documents_no_color_flag` | `ga agent guide` | Stdout contains `"--no-color"` |
| `test_guide_documents_accounts_update` | `ga agent guide` | Stdout contains `"accounts update"` |
| `test_guide_documents_completions` | `ga agent guide` | Stdout contains `"completions"` |
| `test_guide_documents_env_vars` | `ga agent guide` | Stdout contains `"GOOGLE_APPLICATION_CREDENTIALS"` and `"NO_COLOR"` |

---

## Execution Order & Dependencies

```
WS-1 (upgrade)        ──┐
WS-2 (completions)    ──┤
WS-3 (quiet/no-color) ──┤── all independent, run in parallel
WS-4 (accounts update)──┤
WS-5 (install script) ──┤
WS-6 (README)         ──┘  (can start now; finalize after WS-1–3 merge)
WS-7 (agent guide)    ──── depends on WS-1, WS-2, WS-3, WS-4
```

## Definition of Done (per workstream)

Each workstream is complete when:
1. All listed source files are created/modified
2. All tests in the test matrix pass (`uv run pytest tests/test_<name>.py`)
3. `uv run ruff check src/ tests/` passes with no new warnings
4. `uv run pytest` passes (full suite, no regressions)
5. For WS-6: README verification checklist is satisfied

## Estimated Scope

| Workstream | New files | Modified files | Test files | Test count (approx) |
|------------|-----------|----------------|------------|---------------------|
| WS-1 | 1 | 3 | 1 | 14 |
| WS-2 | 1 | 1 | 1 | 7 |
| WS-3 | 0 | 2 | 1 | 10 |
| WS-4 | 0 | 1 | 1 (existing) | 6 |
| WS-5 | 1 | 0 | 1 (shell) | 5 |
| WS-6 | 0 | 1 | 0 | — |
| WS-7 | 0 | 1 | 1 | 7 |
| **Total** | **3** | **9** | **6** | **~49** |
