# Publishing Plan: google-analytics-cli on PyPI

## Overview

Publish the GA CLI as `google-analytics-cli` on PyPI. Users bring their own GCP OAuth credentials (client ID + secret) — the CLI does **not** ship with embedded credentials.

**Current state:**

- Package name in pyproject.toml: `ga-cli`
- PyPI account: Does not exist
- `client_secret.json` in repo root (gitignored, but exists locally)

**Key design decision:** Users create their own GCP project and OAuth client. This avoids:
- Managing a shared GCP project on behalf of all users
- Becoming a quota bottleneck for API requests
- The need for Google OAuth consent screen verification (each user's own project, their own consent screen)
- Shipping extractable secrets in published wheels

---

## Phase 1: User-Provided OAuth Credentials

**Goal:** Users supply their own GCP OAuth client credentials. The CLI guides them through setup.

### 1.1 How Users Provide Credentials

Three methods (checked in order by the CLI):

1. **`client_secret.json` file** — place the downloaded JSON from GCP Console in `~/.config/ga-cli/client_secret.json`
2. **Environment variables** — set `GA_CLI_CLIENT_ID` and `GA_CLI_CLIENT_SECRET`
3. **Service account** — `ga auth login --service-account /path/key.json` (unchanged)

### 1.2 Update `ga agent guide` Setup Section

Add a dedicated section to the agent guide explaining the credential setup process. This makes it easy for AI agents to guide users through onboarding. The guide should cover:

1. Create a GCP project (or use an existing one)
2. Enable the **Google Analytics Admin API** and **Google Analytics Data API**
3. Go to APIs & Services → Credentials → Create OAuth 2.0 Client ID (Desktop application)
4. Download `client_secret.json`
5. Place in `~/.config/ga-cli/` or set env vars
6. Run `ga auth login`

### 1.3 Improve Error Message for Missing Credentials

When a user runs `ga auth login` without any credentials configured, the error message should include:
- A clear explanation of what's needed
- A pointer to `ga agent guide --section setup` for step-by-step instructions
- Links or instructions for the GCP Console steps

### 1.4 Remove Placeholder Injection from Constants

Remove the `__OAUTH_CLIENT_ID__` / `__OAUTH_CLIENT_SECRET__` placeholders from `constants.py`. Since credentials are always user-provided, there is nothing to inject at build time.

**Code changes:**
- `constants.py`: Remove `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` constants (or keep them as env-var-only with no placeholder fallback)
- `oauth.py`: Update `login()` to check for `client_secret.json` first, then env vars, then show a helpful error
- `release.yml`: Remove the `sed` credential injection step and the verification step

### 1.5 Google OAuth Consent Screen (Per User)

Since each user creates their own GCP project, they control their own OAuth consent screen. Document in the setup guide:
- For personal use: consent screen can stay in **Testing** mode (works for the project owner and up to 100 test users)
- For team use: publish to **Production** within their own GCP project
- No need to submit for Google verification unless they want to remove the "unverified app" warning for their team

---

## Phase 2: Credential Cleanup

**Goal:** Ensure no real credentials are committed to the repo. Since users now provide their own credentials, the repo should contain zero secrets.

### 2.1 Verify client_secret.json is Not in Git History

The file is already in `.gitignore`. Verify it was never committed:

```bash
cd ga-cli
git log --all --full-history -- client_secret.json
```

- **If no results:** You're fine, the file was never committed.
- **If it was committed:** Remove from history with `git filter-branch` or `BFG Repo Cleaner` before making the repo public.

### 2.2 Remove GitHub Secrets for OAuth

Since the release workflow no longer injects OAuth credentials:
- **Remove** `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` from GitHub Actions secrets
- The only secret needed is for PyPI publishing (handled via OIDC trusted publishing — no secret needed there either)

---

## Phase 3: Package Rename

**Goal:** Rename from `ga-cli` to `google-analytics-cli` for PyPI.

### 3.1 Verify Name Availability

```bash
pip index versions google-analytics-cli
```

If it returns "No matching distribution", the name is available. Also check on [pypi.org/project/google-analytics-cli/](https://pypi.org/project/google-analytics-cli/) — a 404 means it's free.

### 3.2 Update pyproject.toml

Change the package name:

```toml
[project]
name = "google-analytics-cli"
```

Update URLs to match your actual GitHub repo:

```toml
[project.urls]
Homepage = "https://github.com/gunnargriese/ga-cli"
Repository = "https://github.com/gunnargriese/ga-cli"
Issues = "https://github.com/gunnargriese/ga-cli/issues"
```

The entry point stays the same — users will still type `ga` to invoke the CLI:

```toml
[project.scripts]
ga = "ga_cli.main:run"
```

**Install command will be:** `pip install google-analytics-cli` (or `pipx install google-analytics-cli`)
**CLI command will be:** `ga`

### 3.3 Update README

Update the install instructions in README.md to reference the new package name:

```bash
pip install google-analytics-cli
# or
pipx install google-analytics-cli
```

---

## Phase 4: PyPI Account & Trusted Publishing

**Goal:** Set up PyPI with OIDC trusted publishing (no API tokens to manage).

### 4.1 Create PyPI Account

1. Go to [pypi.org/account/register/](https://pypi.org/account/register/)
2. Create an account
3. **Enable 2FA** (required for trusted publishing) — go to Account Settings → Two factor authentication

### 4.2 Create a TestPyPI Account (for dry runs)

1. Go to [test.pypi.org/account/register/](https://test.pypi.org/account/register/)
2. Create a separate account (TestPyPI and PyPI are independent)
3. Enable 2FA here too

### 4.3 Configure Trusted Publishing (Pending Publisher)

Since the package doesn't exist on PyPI yet, set up a "pending publisher":

1. Go to [pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
2. Under **"Add a new pending publisher"**, fill in:
   - **PyPI project name**: `google-analytics-cli`
   - **Owner**: `gunnargriese` (your GitHub username)
   - **Repository name**: `ga-cli` (your GitHub repo name)
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi` (we'll create this in GitHub)
3. Click "Add"

Do the same on TestPyPI:
1. Go to [test.pypi.org/manage/account/publishing/](https://test.pypi.org/manage/account/publishing/)
2. Same details but **environment name**: `testpypi`

### 4.4 Create GitHub Environments

1. Go to your GitHub repo → Settings → Environments
2. Create environment **`pypi`**
   - No special protection rules needed for a personal project
3. Create environment **`testpypi`**

### 4.5 GitHub Secrets

No GitHub Secrets required:
- **No `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET`** — users provide their own credentials
- **No `PYPI_TOKEN`** — trusted publishing handles authentication via OIDC

---

## Phase 5: Update Release Workflow

**Goal:** Switch from API token to trusted publishing, add TestPyPI support.

### 5.1 Updated release.yml

Replace `ga-cli/.github/workflows/release.yml` with:

```yaml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Install dependencies
        run: uv sync
      - name: Lint
        run: uv run ruff check src/ tests/
      - name: Run tests
        run: uv run pytest

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Build
        run: uv build

      - name: Upload dist artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish-testpypi:
    needs: build
    runs-on: ubuntu-latest
    environment: testpypi
    permissions:
      id-token: write  # Required for OIDC trusted publishing
    steps:
      - name: Download dist artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Publish to TestPyPI
        run: uv publish --index-url https://test.pypi.org/legacy/
        # No token needed — OIDC trusted publishing handles auth

  publish-pypi:
    needs: publish-testpypi
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # Required for OIDC trusted publishing
    steps:
      - name: Download dist artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Publish to PyPI
        run: uv publish
        # No token needed — OIDC trusted publishing handles auth
```

**Key changes from current workflow:**
- Separated test / build / publish into distinct jobs
- **No credential injection** — users provide their own OAuth credentials at runtime
- Publishes to TestPyPI first, then PyPI (sequential — acts as a dry run)
- Uses OIDC trusted publishing instead of `PYPI_TOKEN`
- Build artifacts are shared between jobs
- No secrets required in GitHub Actions

---

## Phase 6: Test Release (TestPyPI)

**Goal:** Validate the entire pipeline before publishing to real PyPI.

### 6.1 Local Build Test

```bash
cd ga-cli

# Build
uv build

# Test install in isolated env
uv venv /tmp/ga-test && source /tmp/ga-test/bin/activate
pip install dist/google_analytics_cli-0.1.0-py3-none-any.whl
ga --help
ga agent guide --section setup  # Should show credential setup instructions

# Test OAuth with your own credentials
cp /path/to/your/client_secret.json ~/.config/ga-cli/
ga auth login  # Should open browser OAuth flow
deactivate
```

### 6.2 Push a Test Tag

```bash
# Use a pre-release version to test
# Update version in pyproject.toml to "0.1.0rc1" first
git tag v0.1.0rc1
git push origin v0.1.0rc1
```

### 6.3 Verify on TestPyPI

1. Check the GitHub Actions run completes successfully
2. Visit `https://test.pypi.org/project/google-analytics-cli/`
3. Test install:
   ```bash
   pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ google-analytics-cli
   ga auth login
   ```
   (The `--extra-index-url` is needed because dependencies like `typer` aren't on TestPyPI)

---

## Phase 7: First Production Release

**Goal:** Publish v0.1.0 to PyPI.

### 7.1 Final Checklist

- [ ] OAuth placeholder injection removed from constants.py and release.yml (Phase 1.4)
- [ ] `ga agent guide --section setup` includes credential setup instructions (Phase 1.2)
- [ ] Error message for missing credentials points to setup guide (Phase 1.3)
- [ ] PyPI pending publisher is configured (Phase 4.3)
- [ ] GitHub environments `pypi` and `testpypi` exist (Phase 4.4)
- [ ] Package name in pyproject.toml is `google-analytics-cli` (Phase 3.2)
- [ ] Version in pyproject.toml is `0.1.0`
- [ ] README has correct install + credential setup instructions (Phase 3.3)
- [ ] TestPyPI dry run succeeded (Phase 6)

### 7.2 Tag and Release

```bash
git tag v0.1.0
git push origin v0.1.0
```

### 7.3 Verify

1. GitHub Actions workflow completes (all 4 jobs green)
2. Package appears at `https://pypi.org/project/google-analytics-cli/`
3. Install and test:
   ```bash
   pip install google-analytics-cli
   ga --version
   ga auth login  # Opens browser, completes OAuth flow
   ga accounts list
   ```

---

## Phase 8: Post-Launch

### 8.1 Add PyPI Badge to README

```markdown
[![PyPI](https://img.shields.io/pypi/v/google-analytics-cli)](https://pypi.org/project/google-analytics-cli/)
```

### 8.2 Document Install Methods

```bash
# pip
pip install google-analytics-cli

# pipx (recommended for CLI tools — isolated env)
pipx install google-analytics-cli

# uv
uv tool install google-analytics-cli
```

### 8.3 Release Script (Optional)

Create a `scripts/release.sh` similar to the GTM CLI's `deno task release`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BUMP_TYPE="${1:?Usage: ./scripts/release.sh <patch|minor|major|x.y.z>}"

# Get current version
CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
echo "Current version: $CURRENT"

# Calculate new version
if [[ "$BUMP_TYPE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  NEW_VERSION="$BUMP_TYPE"
else
  IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"
  case "$BUMP_TYPE" in
    patch) NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))" ;;
    minor) NEW_VERSION="$MAJOR.$((MINOR + 1)).0" ;;
    major) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
    *) echo "Invalid bump type: $BUMP_TYPE"; exit 1 ;;
  esac
fi

echo "New version: $NEW_VERSION"
read -p "Continue? (y/n) " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || exit 0

# Update version
sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
rm -f pyproject.toml.bak

# Commit, tag, push
git add pyproject.toml
git commit -m "chore: bump version to $NEW_VERSION"
git tag "v$NEW_VERSION"
git push origin main "v$NEW_VERSION"

echo "Released v$NEW_VERSION — GitHub Actions will publish to PyPI"
```

---

## Summary of Accounts & Services Needed

| Service | URL | What to do |
|---|---|---|
| PyPI | pypi.org | Create account, enable 2FA, add pending publisher |
| TestPyPI | test.pypi.org | Create account, enable 2FA, add pending publisher |
| GitHub (repo settings) | github.com/gunnargriese/ga-cli/settings | Create environments (no secrets needed) |

**Note:** No Google Cloud Console setup needed on your end — each user manages their own GCP project.

## Estimated Timeline

| Phase | Time | Blocking? |
|---|---|---|
| Phase 1 (User-provided creds) | 1–2 hours (code changes + agent guide update) | Yes — must be done before first publish |
| Phase 2 (Credential cleanup) | 15 minutes | No |
| Phase 3 (Package rename) | 15 minutes | Yes — must be done before first publish |
| Phase 4 (PyPI setup) | 30 minutes | Yes — must be done before first publish |
| Phase 5 (Workflow update) | 15 minutes | Yes — must be done before first publish |
| Phase 6 (Test release) | 30 minutes | Yes — do before production release |
| Phase 7 (Production release) | 15 minutes | — |
| Phase 8 (Post-launch) | 30 minutes | No |

**You can publish to PyPI immediately** — no Google verification or consent screen setup needed on your end. Users handle their own GCP OAuth setup.

---

## Appendix: File-Level Implementation Plan

Detailed breakdown of every file that needs to change for Phases 1, 3, and 5. Use this as the implementation checklist.

### Files to Change (8 files)

#### 1. `src/ga_cli/config/constants.py` — Remove OAuth constants

- Delete `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` (lines ~26–27) and the associated comment
- These constants currently fall back to `__OAUTH_CLIENT_ID__` / `__OAUTH_CLIENT_SECRET__` placeholders — both are dead code once users provide their own credentials
- The env var reads (`GA_CLI_CLIENT_ID`, `GA_CLI_CLIENT_SECRET`) move into the modules that actually use them (`oauth.py`, `credentials.py`)

#### 2. `src/ga_cli/auth/oauth.py` — New credential resolution + Rich error panel

- Remove `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` imports from `constants`
- Update `_get_client_config()` to read `GA_CLI_CLIENT_ID` / `GA_CLI_CLIENT_SECRET` env vars directly (inline, no constants)
- Replace the current `ValueError` raised when credentials are missing with a Rich `Panel` (from `rich.panel`) containing:
  - **Title:** "OAuth client credentials not found"
  - **Body:** The two credential options (`client_secret.json` file path or env vars), a pointer to `ga agent guide --section setup`, and a link to the GCP Console credentials page
- Use `err_console` from `utils.output` to render the panel, then `raise typer.Exit(1)`

#### 3. `src/ga_cli/auth/credentials.py` — Remove constant imports

- Remove `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` imports
- In `load_credentials()` (line ~78–79), the fallback for `client_id` / `client_secret` should become `None` instead of the old constants
- **Rationale:** `save_credentials()` always writes `client_id` and `client_secret` from the actual OAuth flow's credentials object, so the fallback in `load_credentials()` is a dead path. Using `None` is safer than silently injecting a placeholder that would fail on token refresh anyway

#### 4. `src/ga_cli/commands/agent_cmd.py` — Add `setup` section to agent guide

- Add a `_SECTION_SETUP` constant with step-by-step GCP credential setup instructions:
  1. Create a GCP project (or use existing)
  2. Enable Google Analytics Admin API and Google Analytics Data API
  3. Configure OAuth consent screen (Testing mode is fine for personal use)
  4. Create OAuth 2.0 Client ID (Desktop application type)
  5. Download `client_secret.json` and place in `~/.config/ga-cli/`
  6. Alternative: set `GA_CLI_CLIENT_ID` and `GA_CLI_CLIENT_SECRET` env vars
  7. Run `ga auth login`
- Register `"setup"` in the `_SECTIONS` dict
- In `_SECTION_OVERVIEW`, add a note pointing to `ga agent guide --section setup` for credential prerequisites

#### 5. `.github/workflows/release.yml` — Remove credential injection, add OIDC

- Remove the `sed` lines that inject `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` into `constants.py`
- Split into 4 jobs: `test` → `build` → `publish-testpypi` → `publish-pypi`
- Use OIDC trusted publishing (`permissions: id-token: write`) — zero secrets required
- Build artifacts shared between jobs via `upload-artifact` / `download-artifact`
- Full YAML is in Phase 5.1 above

#### 6. `pyproject.toml` — Package rename

- Change `name = "ga-cli"` to `name = "google-analytics-cli"`
- Entry point (`ga = "ga_cli.main:run"`) stays the same — CLI command remains `ga`
- URLs stay the same (GitHub repo name doesn't change)

#### 7. `README.md` — Update install + credential docs

- Change `pip install ga-cli` to `pip install google-analytics-cli` everywhere
- Add `pipx install google-analytics-cli` and `uv tool install google-analytics-cli` as recommended install methods
- Update the CI/CD example to use the new package name
- Update the Environment Variables table: `GA_CLI_CLIENT_ID` / `GA_CLI_CLIENT_SECRET` are no longer "dev override" — they're a primary credential method (remove the "(dev override)" qualifier)

#### 8. `CLAUDE.md` — Reflect new credential model

- Remove the "OAuth placeholders" bullet from Key Conventions (`__OAUTH_CLIENT_ID__` and `__OAUTH_CLIENT_SECRET__` in constants.py are replaced at build time...)
- Update "Auth priority" to document the new resolution order: `client_secret.json` → env vars → service account
- Update CI/CD section: remove "Required GitHub secrets for release: `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `PYPI_TOKEN`" — no secrets are required (OIDC trusted publishing)

### Files NOT Changing

- **Tests** — `test_credentials.py` uses `"test-client-secret"` as literal test data in a mock fixture, not referencing the constants. No test changes needed.
- **`main.py`** — No changes needed
- **`auth/service_account.py`** — Unaffected (service account flow is independent)

### Risk Areas

| Area | Risk | Mitigation |
|------|------|------------|
| `credentials.py` fallback | When loading saved credentials from disk, the current code falls back to `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` if `client_id` / `client_secret` aren't in the JSON. Changing to `None` means old credential files missing those keys would fail on token refresh. | `save_credentials()` always writes `client_id` and `client_secret` from the flow's credentials object, so the fallback should never trigger. Changing to `None` makes this explicit rather than silently using a placeholder. |
| Existing users | Anyone who installed a build with injected credentials and has a saved `credentials.json` | Not affected — their credentials file already has the real `client_id` / `client_secret` baked in from the original OAuth flow. |
| Package rename | Users with `ga-cli` installed won't auto-upgrade to `google-analytics-cli` | Document in release notes. Both `pip install ga-cli` (old) and `pip install google-analytics-cli` (new) will work if the old name is never claimed on PyPI. |
