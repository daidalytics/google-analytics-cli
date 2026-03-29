# Publishing Plan: google-analytics-cli on PyPI

## Overview

Publish the GA CLI as `google-analytics-cli` on PyPI with embedded OAuth credentials, Google app verification, and automated releases via GitHub Actions using trusted publishing (OIDC).

**Current state:**

- Package name in pyproject.toml: `ga-cli`
- OAuth consent screen: Testing mode (only manually added test users can authenticate)
- Google app verification: Not started
- PyPI account: Does not exist
- `client_secret.json` in repo root (gitignored, but exists locally)

---

## Phase 1: Google Cloud Console — OAuth Consent Screen

**Goal:** Move OAuth consent screen from Testing → Production so any Google user can authenticate.

### 1.1 Review OAuth Consent Screen Configuration

1. Go to [Google Cloud Console → APIs & Services → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Select project `daidalytics-ga-cli`
3. Verify the following fields are filled in (required for verification):
   - **App name**: `Google Analytics CLI` (or similar — this is what users see in the consent prompt)
   - **User support email**: Your email
   - **App logo**: Optional but recommended (builds trust on the consent screen)
   - **Application home page**: Your GitHub repo URL (e.g., `https://github.com/gunnargriese/ga-cli`)
   - **Application privacy policy link**: Required for verification — see step 1.2
   - **Application terms of service link**: Optional but recommended
   - **Authorized domains**: `github.com` (if using GitHub pages for privacy policy)
   - **Developer contact email**: Your email

### 1.2 Create a Privacy Policy

Google requires a privacy policy URL for app verification. It doesn't need to be complex. Options:

- **Simplest:** Add a `PRIVACY.md` to your GitHub repo and link to it via the raw GitHub URL or GitHub Pages
- The policy should cover:
  - What data the app accesses (Google Analytics account data)
  - That tokens are stored locally on the user's machine only (`~/.config/` or `~/Library/Application Support/`)
  - That no data is sent to any third-party server
  - That the app is open source (link to repo)
  - Contact information

### 1.3 Review Scopes

The app currently requests these scopes:

| Scope | Sensitivity | Notes |
|---|---|---|
| `openid` | Non-sensitive | Standard |
| `userinfo.email` | Non-sensitive | Standard |
| `userinfo.profile` | Non-sensitive | Standard |
| `analytics.readonly` | Sensitive | Requires verification |
| `analytics.edit` | Sensitive | Requires verification |
| `analytics.manage.users` | Sensitive | Requires verification |

None of these are **restricted** scopes (restricted = Gmail, Drive, etc.), so you will NOT need a third-party security assessment. You only need Google's standard verification review.

**Action item:** Consider whether you truly need all three analytics scopes at launch. Reducing to just `analytics.readonly` would still require verification but makes the review simpler and faster. You can always add scopes later. If `analytics.edit` and `analytics.manage.users` are needed for existing commands (properties create/delete, user management), keep them.

### 1.4 Publish to Production

1. On the OAuth consent screen page, click **"PUBLISH APP"**
2. Google will show a warning that verification is required for sensitive scopes
3. Confirm — your app will enter a "Needs verification" state
4. **While unverified:** Any user can still authenticate, but they will see a "This app isn't verified" warning screen with an "Advanced → Go to app (unsafe)" link. This is usable but not ideal for a public tool.

### 1.5 Submit for Google Verification

1. After publishing, click **"PREPARE FOR VERIFICATION"**
2. Google will ask you to:
   - Confirm your authorized domains
   - Provide a YouTube video or screen recording demonstrating the OAuth flow (showing the consent screen, what happens after granting access)
   - Explain why each sensitive scope is needed
3. **For the justification, explain:**
   - `analytics.readonly`: CLI reads account/property/stream data and runs reports
   - `analytics.edit`: CLI creates and manages properties and data streams
   - `analytics.manage.users`: CLI manages user permissions on GA4 properties
4. Submit for review
5. **Timeline:** Google verification typically takes 2–6 weeks for sensitive (non-restricted) scopes. You can proceed with all other phases while waiting — users will just see the "unverified app" warning.

---

## Phase 2: Credential Cleanup

**Goal:** Ensure no real credentials are committed to the repo.

### 2.1 Verify client_secret.json is Not in Git History

The file is already in `.gitignore`. Verify it was never committed:

```bash
cd ga-cli
git log --all --full-history -- client_secret.json
```

- **If no results:** You're fine, the file was never committed.
- **If it was committed:** You have two options:
  - **Option A (recommended if repo is not yet public):** Remove from history with `git filter-branch` or `BFG Repo Cleaner`, then rotate the client secret in Google Cloud Console (APIs & Services → Credentials → edit the OAuth client → reset secret). Update your local `client_secret.json` and GitHub Secrets with the new values.
  - **Option B (if repo is already public):** Rotate the client secret immediately (Google Cloud Console → Credentials → reset secret). The old secret is now useless. No need to rewrite history since the old credentials are invalidated.

### 2.2 Set Up Local Development Auth

For local development without the `client_secret.json` file, create a `.env.example` (committed) for documentation:

```
# Copy to .env and fill in values for local OAuth development
# Get these from Google Cloud Console → APIs & Services → Credentials
GA_CLI_CLIENT_ID=your-client-id.apps.googleusercontent.com
GA_CLI_CLIENT_SECRET=your-client-secret
```

Developers can either:
- Place `client_secret.json` in `~/.config/ga-cli/` (or `~/Library/Application Support/ga-cli/` on macOS)
- Set `GA_CLI_CLIENT_ID` and `GA_CLI_CLIENT_SECRET` env vars

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

### 4.5 Set GitHub Secrets

Go to your GitHub repo → Settings → Secrets and variables → Actions:

- `OAUTH_CLIENT_ID` — your Google OAuth client ID
- `OAUTH_CLIENT_SECRET` — your Google OAuth client secret

No `PYPI_TOKEN` needed — trusted publishing handles authentication via OIDC.

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

      - name: Inject OAuth credentials
        run: |
          sed -i 's/__OAUTH_CLIENT_ID__/${{ secrets.OAUTH_CLIENT_ID }}/g' src/ga_cli/config/constants.py
          sed -i 's/__OAUTH_CLIENT_SECRET__/${{ secrets.OAUTH_CLIENT_SECRET }}/g' src/ga_cli/config/constants.py

      - name: Verify credentials were injected
        run: |
          # Fail the build if placeholders are still present
          if grep -q '__OAUTH_CLIENT_ID__\|__OAUTH_CLIENT_SECRET__' src/ga_cli/config/constants.py; then
            echo "ERROR: OAuth placeholders were not replaced. Check GitHub Secrets."
            exit 1
          fi

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
- Added credential injection verification step (catches misconfigured secrets)
- Publishes to TestPyPI first, then PyPI (sequential — acts as a dry run)
- Uses OIDC trusted publishing instead of `PYPI_TOKEN`
- Build artifacts are shared between jobs (credentials are only in the built wheel, not in source)

---

## Phase 6: Test Release (TestPyPI)

**Goal:** Validate the entire pipeline before publishing to real PyPI.

### 6.1 Local Build Test

```bash
cd ga-cli

# Simulate what CI does
export GA_CLI_CLIENT_ID="your-client-id"
export GA_CLI_CLIENT_SECRET="your-client-secret"
sed 's/__OAUTH_CLIENT_ID__/'"$GA_CLI_CLIENT_ID"'/g; s/__OAUTH_CLIENT_SECRET__/'"$GA_CLI_CLIENT_SECRET"'/g' \
  src/ga_cli/config/constants.py > /tmp/constants_check.py
grep -c "OAUTH_CLIENT" /tmp/constants_check.py  # Should show lines with real values, not placeholders

# Build
uv build

# Test install in isolated env
uv venv /tmp/ga-test && source /tmp/ga-test/bin/activate
pip install dist/google_analytics_cli-0.1.0-py3-none-any.whl
ga --help
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

- [ ] PyPI pending publisher is configured (Phase 4.3)
- [ ] GitHub environments `pypi` and `testpypi` exist (Phase 4.4)
- [ ] GitHub Secrets `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` are set (Phase 4.5)
- [ ] Package name in pyproject.toml is `google-analytics-cli` (Phase 3.2)
- [ ] Version in pyproject.toml is `0.1.0`
- [ ] README has correct install instructions (Phase 3.3)
- [ ] Privacy policy exists and is linked in OAuth consent screen (Phase 1.2)
- [ ] OAuth consent screen is published to Production (Phase 1.4)
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
| Google Cloud Console | console.cloud.google.com | Publish consent screen, submit for verification |
| PyPI | pypi.org | Create account, enable 2FA, add pending publisher |
| TestPyPI | test.pypi.org | Create account, enable 2FA, add pending publisher |
| GitHub (repo settings) | github.com/gunnargriese/ga-cli/settings | Create environments, add secrets |

## Estimated Timeline

| Phase | Time | Blocking? |
|---|---|---|
| Phase 1 (Google Console) | 1 hour setup + 2–6 weeks verification | No — app works while unverified (shows warning) |
| Phase 2 (Credential cleanup) | 15 minutes | No |
| Phase 3 (Package rename) | 15 minutes | Yes — must be done before first publish |
| Phase 4 (PyPI setup) | 30 minutes | Yes — must be done before first publish |
| Phase 5 (Workflow update) | 15 minutes | Yes — must be done before first publish |
| Phase 6 (Test release) | 30 minutes | Yes — do before production release |
| Phase 7 (Production release) | 15 minutes | — |
| Phase 8 (Post-launch) | 30 minutes | No |

**You can publish to PyPI immediately** (Phases 2–7) without waiting for Google verification. Users will see the "unverified app" warning during OAuth but can still click through. Once Google approves, the warning disappears automatically.
