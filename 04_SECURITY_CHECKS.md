# Security Checks — Pre-Publish Audit

## Overview

Security review of the GA CLI codebase prior to publishing as an open-source package on PyPI. Findings are organized by severity and grouped into actionable phases.

**Current state:**

- `client_secret.json` with real OAuth credentials exists in repo root (gitignored but present on disk)
- Release workflow injects OAuth secrets into source at build time — secrets are extractable from published wheels
- Measurement Protocol secrets displayed in plaintext in CLI output
- No input validation on user-supplied resource IDs
- No credential file permission checks on load

---

## Findings Summary

| # | Severity | Finding | File(s) | Phase |
|---|----------|---------|---------|-------|
| S1 | Critical | OAuth credentials on disk | `client_secret.json` | 1 |
| S2 | Critical | Client secret extractable from published package | `.github/workflows/release.yml`, `src/ga_cli/config/constants.py` | 1 |
| S3 | High | MP secrets displayed in plaintext | `src/ga_cli/commands/mp_secrets.py` | 2 |
| S4 | Medium | No input validation on numeric IDs | `src/ga_cli/commands/properties.py`, `data_streams.py`, etc. | 2 |
| S5 | Medium | No credential file permission check on load | `src/ga_cli/auth/credentials.py` | 2 |
| S6 | Medium | Update check file uses default permissions | `src/ga_cli/commands/upgrade_cmd.py` | 3 |
| S7 | Low | Silent exception swallowing in update check | `src/ga_cli/commands/upgrade_cmd.py` | 3 |
| S8 | Low | TOCTOU in OAuth flow file check | `src/ga_cli/auth/oauth.py` | 3 |
| S9 | Low | No dependency vulnerability scanning in CI | `.github/workflows/ci.yml` | 3 |

---

## Phase 1: Critical — Before Publishing

### S1: Rotate OAuth Credentials

**Problem:** `client_secret.json` in the repo root contains a live OAuth client ID and secret (`779984266832-...`). Even though it's in `.gitignore`, the credentials should be considered compromised if anyone has ever had access to the working directory.

**Steps:**

1. Go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. Select project `daidalytics-ga-cli`
3. Delete the existing OAuth 2.0 client ID
4. Create a new OAuth 2.0 client ID (Desktop application type)
5. Download the new `client_secret.json` and place it in the repo root
6. Update GitHub Actions secrets `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` to match
7. Delete the old `client_secret.json` from disk

**Verification:** Run `uv run ga auth login` and confirm the OAuth flow works with the new credentials.

---

### S2: Harden OAuth Client Configuration

**Problem:** The release workflow in `.github/workflows/release.yml` (lines 23–25) uses `sed` to inject `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` into `src/ga_cli/config/constants.py` at build time. The resulting wheel ships these values in plaintext — anyone can extract them with `unzip *.whl`.

