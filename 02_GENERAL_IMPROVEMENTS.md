# General Improvements — AI-Agent Readiness

## Background

Based on recommendations from [Rewrite Your CLI for AI Agents](https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/) by Justin Poehnelt, this plan covers four improvements to make `ga-cli` an agent-first CLI — optimized for Claude Code and CI/CD pipelines, with human use as a secondary concern.

### Design Principles

1. **Predictable, machine-parseable output** — all output (including errors) must be structured JSON when the agent requests it
2. **Self-documenting** — the CLI itself is the schema source; no stale docs or external references needed
3. **Safe by default** — mutations are previewable before execution
4. **Minimal translation loss** — agents pass API payloads directly, not reconstructed flag-by-flag

### Current Compliance

| Requirement | Status | Grade | Notes |
|---|---|---|---|
| JSON output | 17/19 commands | **A** | Auto-JSON on non-TTY, `--quiet` flag |
| Structured errors | **Implemented** | **A** | JSON errors on stderr, exit codes 1/2/3/4, `resolve_output_format()` |
| Dry-run mode | Not implemented | **F** | Mutations execute immediately |
| Schema introspection | Partial | **C** | `ga reports metadata` exists, no general `--describe` |
| Raw JSON input | Not implemented | **F** | Agents must construct individual flags |
| Headless auth | Strong | **A** | `GA_CLI_SERVICE_ACCOUNT`, env vars, `--yes` to skip prompts |
| Skill/context files | Strong | **A** | `ga agent guide` with sections for reports, admin, examples |

---

## Implementation Order

Ordered by agent value and dependency chain:

1. [Structured Error Output](#1-structured-error-output) — foundational; everything else builds on predictable error handling
2. [`--dry-run`](#2---dry-run-on-mutative-commands) — agent safety; highest immediate value for mutation commands
3. [`--describe` Schema Introspection](#3---describe-schema-introspection) — self-documenting CLI; future MCP bridge
4. [`--json-input`](#4---json-input-on-createupdate-commands) — full agent autonomy for mutations

**Dropped from original plan** (discussed, decided not worth the complexity):
- ~~NDJSON streaming~~ — GA4 response sizes are modest; JSON + `jq` covers all agent needs
- ~~`--fields` filtering~~ — `jq` achieves the same client-side filtering (`ga properties list -o json | jq '[.[] | {name, displayName}]'`)
- ~~Input hardening~~ — can be rolled out incrementally later; Google API already rejects bad input

---

## 1. Structured Error Output

**Goal:** Make errors machine-parseable. When `-o json` is active (explicitly or via non-TTY detection), errors are JSON on stderr with distinct exit codes. Agents can branch on failure type without parsing human-readable strings.

**Status:** `[x]` **Done**

### Exit Code Scheme

| Code | Meaning | When |
|---|---|---|
| 0 | Success | Command completed |
| 1 | Client error | Bad input, missing flags, validation failure (`typer.BadParameter`) |
| 2 | Auth error | Not authenticated, token expired, permission denied (401/403) |
| 3 | API error | Google returned 4xx (not auth) or 5xx |
| 4 | Network error | Connection timeout, DNS failure, unreachable |

### Files Changed

| File | Change |
|---|---|
| `src/ga_cli/utils/errors.py` | New `classify_error()` function mapping exceptions to exit codes. Updated `handle_error()` to emit JSON to stderr when format is `"json"`, raw `print()` to avoid Rich line-wrapping |
| `src/ga_cli/utils/output.py` | Added `set_output_format()` / `get_current_output_format()` for format tracking. Added `resolve_output_format()` helper that resolves CLI flag > config > TTY detection and updates the global format |
| `src/ga_cli/utils/__init__.py` | Re-exports `classify_error`, `resolve_output_format` |
| `src/ga_cli/main.py` | Calls `set_output_format()` in the app callback for early format resolution |
| All 22 command files | Replaced `get_effective_value(output_format, "output_format") or "table"` with `resolve_output_format(output_format)` (83 occurrences) so the subcommand's `-o` flag propagates to error handling |
| `tests/conftest.py` | Resets `_current_output_format` between tests |
| `tests/test_errors.py` | New `TestClassifyError` (14 tests) and `TestHandleErrorJson` (6 tests). Updated `TestHandleError` to assert classified exit codes |
| `tests/test_output.py` | New `TestOutputFormatTracking` (3 tests) |
| 25 command test files | Updated `exit_code == 1` assertions to `== 2` (auth/403) or `== 3` (API/generic) |

### Implementation Notes

- **JSON errors written with `print()` to stderr**, not Rich Console — Rich wraps long lines which breaks `json.loads()`
- **`resolve_output_format()`** replaced the manual `get_effective_value(output_format, "output_format") or "table"` pattern across all commands, ensuring the global format is always in sync when `handle_error()` runs
- **`classify_error()` uses guarded imports** (`try/except ImportError`) for `google.auth.exceptions`, `requests.exceptions`, and `urllib3.exceptions` to avoid hard dependency failures
- **Network OSError filtering** via `_is_network_os_error()` — only classifies connection-related errnos (ECONNREFUSED, ETIMEDOUT, etc.) as network errors, not file I/O OSErrors
- **`typer.BadParameter` errors** remain Typer-formatted (not JSON) — they're raised before `handle_error()` and include the flag name, which is useful enough for agents

### Verified Behavior

```
# Auth error (403) — JSON output
$ ga properties get -p 999999999999 -o json
stderr: {"error": true, "exit_code": 2, "category": "auth_error", "message": "The caller does not have permission", "status_code": 403}
exit: 2

# API error (400) — JSON output
$ ga reports run -p 250400352 -m "nonexistent_metric" -d "date" -o json
stderr: {"error": true, "exit_code": 3, "category": "api_error", "message": "Did you mean engagementRate? ...", "status_code": 400}
exit: 3

# Auth error (403) — table output (human-readable, unchanged)
$ ga properties get -p 999999999999 -o table
stderr: Error: The caller does not have permission
exit: 2
```

---

## 2. `--dry-run` on Mutative Commands

**Goal:** Validate and show what would be sent to the API without executing. Agents can preview mutations, verify their parameters, and catch mistakes before they become live changes.

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
    method: str,
    resource_path: str,
    body: dict | None,
    fmt: str,
    update_mask: str | None = None,
) -> None:
    """Output what would be sent to the API and exit.

    Args:
        action: "create", "update", or "delete"
        method: HTTP method that would be used ("POST", "PATCH", "DELETE")
        resource_path: Full API resource path (e.g., "properties/123456")
        body: Request body dict, or None for deletes
        fmt: Output format ("json", "table", etc.)
        update_mask: For PATCH requests, the updateMask value
    """
    payload = {
        "dry_run": True,
        "action": action,
        "method": method,
        "resource": resource_path,
        "idempotent": action == "delete",
    }
    if body is not None:
        payload["body"] = body
    if update_mask is not None:
        payload["update_mask"] = update_mask
    output(payload, fmt)
    raise typer.Exit(0)
```

**Per-command pattern:**

1. Add to function signature:
   ```python
   dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without executing"),
   ```

2. For **create** commands — insert right before `.execute()`:
   ```python
   if dry_run:
       handle_dry_run("create", "POST", f"properties/{effective_property}", body, effective_format)
   ```

3. For **update** commands — insert right before `.execute()`:
   ```python
   if dry_run:
       handle_dry_run(
           "update", "PATCH", f"properties/{effective_property}",
           body, effective_format, update_mask=update_mask,
       )
   ```

4. For **delete** commands — insert before confirmation *and* execution:
   ```python
   if dry_run:
       handle_dry_run("delete", "DELETE", f"properties/{effective_property}", None, effective_format)
   # Confirmation prompt only runs if not dry-run
   if not yes:
       confirmed = questionary.confirm(...).ask()
       ...
   ```

### Example Dry-Run Output

**Create:**
```json
{
  "dry_run": true,
  "action": "create",
  "method": "POST",
  "resource": "accounts/123456",
  "idempotent": false,
  "body": {
    "parent": "accounts/123456",
    "displayName": "My Property",
    "timeZone": "America/Los_Angeles",
    "currencyCode": "USD"
  }
}
```

**Update:**
```json
{
  "dry_run": true,
  "action": "update",
  "method": "PATCH",
  "resource": "properties/123456",
  "idempotent": false,
  "body": {
    "displayName": "New Name"
  },
  "update_mask": "displayName"
}
```

**Delete:**
```json
{
  "dry_run": true,
  "action": "delete",
  "method": "DELETE",
  "resource": "properties/123456",
  "idempotent": true
}
```

### Edge Cases

- **Delete commands:** `body` is `None` — payload shows only action + resource
- **Update commands:** `update_mask` included so the agent sees which fields change
- **Confirmation prompts:** Skipped entirely in dry-run mode (no "are you sure?" for a no-op)
- **`--dry-run` + `--json-input`** (Improvement 4): JSON is parsed and merged first, then dry-run outputs the merged body — works naturally since dry-run check happens after body construction
- **Idempotency hint:** `"idempotent": true` for deletes (safe to retry), `false` for creates (may duplicate)

### Testing

Per mutative command, add a test that:
- Passes `--dry-run` and asserts exit code 0
- Asserts output contains `"dry_run": true`, the correct `action`, and the expected `resource` path
- Asserts the API `.execute()` mock is **never called** (`assert_not_called()`)
- For update commands: verify `update_mask` is present
- For delete commands: verify `body` is absent, `idempotent` is `true`

---

## 3. `--describe` Schema Introspection

**Goal:** Every command can describe its own interface as JSON Schema, making the CLI self-documenting for agents. This eliminates stale documentation and becomes the bridge to auto-generated MCP tool definitions.

**Status:** `[ ]` Not started

### Design: JSON Schema Output

The `--describe` flag outputs a JSON object that is close to JSON Schema / MCP tool definition format. This makes it trivial to auto-generate MCP `tools` from CLI introspection.

```json
{
  "command": "ga properties create",
  "description": "Create a new GA4 property",
  "parameters": {
    "type": "object",
    "properties": {
      "display_name": {
        "type": "string",
        "description": "Display name for the property",
        "flag": "--name",
        "required": true
      },
      "account_id": {
        "type": "string",
        "description": "Parent account ID",
        "flag": "--account-id",
        "aliases": ["-a"],
        "required": true,
        "config_fallback": "default_account_id"
      },
      "timezone": {
        "type": "string",
        "description": "Reporting timezone",
        "flag": "--timezone",
        "default": "America/Los_Angeles"
      },
      "currency": {
        "type": "string",
        "description": "Reporting currency code",
        "flag": "--currency",
        "default": "USD"
      },
      "json_input": {
        "type": "string",
        "description": "Raw JSON request body (alternative to individual flags)",
        "flag": "--json-input"
      }
    },
    "required": ["display_name", "account_id"]
  },
  "output": {
    "type": "object",
    "description": "The created GA4 property resource"
  },
  "mutative": true,
  "supports_dry_run": true,
  "supports_json_input": true
}
```

### Files to Change

| File | Change |
|---|---|
| `src/ga_cli/utils/describe.py` | **New file** — `CommandSchema` dataclass, `handle_describe()`, schema registry |
| `src/ga_cli/utils/__init__.py` | Re-export `handle_describe`, `register_schema` |
| All command files | Register schema metadata via decorator or call, add `--describe` flag |
| `src/ga_cli/main.py` | Add `ga --describe` for top-level CLI schema (lists all command groups) |

### Implementation Details

**New file `src/ga_cli/utils/describe.py`:**

```python
import json
import sys
from dataclasses import dataclass, field


@dataclass
class ParamSchema:
    """Schema for a single CLI parameter."""
    name: str
    type: str                           # "string", "integer", "boolean", "array"
    description: str
    flag: str                           # "--name", "--property-id"
    aliases: list[str] = field(default_factory=list)   # ["-p", "-a"]
    required: bool = False
    default: str | int | bool | None = None
    enum: list[str] | None = None       # Allowed values
    config_fallback: str | None = None  # Config key that can provide this value


@dataclass
class CommandSchema:
    """Schema for a CLI command."""
    command: str                         # "ga properties create"
    description: str
    parameters: list[ParamSchema]
    mutative: bool = False
    supports_dry_run: bool = False
    supports_json_input: bool = False
    output_description: str = "JSON object or table"


# Registry: command_name -> CommandSchema
_schemas: dict[str, CommandSchema] = {}


def register_schema(schema: CommandSchema) -> None:
    """Register a command's schema for --describe lookups."""
    _schemas[schema.command] = schema


def get_schema(command: str) -> CommandSchema | None:
    """Look up a registered schema by command name."""
    return _schemas.get(command)


def get_all_schemas() -> dict[str, CommandSchema]:
    """Return all registered schemas."""
    return dict(_schemas)


def schema_to_json(schema: CommandSchema) -> dict:
    """Convert a CommandSchema to a JSON-serializable dict (JSON Schema-like)."""
    properties = {}
    required = []

    for param in schema.parameters:
        prop: dict = {
            "type": param.type,
            "description": param.description,
            "flag": param.flag,
        }
        if param.aliases:
            prop["aliases"] = param.aliases
        if param.default is not None:
            prop["default"] = param.default
        if param.enum is not None:
            prop["enum"] = param.enum
        if param.config_fallback:
            prop["config_fallback"] = param.config_fallback
        if param.required:
            required.append(param.name)

        properties[param.name] = prop

    result = {
        "command": schema.command,
        "description": schema.description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        "mutative": schema.mutative,
        "supports_dry_run": schema.supports_dry_run,
        "supports_json_input": schema.supports_json_input,
        "output": {
            "description": schema.output_description,
        },
    }
    return result


def handle_describe(command: str) -> None:
    """Output the schema for a command and exit."""
    schema = get_schema(command)
    if schema is None:
        print(json.dumps({"error": f"No schema registered for '{command}'"}))
        sys.exit(1)
    print(json.dumps(schema_to_json(schema), indent=2))
    sys.exit(0)


def handle_describe_all() -> None:
    """Output schemas for all registered commands and exit."""
    all_schemas = get_all_schemas()
    result = {
        "cli": "ga-cli",
        "commands": {name: schema_to_json(schema) for name, schema in sorted(all_schemas.items())},
    }
    print(json.dumps(result, indent=2))
    sys.exit(0)
```

**Per-command registration pattern:**

Each command file registers its schemas at module level. Example for `properties.py`:

```python
from ..utils.describe import register_schema, CommandSchema, ParamSchema

# Register schemas for --describe
register_schema(CommandSchema(
    command="ga properties create",
    description="Create a new GA4 property",
    parameters=[
        ParamSchema(
            name="display_name", type="string",
            description="Display name for the property",
            flag="--name", required=True,
        ),
        ParamSchema(
            name="account_id", type="string",
            description="Parent account ID",
            flag="--account-id", aliases=["-a"],
            required=True, config_fallback="default_account_id",
        ),
        ParamSchema(
            name="timezone", type="string",
            description="Reporting timezone",
            flag="--timezone", default="America/Los_Angeles",
        ),
        ParamSchema(
            name="currency", type="string",
            description="Reporting currency code",
            flag="--currency", default="USD",
        ),
    ],
    mutative=True,
    supports_dry_run=True,
    supports_json_input=True,
    output_description="The created GA4 property resource",
))

register_schema(CommandSchema(
    command="ga properties list",
    description="List GA4 properties for an account",
    parameters=[
        ParamSchema(
            name="account_id", type="string",
            description="Account ID to list properties for",
            flag="--account-id", aliases=["-a"],
            required=True, config_fallback="default_account_id",
        ),
    ],
    mutative=False,
    output_description="Array of GA4 property resources",
))
```

**Per-command `--describe` flag:**

```python
@properties_app.command("create")
def create_cmd(
    # ... existing params ...
    describe: bool = typer.Option(False, "--describe", help="Show command schema as JSON"),
):
    if describe:
        handle_describe("ga properties create")
    # ... rest of command ...
```

**Top-level `--describe` in `main.py`:**

```python
@app.callback(invoke_without_command=True)
def main(
    # ... existing params ...
    describe: bool = typer.Option(False, "--describe", help="Show CLI schema as JSON"),
):
    # ... existing logic ...
    if describe:
        from .utils.describe import handle_describe_all
        handle_describe_all()
```

### MCP Bridge (Future)

The schema format is designed to map directly to MCP tool definitions:

```python
# Future: auto-generate MCP tools from CLI schemas
def schema_to_mcp_tool(schema: CommandSchema) -> dict:
    """Convert a CommandSchema to an MCP tool definition."""
    return {
        "name": schema.command.replace(" ", "_").replace("ga_", "ga4_"),
        "description": schema.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                p.name: {"type": p.type, "description": p.description}
                for p in schema.parameters
            },
            "required": [p.name for p in schema.parameters if p.required],
        },
    }
```

### Edge Cases

- **Commands without schemas:** If `--describe` is called on a command that hasn't registered a schema, return an error JSON with exit code 1.
- **`ga --describe`** (top-level): Returns all schemas — useful for agents to discover the full CLI surface in one call.
- **Schema staleness:** Schemas are co-located with command code, so they update together. Add a CI check that compares registered schema parameter names against actual Typer option names to catch drift.
- **`--describe` + other flags:** `--describe` takes precedence and exits immediately (no API calls, no auth needed).

### Testing

- Test `--describe` on a registered command → verify JSON Schema structure, parameter names, types
- Test `--describe` on top-level `ga` → verify all registered commands appear
- Test `--describe` on unregistered command → verify error JSON
- Test that `required` fields match actual Typer `...` (required) vs `None` (optional)
- Test that `mutative`, `supports_dry_run`, `supports_json_input` flags are accurate
- CI lint: verify schema parameter count matches Typer option count per command (catches forgotten schema updates)

---

## 4. `--json-input` on Create/Update Commands

**Goal:** Accept a raw JSON body as an alternative to individual CLI flags, eliminating translation loss. Agents pass the API payload directly instead of decomposing it into flags.

**Status:** `[ ]` Not started

### Design Decisions

- **Flag name:** `--json-input` (not `--json`) to avoid confusion with `--output json`
- **Precedence:** Individual CLI flags override JSON keys when both are provided
- **Required flags:** Become `Optional` when `--json-input` exists — post-merge validation ensures all required fields are present
- **Stdin support:** `--json-input -` reads from stdin; `--json-input @file.json` reads from a file
- **Interaction with `--dry-run`:** JSON is parsed and merged first, then dry-run outputs the merged body

### Files to Change

| File | Change |
|---|---|
| `src/ga_cli/utils/json_input.py` | **New file** — parse, merge, stdin/file reading |
| `src/ga_cli/utils/__init__.py` | Re-export |
| ~16 create/update command functions | Add `--json-input` option, make flags optional, validate merged body |

### Implementation Details

**New file `src/ga_cli/utils/json_input.py`:**

```python
import json
import sys
import typer


def read_json_input(value: str) -> str:
    """Read JSON from a string, stdin (-), or file (@path).

    Supports three input modes:
      - Literal JSON string: '{"displayName": "My Prop"}'
      - Stdin: '-'  (reads all of stdin)
      - File: '@path/to/file.json'

    Returns the raw JSON string (not yet parsed).
    """
    if value == "-":
        if sys.stdin.isatty():
            raise typer.BadParameter("--json-input - requires piped input, but stdin is a terminal")
        return sys.stdin.read()
    if value.startswith("@"):
        path = value[1:]
        try:
            with open(path) as f:
                return f.read()
        except FileNotFoundError:
            raise typer.BadParameter(f"File not found: {path}")
        except PermissionError:
            raise typer.BadParameter(f"Permission denied: {path}")
    return value


def parse_json_input(json_str: str) -> dict:
    """Parse a JSON string into a dict.

    Raises typer.BadParameter on invalid JSON or non-object input.
    """
    raw = read_json_input(json_str)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON: {e}")
    if not isinstance(data, dict):
        raise typer.BadParameter("JSON input must be an object, not a list or scalar")
    return data


def merge_json_with_flags(json_body: dict, flag_overrides: dict) -> dict:
    """Merge JSON body with CLI flag values. Flags take precedence.

    flag_overrides should only contain keys explicitly set by the user
    (i.e., not None). Keys use API field names (camelCase).
    """
    merged = {**json_body}
    for k, v in flag_overrides.items():
        if v is not None:
            merged[k] = v
    return merged


def require_fields(body: dict, required: list[str], flag_hints: dict[str, str]) -> None:
    """Validate that all required fields are present in the merged body.

    Args:
        body: The merged request body.
        required: List of required API field names (camelCase).
        flag_hints: Mapping of API field name to CLI flag name,
                    for helpful error messages. E.g. {"displayName": "--name"}
    """
    missing = [f for f in required if not body.get(f)]
    if missing:
        hints = [f"{f} ({flag_hints.get(f, f)})" for f in missing]
        raise typer.BadParameter(
            f"Missing required fields: {', '.join(hints)}. "
            f"Provide via --json-input or individual flags."
        )
```

**Per-command integration pattern (using `properties create` as reference):**

Before (current):
```python
def create_cmd(
    display_name: str = typer.Option(..., "--name", help="Display name"),
    account_id: Optional[str] = typer.Option(None, "--account-id", "-a", help="..."),
    timezone: str = typer.Option("America/Los_Angeles", "--timezone", help="..."),
    currency: str = typer.Option("USD", "--currency", help="..."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="..."),
):
    ...
    body = {
        "parent": f"accounts/{effective_account}",
        "displayName": display_name,
        "timeZone": timezone,
        "currencyCode": currency,
    }
    item = admin.properties().create(body=body).execute()
```

After:
```python
def create_cmd(
    display_name: Optional[str] = typer.Option(None, "--name", help="Display name"),
    account_id: Optional[str] = typer.Option(None, "--account-id", "-a", help="..."),
    timezone: Optional[str] = typer.Option(None, "--timezone", help="..."),
    currency: Optional[str] = typer.Option(None, "--currency", help="..."),
    json_input: Optional[str] = typer.Option(None, "--json-input", help="JSON request body"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="..."),
):
    ...
    if json_input:
        body = parse_json_input(json_input)
        # Flags override JSON values when explicitly provided
        flag_overrides = {}
        if display_name is not None:
            flag_overrides["displayName"] = display_name
        if timezone is not None:
            flag_overrides["timeZone"] = timezone
        if currency is not None:
            flag_overrides["currencyCode"] = currency
        body = merge_json_with_flags(body, flag_overrides)
    else:
        # Traditional flag-only path — apply defaults for optional fields
        body = {}
        if display_name is not None:
            body["displayName"] = display_name
        if timezone is not None:
            body["timeZone"] = timezone
        else:
            body["timeZone"] = "America/Los_Angeles"
        if currency is not None:
            body["currencyCode"] = currency
        else:
            body["currencyCode"] = "USD"

    # Ensure parent is always set from resolved account_id
    body["parent"] = f"accounts/{effective_account}"

    # Validate required fields regardless of input mode
    require_fields(body, ["displayName"], {"displayName": "--name"})

    if dry_run:
        handle_dry_run("create", "POST", f"accounts/{effective_account}", body, effective_format)

    item = admin.properties().create(body=body).execute()
```

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

### Example Agent Workflows

**Direct JSON payload:**
```bash
ga properties create \
  --account-id 123456 \
  --json-input '{"displayName": "My Property", "timeZone": "Europe/Berlin", "currencyCode": "EUR"}' \
  -o json
```

**JSON from file (complex body):**
```bash
ga data-streams create \
  --property-id 123456 \
  --json-input @stream_config.json \
  -o json
```

**Stdin pipe (chaining commands):**
```bash
echo '{"displayName": "Updated Name"}' | ga properties update --property-id 123456 --json-input - -o json
```

**JSON + flag override:**
```bash
ga properties create \
  --account-id 123456 \
  --json-input '{"timeZone": "UTC", "currencyCode": "EUR"}' \
  --name "Override Name" \
  -o json
```

**Combined with dry-run (preview before executing):**
```bash
ga properties create \
  --account-id 123456 \
  --json-input '{"displayName": "My Property"}' \
  --dry-run \
  -o json
```

### Edge Cases

- **Invalid JSON:** `typer.BadParameter("Invalid JSON: ...")`
- **JSON provides unknown fields:** Let the API return the error (don't over-validate — API knows its own schema)
- **JSON missing required fields, no flags:** `require_fields()` raises `typer.BadParameter` with a clear message listing missing fields and their corresponding flags
- **`--json-input` + `--dry-run`:** JSON is parsed and merged first, then dry-run outputs the merged body
- **Stdin when TTY:** Error with "requires piped input" (prevents interactive hang)
- **Flag defaults vs JSON:** When `--json-input` is provided, flag defaults are NOT applied — only explicitly-set flags override. This prevents `--timezone America/Los_Angeles` from silently overriding a timezone the agent set in JSON.
- **Backwards compatibility:** Existing flag-only usage is unchanged. All current tests pass without modification.

### Testing

- JSON-only create (no flags) → verify correct body sent to API
- Flags-only create (no JSON) → existing tests cover this, verify they still pass
- JSON + flag override → verify flag wins
- Invalid JSON input → verify `typer.BadParameter`
- JSON missing required fields, no flags → verify clear error message
- `--json-input -` with piped input → verify stdin reading
- `--json-input @file.json` → verify file reading
- `--json-input @nonexistent.json` → verify file not found error
- `--json-input` + `--dry-run` → verify merged body in dry-run output, API not called

---

## Files Changed Summary

| File | Improvements |
|---|---|
| `src/ga_cli/utils/errors.py` | 1 (structured errors, exit codes) |
| `src/ga_cli/utils/output.py` | 1 (format tracking for errors) |
| `src/ga_cli/utils/dry_run.py` | 2 — **new** |
| `src/ga_cli/utils/describe.py` | 3 — **new** |
| `src/ga_cli/utils/json_input.py` | 4 — **new** |
| `src/ga_cli/utils/__init__.py` | 2, 3, 4 (re-exports) |
| `src/ga_cli/main.py` | 1 (output format in callback), 3 (`--describe` top-level) |
| All command files | 2 (`--dry-run`), 3 (`--describe` + schema registration), 4 (`--json-input`) |

## Dependency Chain

```
1. Structured Errors    (standalone — no dependencies)
        ↓
2. --dry-run            (uses output(), benefits from structured errors)
        ↓
3. --describe           (references dry-run + json-input support in schema metadata)
        ↓
4. --json-input         (interacts with --dry-run; schema registered in --describe)
```

Improvements 1 and 2 can be built and shipped independently. Improvement 3 references whether commands support dry-run and json-input (metadata flags), so it's best done after those are finalized — but the `describe.py` infrastructure can be built early and schemas filled in as features land. Improvement 4 is the most invasive (changes function signatures) and should go last.
