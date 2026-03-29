# Tier 2 Implementation Plan — Alpha API Workstreams

## Context

Tier 1 (all 19 v1beta workstreams) is complete. Tier 2 adds 11 workstreams that use **v1alpha** APIs — both `analyticsadmin` and `analyticsdata` alpha endpoints. This is the first time alpha APIs are introduced to the project.

The key architectural prerequisite is adding two new alpha client builders (`get_admin_alpha_client()` and `get_data_alpha_client()`) since the project currently only has v1beta clients.

---

## Phase 0: Alpha Client Infrastructure

**File:** `src/ga_cli/api/client.py`

Add two new cached client builders following the existing pattern:

- `get_admin_alpha_client()` → `build("analyticsadmin", "v1alpha", credentials=creds)`
- `get_data_alpha_client()` → `build("analyticsdata", "v1alpha", credentials=creds)`
- Update `clear_client_cache()` to also clear the two new cached instances

This is a **shared dependency** for nearly all Tier 2 workstreams.

---

## Phase 1: Admin Alpha CRUD Commands (WS-AA1 through WS-AA8)

These 8 workstreams follow the exact same CRUD pattern as existing commands (custom-dimensions, google-ads-links, etc.) but use `get_admin_alpha_client()` instead of `get_admin_client()`.

### Implementation order and details:

#### 1. WS-AA1: Audiences (`ga audiences`)
- **Commands:** list, get, create, update, archive (not delete — uses archive endpoint)
- **Files:** `src/ga_cli/commands/audiences.py`, `tests/test_audiences.py`
- **Notes:** create/update use `--config` JSON file (complex filter clauses). Archive uses `questionary.confirm` like delete.
- **Table columns:** Name, Display Name, Description, Membership Duration Days

#### 2. WS-AA2: BigQuery Links (`ga bigquery-links`)
- **Commands:** list, get, create, update, delete
- **Files:** `src/ga_cli/commands/bigquery_links.py`, `tests/test_bigquery_links.py`
- **Notes:** create uses CLI flags: `--project`, `--daily-export/--no-daily-export`, `--streaming-export/--no-streaming-export`, `--include-advertising-id/--no-include-advertising-id`, `--fresh-daily-export/--no-fresh-daily-export`
- **Table columns:** Name, Project, Daily Export, Streaming Export, Create Time

#### 3. WS-AA3: Channel Groups (`ga channel-groups`)
- **Commands:** list, get, create, update, delete
- **Files:** `src/ga_cli/commands/channel_groups.py`, `tests/test_channel_groups.py`
- **Notes:** create/update use `--config` JSON file (complex rule structures)
- **Table columns:** Name, Display Name, Description, System Defined

#### 4. WS-AA4: Calculated Metrics (`ga calculated-metrics`)
- **Commands:** list, get, create, update, delete
- **Files:** `src/ga_cli/commands/calculated_metrics.py`, `tests/test_calculated_metrics.py`
- **Notes:** create uses CLI flags: `--calculated-metric-id`, `--display-name`, `--description`, `--formula`, `--metric-unit`
- **Table columns:** Name, Calculated Metric ID, Display Name, Formula, Metric Unit

#### 5. WS-AA5: Event Create Rules (`ga event-create-rules`)
- **Commands:** list, get, create, update, delete
- **Files:** `src/ga_cli/commands/event_create_rules.py`, `tests/test_event_create_rules.py`
- **Notes:** All commands require **both** `--property-id` and `--stream-id`. Parent path: `properties/{id}/dataStreams/{id}`. create/update use `--config` JSON.
- **Table columns:** Name, Destination Event, Conditions Count

#### 6. WS-AA6: Event Edit Rules (`ga event-edit-rules`)
- **Commands:** list, get, create, update, delete, **reorder**
- **Files:** `src/ga_cli/commands/event_edit_rules.py`, `tests/test_event_edit_rules.py`
- **Notes:** Same as WS-AA5 plus a `reorder` command with `--rule-ids` (comma-separated IDs). 6 commands total.
- **Table columns:** Name, Display Name, Processing Order

#### 7. WS-AA7: Access Bindings (`ga access-bindings`)
- **Commands:** list, get, create, update, delete
- **Files:** `src/ga_cli/commands/access_bindings.py`, `tests/test_access_bindings.py`
- **Notes:** Each command accepts **either** `--account-id` or `--property-id` (mutually exclusive parent). create uses `--user` (email) and `--roles` (comma-separated). Tests must cover both account-level and property-level paths.
- **Table columns:** Name, User, Roles

#### 8. WS-AA8: Reporting Data Annotations (`ga annotations`)
- **Commands:** list, get, create, update, delete
- **Files:** `src/ga_cli/commands/annotations.py`, `tests/test_annotations.py`
- **Notes:** create uses CLI flags: `--title`, `--description`, `--annotation-date` (YYYY-MM-DD), `--color`. Straightforward CRUD.
- **Table columns:** Name, Title, Date, Description, Color

---

## Phase 2: Admin Alpha Settings (WS-AA9)

#### 9. WS-AA9: Property Settings (`ga property-settings`)
- **Commands:** attribution, google-signals, enhanced-measurement (3 get/set hybrid commands)
- **Files:** `src/ga_cli/commands/property_settings.py`, `tests/test_property_settings.py`
- **Notes:** Each command is a get/set hybrid — if no update flags are passed, it GETs current settings; if flags are provided, it PATCHes. Enhanced-measurement additionally requires `--stream-id`.
- **Pattern divergence:** Not standard CRUD. Each subcommand is its own resource endpoint.

