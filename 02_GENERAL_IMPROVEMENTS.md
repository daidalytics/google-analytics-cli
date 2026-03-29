# General Improvements — AI-Agent Readiness

## Background

Based on recommendations from [Rewrite Your CLI for AI Agents](https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/) by Justin Poehnelt, this plan covers five improvements to make `ga-cli` more suitable for AI-agent consumption.

### Key Takeaways from the Article

The article argues that **human DX** (discoverability, forgiveness) differs fundamentally from **agent DX** (predictability, defense-in-depth):

1. **Raw JSON over flags** — Accept full API payloads via `--json`/`--params` to eliminate translation loss between agent-generated input and API schemas.
2. **JSON output everywhere** — `--output json`, auto-detect non-TTY, env var override.
3. **Runtime schema introspection** — `--schema`/`--describe` exposing params, types, scopes as machine-readable JSON so the CLI itself is the documentation source.
4. **Field masking** — `--fields` to limit response scope and conserve agent context windows.
5. **NDJSON streaming** — One JSON object per line with `--page-all` for stream-processable, memory-efficient pagination.
6. **Input hardening** — Treat agent input as hostile. Reject traversals, control chars, bad encodings. Agents hallucinate these patterns.
7. **Dry-run mode** — `--dry-run` on all mutative commands for validation without execution.
8. **Headless auth** — Env-var tokens, service accounts, no browser redirects.
9. **Skill/context files** — Ship agent guidance as structured Markdown with YAML frontmatter.
10. **MCP surface** — Expose typed JSON-RPC alongside CLI for direct tool invocation.

### Current Compliance

| Requirement | Status | Grade | Notes |
|---|---|---|---|
| JSON output | 17/19 commands | **A** | Auto-JSON on non-TTY, `--quiet` flag |
| Raw JSON input | Not implemented | **F** | Agents must construct individual flags |
| Schema introspection | Partial | **C** | `ga reports metadata` exists, no general `--describe` |
| Field masking | Not implemented | **F** | Full objects always returned |
| NDJSON / streaming | Not implemented | **F** | `paginate_all()` buffers everything |
| Input hardening | Good basics | **B** | Enum validation, path checks — no traversal/control-char blocking |
| Dry-run mode | Not implemented | **F** | Mutations execute immediately |
| Headless auth | Strong | **A** | `GA_CLI_SERVICE_ACCOUNT`, env vars, `--yes` to skip prompts |
| Skill/context files | Strong | **A** | `ga agent guide` with sections for reports, admin, examples |
| MCP surface | Not implemented | **N/A** | Out of scope for now |

---

## Implementation Order

Ordered from smallest/most-isolated to largest/most-complex:

1. [NDJSON Streaming Output](#1-ndjson-streaming-output) — localized to output layer
2. [`--fields` Filtering](#2---fields-filtering) — localized to output layer + main callback
3. [Input Hardening](#3-input-hardening) — new module + incremental per-command integration
4. [`--dry-run`](#4---dry-run-on-mutative-commands) — new module + mechanical per-command change
5. [`--json-input`](#5---json-input-on-createupdate-commands) — most complex, rethinks required vs optional flags

---

## 1. NDJSON Streaming Output

**Goal:** Add `--output ndjson` format — one JSON object per line, no array wrapper, no indentation. Useful for agents processing paginated results one record at a time.

**Status:** `[ ]` Not started

### Files to Change

| File | Change |
|---|---|
| `src/ga_cli/config/store.py` | Add `"ndjson"` to `OutputFormat` literal type |
| `src/ga_cli/utils/output.py` | Add `ndjson` branch in `output()` |
| All command files | Update `--output` help text to include `ndjson` |

### Implementation Details

**In `output.py`**, add an `ndjson` branch:

```python
elif effective_fmt == "ndjson":
    if isinstance(data, list):
        for item in data:
            console.print(json.dumps(item, default=str))
    else:
        console.print(json.dumps(data, default=str))
```

**Edge cases:**
- Empty lists produce zero lines (no "No results found" — agents expect 0 lines = 0 results)
- Single-dict output (from `get` commands): one JSON line, identical to JSON but without indentation
- Report data: transform rows and output each row as a line

### Testing

- Test NDJSON on a list of dicts — verify each line is valid JSON, N items = N lines
- Test NDJSON on a single dict — verify single line of JSON
- Test NDJSON on empty list — verify no output
- Test NDJSON can be set as default via `ga config set output_format ndjson`

---

## 2. `--fields` Filtering

**Goal:** Global option to limit which top-level fields appear in output, reducing context window waste for agents.

**Status:** `[ ]` Not started

### Files to Change

| File | Change |
|---|---|
| `src/ga_cli/main.py` | Add `--fields` to the app callback |
| `src/ga_cli/utils/output.py` | Add `set_fields()`, `_filter_fields()` applied before format dispatch |

No command files need changes — filtering happens in the shared `output()` path.

### Implementation Details

**In `main.py`**, add to callback:

```python
fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated fields to include in output")
```

Call `set_fields(fields)` in `output.py`.

**In `output.py`**, add module-level state (same pattern as `_quiet` and `_no_color`):

```python
_fields: Optional[list[str]] = None

def set_fields(fields: Optional[str]) -> None:
    global _fields
    _fields = [f.strip() for f in fields.split(",")] if fields else None

def _filter_fields(data, fields):
    if not fields:
        return data
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in fields}
    if isinstance(data, list):
        return [{k: v for k, v in item.items() if k in fields} for item in data if isinstance(item, dict)]
    return data
```

Apply `_filter_fields(data, _fields)` in `output()` before format dispatch. For table output, override `columns` and `headers` to only include filtered fields.

**Edge cases:**
- Non-existent field names: silently skip (produce partial results)
- v1 only supports top-level keys — no dot-path nesting like `webStreamData.defaultUri`
- Empty result after filtering: show empty JSON `{}` or `[]`
- Interacts with NDJSON: field filtering applies before format dispatch, so NDJSON automatically benefits

### Testing

- `--fields name,displayName` on a list command — verify other fields absent
- `--fields` with JSON output
- `--fields` with a non-existent field name
- `--fields` on a single-object command (`get`)

---

## 3. Input Hardening

**Goal:** Reject malicious or hallucinated agent inputs (path traversals, control characters, malformed resource IDs) before they reach the API.

**Status:** `[ ]` Not started

### Files to Change

| File | Change |
|---|---|
| `src/ga_cli/utils/validation.py` | **New file** — validation functions |
| `src/ga_cli/utils/__init__.py` | Re-export validation functions |
| All command files | Call validators after `require_options()` |

### Implementation Details

**New file `src/ga_cli/utils/validation.py`** with three functions:

```python
import re
import typer

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAVERSAL_RE = re.compile(r"\.\./|\.\\|%2e%2e", re.IGNORECASE)

def validate_resource_id(value: str, label: str) -> str:
    """Validate a numeric resource ID. Reject traversals, control chars, non-digits."""
    if not value:
        raise typer.BadParameter(f"{label} must not be empty")
    if _TRAVERSAL_RE.search(value):
        raise typer.BadParameter(f"{label} contains path traversal")
    if _CONTROL_CHAR_RE.search(value):
        raise typer.BadParameter(f"{label} contains control characters")
    if not re.fullmatch(r"\d+", value):
        raise typer.BadParameter(f"{label} must be numeric, got '{value}'")
    return value

def validate_string_input(value: str, label: str, max_length: int = 500) -> str:
    """Validate free-text input (display names, descriptions)."""
    if _TRAVERSAL_RE.search(value):
        raise typer.BadParameter(f"{label} contains path traversal")
    if _CONTROL_CHAR_RE.search(value):
        raise typer.BadParameter(f"{label} contains control characters")
    if len(value) > max_length:
        raise typer.BadParameter(f"{label} exceeds max length of {max_length}")
    return value

def validate_resource_name(value: str, label: str) -> str:
    """Validate a full resource name like 'properties/123456'."""
    if _TRAVERSAL_RE.search(value):
        raise typer.BadParameter(f"{label} contains path traversal")
    if _CONTROL_CHAR_RE.search(value):
        raise typer.BadParameter(f"{label} contains control characters")
    if not re.fullmatch(r"[a-zA-Z0-9/_-]+", value):
        raise typer.BadParameter(f"{label} contains invalid characters")
    return value
```

**Per-command integration pattern** (insert right after `require_options()`):

```python
validate_resource_id(effective_account, "account_id")
validate_string_input(display_name, "display_name", max_length=200)
```

**Exception:** Calculated metric formulas contain `{{...}}` — use a dedicated or relaxed validator, or skip validation for formula fields.

**Incremental rollout:** Start with `properties.py` and `accounts.py` as reference, then propagate to remaining command files.

### Testing

- Test each validation function with valid input
- Test path traversal rejection: `../etc/passwd`, `..%2f`, `..\\`
- Test control character rejection: `\x00`, `\x1f`
- Test numeric ID validation with non-numeric strings
- Integration test: pass a malicious ID to a command, verify rejection before API call

---

## 4. `--dry-run` on Mutative Commands

**Goal:** Validate and show what would be sent to the API without executing. Critical safety mechanism for agents.

**Status:** `[ ]` Not started

### Files to Change

| File | Change |
|---|---|
| `src/ga_cli/utils/dry_run.py` | **New file** — `handle_dry_run()` helper |
| `src/ga_cli/utils/__init__.py` | Re-export `handle_dry_run` |
| ~20 command functions | Add `--dry-run` option + check before `.execute()` |

### Affected Commands

| Command file | Functions to update |
|---|---|
| `accounts.py` | update, delete |
| `properties.py` | create, update, delete, acknowledge-udc |
| `data_streams.py` | create, update, delete |
| `custom_dimensions.py` | create, update, archive |
| `custom_metrics.py` | create, update, archive |
| `key_events.py` | create, update, delete |
| `annotations.py` | create, update, delete |
| `calculated_metrics.py` | create, update, delete |
| `firebase_links.py` | create, delete |
| `google_ads_links.py` | create, update, delete |
| `mp_secrets.py` | create, update, delete |
| `data_retention.py` | update |

### Implementation Details

**New file `src/ga_cli/utils/dry_run.py`:**

```python
import typer
from ga_cli.utils.output import output

def handle_dry_run(
    action: str,
    resource_path: str,
    body: dict | None,
    fmt: str,
) -> None:
    """Output what would happen and exit."""
    payload = {
        "dry_run": True,
        "action": action,       # "create", "update", "delete"
        "resource": resource_path,
    }
    if body is not None:
        payload["body"] = body
    output(payload, fmt)
    raise typer.Exit(0)
```

**Per-command pattern:**

1. Add to signature:
   ```python
   dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without executing"),
   ```

2. Insert right before the `.execute()` call:
   ```python
   if dry_run:
       handle_dry_run("create", f"accounts/{effective_account}/properties", body, effective_format)
   ```

**Edge cases:**
- **Delete commands:** `body` is `None` — show only action + resource path
- **Update commands:** Include `updateMask` in the dry-run payload so the agent sees which fields would change
- **Confirmation prompts:** Skip them entirely in dry-run mode (no point asking "are you sure?" for a no-op)

### Testing

Per mutative command, add a test that:
- Passes `--dry-run` and asserts exit code 0
- Asserts output contains `"dry_run": true`
- Asserts the API `.execute()` mock is **never called** (`assert_not_called()`)

---

## 5. `--json-input` on Create/Update Commands

**Goal:** Accept a raw JSON body as an alternative to individual CLI flags, eliminating translation loss for agents.

**Status:** `[ ]` Not started

### Files to Change

| File | Change |
|---|---|
| `src/ga_cli/utils/json_input.py` | **New file** — parse + merge helpers |
| `src/ga_cli/utils/__init__.py` | Re-export |
| ~16 create/update command functions | Add `--json-input` option, make flags optional, validate merged body |

### Design Decisions

- **Flag name:** `--json-input` (not `--json`) to avoid confusion with `--output json`
- **Precedence:** Individual CLI flags override JSON keys when both are provided
- **Required flags:** Become `Optional` when `--json-input` exists — post-merge validation ensures all required fields are present
- **Validation:** JSON values pass through input hardening (Improvement 3) after parsing

### Implementation Details

**New file `src/ga_cli/utils/json_input.py`:**

```python
import json
import typer

def parse_json_input(json_str: str) -> dict:
    """Parse a JSON string, raising typer.BadParameter on invalid JSON."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON: {e}")
    if not isinstance(data, dict):
        raise typer.BadParameter("JSON input must be an object, not a list or scalar")
    return data

def merge_json_with_flags(json_body: dict, flag_overrides: dict) -> dict:
    """Merge JSON body with CLI flag values. Flags take precedence.

    flag_overrides should only contain keys that were explicitly set by the user
    (i.e., not None).
    """
    merged = {**json_body}
    for k, v in flag_overrides.items():
        if v is not None:
            merged[k] = v
    return merged
```

**Per-command integration pattern (using `properties create` as reference):**

Before (current):
```python
def create(
    display_name: str = typer.Option(..., "--name", help="Display name"),
    ...
):
    body = {"displayName": display_name, ...}
```

After:
```python
def create(
    display_name: Optional[str] = typer.Option(None, "--name", help="Display name"),
    json_input: Optional[str] = typer.Option(None, "--json-input", help="JSON request body"),
    ...
):
    if json_input:
        base = parse_json_input(json_input)
        flag_overrides = {}
        if display_name is not None:
            flag_overrides["displayName"] = display_name
        body = merge_json_with_flags(base, flag_overrides)
    else:
        if display_name is None:
            raise typer.BadParameter("--name is required (or use --json-input)")
        body = {"displayName": display_name, ...}
```

**Edge cases:**
- Invalid JSON: `typer.BadParameter("Invalid JSON: ...")`
- JSON provides fields the API doesn't accept: let the API return the error (don't over-validate)
- JSON missing required fields and no flags provided: raise `typer.BadParameter` with a clear message listing missing fields
- Interaction with `--dry-run`: JSON input is parsed and merged, then dry-run outputs the merged body without executing

### Affected Commands

| Command file | Functions |
|---|---|
| `accounts.py` | update |
| `properties.py` | create, update |
| `data_streams.py` | create, update |
| `custom_dimensions.py` | create, update |
| `custom_metrics.py` | create, update |
| `key_events.py` | create, update |
| `annotations.py` | create, update |
| `calculated_metrics.py` | create, update |
| `firebase_links.py` | create |
| `google_ads_links.py` | create, update |
| `mp_secrets.py` | create, update |
| `data_retention.py` | update |

### Testing

- JSON-only create (no flags) — verify correct body
- Flags-only create (no JSON) — existing tests cover this, verify they still pass
- JSON + flag override — verify flag wins
- Invalid JSON input — verify `typer.BadParameter`
- JSON missing required fields, no flags — verify clear error message

---

## Files Changed Summary

| File | Improvements |
|---|---|
| `src/ga_cli/utils/output.py` | 1 (NDJSON), 2 (fields) |
| `src/ga_cli/utils/validation.py` | 3 — **new** |
| `src/ga_cli/utils/dry_run.py` | 4 — **new** |
| `src/ga_cli/utils/json_input.py` | 5 — **new** |
| `src/ga_cli/utils/__init__.py` | 3, 4, 5 (re-exports) |
| `src/ga_cli/main.py` | 2 (`--fields` global option) |
| `src/ga_cli/config/store.py` | 1 (`OutputFormat` adds `"ndjson"`) |
| All command files | 1 (help text), 3 (validation calls), 4 (`--dry-run`), 5 (`--json-input`) |