This is an inherent limitation of desktop OAuth apps (Google's own `gcloud` CLI does the same). The client secret is **not** a user secret — it identifies the application, not the user. However, the blast radius should be minimized.

**Steps:**

1. Ensure the OAuth client is configured as **Desktop** application type (not Web)
2. Verify redirect URI is restricted to `http://localhost` only
3. Confirm OAuth consent screen scopes are the minimum required
4. Consider adding a rate limit or abuse-detection note in the Google Cloud Console
5. Document in the README that the embedded client ID is intentionally public (this is standard for desktop OAuth apps)

**Verification:**

```bash
# After building, inspect the wheel to confirm only expected secrets are present
uv build
unzip -p dist/*.whl ga_cli/config/constants.py | grep -E 'CLIENT_ID|CLIENT_SECRET'
# Should show the placeholders (in dev) or the injected values (in release)
```

---

## Phase 2: High / Medium — Before or Shortly After Publishing

### S3: Mask Measurement Protocol Secrets in Output

**Problem:** `src/ga_cli/commands/mp_secrets.py` (lines 50–55) displays `secretValue` in full in table output. This can leak into terminal scrollback, CI logs, or screenshots.

**Steps:**

1. In table output mode, mask `secretValue` to show only the first 4 characters + `****`
2. Add a `--show-secrets` flag that displays the full value
3. JSON output mode should remain unmasked (machine-readable, typically piped)

**Implementation sketch:**

```python
# In mp_secrets.py, before passing to output()
if effective_format == "table" and not show_secrets:
    for s in secrets:
        val = s.get("secretValue", "")
        s["secretValue"] = val[:4] + "****" if len(val) > 4 else "****"
```

**Verification:** Run `uv run ga mp-secrets list` and confirm secrets are masked. Run with `--show-secrets` and confirm full values appear.

---

### S4: Validate Numeric Resource IDs

**Problem:** User-supplied account, property, and data stream IDs are interpolated directly into API resource paths (e.g., `f"parent:accounts/{effective_account}"`) without validation. While the Google API will reject invalid values, the error messages are confusing.

**Steps:**

1. Add a shared validation helper in `src/ga_cli/utils/`:

```python
def validate_numeric_id(value: str, label: str = "ID") -> str:
    """Ensure a resource ID is numeric."""
    if not value.isdigit():
        raise typer.BadParameter(f"{label} must be numeric, got: {value}")
    return value
```

2. Apply at the entry point of each command that accepts an ID (accounts, properties, data-streams, custom-dimensions, mp-secrets, etc.)

**Verification:** Run `uv run ga properties get --property-id "foo; rm -rf /"` and confirm a clean validation error.

---

### S5: Check Credential File Permissions on Load

**Problem:** `src/ga_cli/auth/credentials.py` sets `0o600` permissions when writing credentials (line 54–55) but never checks permissions on load. If something loosens permissions (e.g., a backup tool restoring files), the user won't be warned.

**Steps:**

1. In `load_credentials()`, after confirming the file exists, check permissions on non-Windows systems:

```python
if platform.system() != "Windows":
    mode = creds_path.stat().st_mode & 0o777
    if mode & 0o077:
        warn(f"Credentials file has overly permissive permissions ({oct(mode)}). "
             f"Run: chmod 600 {creds_path}")
```

2. Issue a warning (not an error) — don't block the user from using the CLI.

**Verification:** `chmod 644 ~/.config/ga-cli/credentials.json`, then run any authenticated command and confirm a warning appears.

---

## Phase 3: Low — Hardening

### S6: Set Permissions on Update Check File

**Problem:** `src/ga_cli/commands/upgrade_cmd.py` (lines 139–140) writes `.update_check.json` with default file permissions. On some systems this may be world-readable.

**Steps:**

1. After writing the file, apply `0o600` permissions (same pattern as credentials):

```python
check_path.write_text(json.dumps({"last_check": now}))
if platform.system() != "Windows":
    os.chmod(check_path, 0o600)
```

---

### S7: Log Errors in Update Check Instead of Silencing

**Problem:** `maybe_check_for_updates()` in `upgrade_cmd.py` (lines 137–141) catches all exceptions with `pass`. This hides potential security issues (e.g., SSL errors, DNS hijacking).

**Steps:**

1. Replace `pass` with debug-level logging:

```python
except Exception as e:
    import logging
    logging.debug(f"Update check failed: {e}")
```

---

### S8: Replace TOCTOU File Existence Check in OAuth Flow

**Problem:** `src/ga_cli/auth/oauth.py` (line 187) checks `client_secret_path.exists()` before reading — a race condition where the file could be deleted between check and use.

**Steps:**

1. Replace the exists-then-read pattern with a try/except:

```python
try:
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
except FileNotFoundError:
    # Handle missing file
```

---

### S9: Add Dependency Vulnerability Scanning to CI

**Problem:** No automated scanning for known vulnerabilities in dependencies.

**Steps:**

1. Add a `pip-audit` step to `.github/workflows/ci.yml`:

```yaml
- name: Audit dependencies
  run: |
    pip install pip-audit
    pip-audit --requirement <(uv pip compile pyproject.toml)
```

2. Optionally enable GitHub Dependabot by adding `.github/dependabot.yml`.

---

## Checklist

- [ ] **S1** — Rotate OAuth credentials in Google Cloud Console
- [ ] **S2** — Verify OAuth client is Desktop type with localhost-only redirect
- [ ] **S3** — Mask MP secrets in table output, add `--show-secrets` flag
- [ ] **S4** — Add numeric ID validation helper and apply to all commands
- [ ] **S5** — Add permission check on credential file load
- [ ] **S6** — Set `0o600` on update check timestamp file
- [ ] **S7** — Add debug logging in update check exception handler
- [ ] **S8** — Replace TOCTOU pattern with try/except in OAuth flow
- [ ] **S9** — Add `pip-audit` to CI workflow