---

## Phase 3: Data Alpha Commands (WS-DA1, WS-DA2)

#### 10. WS-DA1: Funnel Reports (`ga reports funnel`)
- **Commands:** funnel (added to existing `reports_app`)
- **Files modified:** `src/ga_cli/commands/reports.py`; **Files created:** `tests/test_reports_funnel.py`
- **Notes:** Uses `get_data_alpha_client()`. Accepts `--config` JSON with funnel step definitions. Table output: Step Name, Active Users, Completion Rate, Drop-off Rate.
- **Important:** This is added to the **existing** reports command group, not a new Typer app.

#### 11. WS-DA2: Property Quotas (`ga properties quotas`)
- **Commands:** quotas (added to existing `properties_app`)
- **Files modified:** `src/ga_cli/commands/properties.py`, `tests/test_properties.py`
- **Notes:** Uses `get_data_alpha_client()`. Simple GET, table shows Quota Category / Consumed / Remaining / Limit.
- **Important:** Added to the **existing** properties command group.

---

## Registration in `main.py`

Add imports and `app.add_typer()` calls for all 8 new command groups (Phase 1 + Phase 2):

```
audiences, bigquery-links, channel-groups, calculated-metrics,
event-create-rules, event-edit-rules, access-bindings, annotations,
property-settings
```

WS-DA1 and WS-DA2 modify existing command groups — no new registration needed.

---

## Key Design Decisions

1. **Alpha client naming:** `get_admin_alpha_client()` / `get_data_alpha_client()` — clear distinction from beta
2. **`--config` JSON for complex resources:** Audiences, channel groups, event create/edit rules use JSON files (same pattern as `ga reports batch`)
3. **CLI flags for simple resources:** Calculated metrics, annotations, BigQuery links use direct flags
4. **Access bindings parent resolution:** Validate that exactly one of `--account-id` / `--property-id` is provided; raise `typer.BadParameter` if both or neither
5. **Event rules double-parent:** Both event create/edit rules need `--property-id` AND `--stream-id`, constructing parent as `properties/{pid}/dataStreams/{sid}`

---

## Suggested Execution Order

Build in dependency order, commit after each workstream passes tests:

1. **Phase 0** — Alpha clients (prerequisite for everything)
2. **WS-AA8** (Annotations) — simplest CRUD, good to validate alpha client works
3. **WS-AA4** (Calculated Metrics) — simple flag-based CRUD
4. **WS-AA2** (BigQuery Links) — flag-based CRUD with boolean toggles
5. **WS-AA1** (Audiences) — JSON config CRUD with archive instead of delete
6. **WS-AA3** (Channel Groups) — JSON config CRUD
7. **WS-AA5** (Event Create Rules) — double-parent pattern
8. **WS-AA6** (Event Edit Rules) — double-parent + reorder
9. **WS-AA7** (Access Bindings) — account-or-property parent
10. **WS-AA9** (Property Settings) — get/set hybrid pattern
11. **WS-DA1** (Funnel Reports) — data alpha, added to existing command
12. **WS-DA2** (Property Quotas) — data alpha, added to existing command

---

## Agent Guide Updates

**File:** `src/ga_cli/commands/agent_cmd.py`

After each workstream, update the agent guide incrementally:

1. **`_SECTION_OVERVIEW`** — Add new command groups to the Command Reference section
2. **`_SECTION_ADMIN`** — Add new admin command sections (audiences, bigquery-links, channel-groups, calculated-metrics, event-create-rules, event-edit-rules, access-bindings, annotations, property-settings). Follow the existing format: heading, code block with commands, bullet notes about constraints.
3. **`_SECTION_REPORTS`** — Add funnel report command
4. **`_SECTION_EXAMPLES`** — Optionally add example workflows using new commands

The admin section title should be updated to reflect the expanded coverage (currently says "Properties, Data Streams, Custom Dimensions, Custom Metrics & Key Events").

---

## Verification

After each workstream:
```bash
uv run pytest tests/test_<name>.py -v   # New tests pass
uv run ruff check src/ tests/           # No lint warnings
uv run pytest                           # Full suite, no regressions
```

After all workstreams:
- `ga --help` shows all new command groups
- Each new command group's `--help` shows correct subcommands
- Manual smoke test with a real GA4 property (if available)

---

## File Impact Summary

| Action | Count | Files |
|--------|-------|-------|
| **Modify** | 4 | `api/client.py`, `main.py`, `commands/reports.py`, `commands/properties.py` |
| **Create (commands)** | 9 | audiences, bigquery_links, channel_groups, calculated_metrics, event_create_rules, event_edit_rules, access_bindings, annotations, property_settings |
| **Create (tests)** | 10 | test_audiences, test_bigquery_links, test_channel_groups, test_calculated_metrics, test_event_create_rules, test_event_edit_rules, test_access_bindings, test_annotations, test_property_settings, test_reports_funnel |
| **Modify (tests)** | 1 | `tests/test_properties.py` |
| **Modify (agent guide)** | 1 | `commands/agent_cmd.py` (updated incrementally) |
| **Total new commands** | ~46 | See per-workstream counts above |
