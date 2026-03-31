"""Agent guide command: prints a concise reference for AI agents using the GA CLI."""

from typing import Optional

import typer

agent_app = typer.Typer(name="agent", help="AI agent utilities", no_args_is_help=True)

# ---------------------------------------------------------------------------
# Section content
# ---------------------------------------------------------------------------

_SECTION_OVERVIEW = r"""# GA CLI — AI Agent Quick Reference

## Setup
```bash
ga auth login                                  # OAuth (interactive)
ga auth login --service-account /path/key.json # Service account (non-interactive)
ga config set default_account_id 123456789
ga config set default_property_id 987654321
ga config set output_format json               # Recommended for agents
```

## Global Flags
| Flag | Effect |
|------|--------|
| `-o json` | Machine-readable output |
| `-o compact` | Minimal output |
| `--quiet` / `-q` | Suppress info/warnings (errors still shown) |
| `--no-color` | Disable colored output |
| `--yes` / `-y` | Skip confirmation prompts |

## Resource Hierarchy
```
Account → Property → Data Stream (Web / Android / iOS)
```

## Command Reference

### Auth
```bash
ga auth login [--service-account PATH]
ga auth logout
ga auth status [-o json]
```

### Config
```bash
ga config get [KEY]
ga config set KEY VALUE
ga config unset KEY
ga config setup          # Interactive wizard
ga config reset
```
Keys: `default_account_id`, `default_property_id`, `output_format`

### Accounts
```bash
ga accounts list [-o json]
ga accounts get -a ACCOUNT_ID [-o json]
ga accounts update -a ACCOUNT_ID --name "Name"
```

### Account Summaries
```bash
ga account-summaries list [-o json]
```

### Properties
```bash
ga properties list [-a ACCOUNT_ID] [-o json]
ga properties get [-p PROPERTY_ID] [-o json]
ga properties create -a ACCOUNT_ID --name "Name" [--timezone TZ] [--currency CODE]
ga properties update -p PROPERTY_ID [--name NAME] [--timezone TZ] [--currency CODE] [--industry CAT]
ga properties delete -p PROPERTY_ID --yes
```

### Custom Dimensions
```bash
ga custom-dimensions list [-p PROPERTY_ID] [-o json]
ga custom-dimensions get -p PROPERTY_ID -d DIMENSION_ID [-o json]
ga custom-dimensions create -p PROPERTY_ID --parameter-name NAME --display-name NAME --scope EVENT|USER|ITEM
ga custom-dimensions update -p PROPERTY_ID -d DIMENSION_ID [--display-name NAME] [--description TEXT]
ga custom-dimensions archive -p PROPERTY_ID -d DIMENSION_ID --yes
```

### Custom Metrics
```bash
ga custom-metrics list [-p PROPERTY_ID] [-o json]
ga custom-metrics get -p PROPERTY_ID -m METRIC_ID [-o json]
ga custom-metrics create -p PROPERTY_ID --parameter-name NAME --display-name NAME --scope EVENT --measurement-unit UNIT
ga custom-metrics update -p PROPERTY_ID -m METRIC_ID [--display-name NAME] [--measurement-unit UNIT]
ga custom-metrics archive -p PROPERTY_ID -m METRIC_ID --yes
```
Measurement units: `STANDARD`, `CURRENCY`, `FEET`, `METERS`, `KILOMETERS`, `MILES`, `MILLISECONDS`, `SECONDS`, `MINUTES`, `HOURS`

### Key Events
```bash
ga key-events list [-p PROPERTY_ID] [-o json]
ga key-events get -p PROPERTY_ID -k KEY_EVENT_ID [-o json]
ga key-events create -p PROPERTY_ID --event-name NAME [--counting-method ONCE_PER_EVENT|ONCE_PER_SESSION]
ga key-events update -p PROPERTY_ID -k KEY_EVENT_ID --counting-method METHOD
ga key-events delete -p PROPERTY_ID -k KEY_EVENT_ID --yes
```

### Data Streams
```bash
ga data-streams list [-p PROPERTY_ID] [-o json]
ga data-streams get -p PROPERTY_ID -s STREAM_ID [-o json]
ga data-streams create -p PROPERTY_ID --display-name "Name" [--type TYPE] [--url URL] [--bundle-id ID]
ga data-streams update -p PROPERTY_ID -s STREAM_ID [--display-name NAME]
ga data-streams delete -p PROPERTY_ID -s STREAM_ID --yes
```
Types: `WEB_DATA_STREAM` (requires `--url`), `ANDROID_APP_DATA_STREAM` / `IOS_APP_DATA_STREAM` (require `--bundle-id`)

### Measurement Protocol Secrets
```bash
ga mp-secrets list -p PROPERTY_ID -s STREAM_ID [-o json]
ga mp-secrets get -p PROPERTY_ID -s STREAM_ID --secret-id SECRET_ID [-o json]
ga mp-secrets create -p PROPERTY_ID -s STREAM_ID --display-name "Name" [-o json]
ga mp-secrets update -p PROPERTY_ID -s STREAM_ID --secret-id SECRET_ID [--display-name NAME]
ga mp-secrets delete -p PROPERTY_ID -s STREAM_ID --secret-id SECRET_ID --yes
```
Requires both `--property-id` and `--stream-id`. The API auto-generates the secret value on create.

### Google Ads Links
```bash
ga google-ads-links list [-p PROPERTY_ID] [-o json]
ga google-ads-links create -p PROPERTY_ID --customer-id ID [--no-ads-personalization]
ga google-ads-links update -p PROPERTY_ID --link-id ID [--ads-personalization|--no-ads-personalization]
ga google-ads-links delete -p PROPERTY_ID --link-id ID --yes
```
No `get` method — use `list` to view links.

### Firebase Links
```bash
ga firebase-links list [-p PROPERTY_ID] [-o json]
ga firebase-links create -p PROPERTY_ID --project "projects/FIREBASE_PROJECT"
ga firebase-links delete -p PROPERTY_ID --link-id ID --yes
```
No `get` or `update` methods. A property can have at most one Firebase link.

### Access Bindings (alpha)
```bash
ga access-bindings list (-a ACCOUNT_ID | -p PROPERTY_ID) [-o json]
ga access-bindings get (-a ACCOUNT_ID | -p PROPERTY_ID) -b BINDING_ID [-o json]
ga access-bindings create (-a ACCOUNT_ID | -p PROPERTY_ID) --user EMAIL --roles viewer,editor [-o json]
ga access-bindings update (-a ACCOUNT_ID | -p PROPERTY_ID) -b BINDING_ID --roles viewer [-o json]
ga access-bindings delete (-a ACCOUNT_ID | -p PROPERTY_ID) -b BINDING_ID --yes
```
Requires either `--account-id` or `--property-id` (not both). Roles: viewer, analyst, editor, admin, no-cost-data, no-revenue-data.

### Annotations (alpha)
```bash
ga annotations list [-p PROPERTY_ID] [-o json]
ga annotations get -p PROPERTY_ID -a ANNOTATION_ID [-o json]
ga annotations create -p PROPERTY_ID --title TEXT --annotation-date YYYY-MM-DD [--description TEXT] [--color COLOR]
ga annotations update -p PROPERTY_ID -a ANNOTATION_ID [--title TEXT] [--description TEXT] [--color COLOR]
ga annotations delete -p PROPERTY_ID -a ANNOTATION_ID --yes
```
Mark dates on reports with contextual notes (e.g., launches, campaigns).

### Audiences (alpha)
```bash
ga audiences list [-p PROPERTY_ID] [-o json]
ga audiences get -p PROPERTY_ID -a AUDIENCE_ID [-o json]
ga audiences create -p PROPERTY_ID --config audience.json [-o json]
ga audiences update -p PROPERTY_ID -a AUDIENCE_ID --config update.json [-o json]
ga audiences archive -p PROPERTY_ID -a AUDIENCE_ID --yes
```
Create/update use `--config` JSON file (complex filter clauses). Only `displayName`, `description`, and `eventTrigger` can be updated. Uses `archive` instead of `delete`.

### BigQuery Links (alpha)
```bash
ga bigquery-links list [-p PROPERTY_ID] [-o json]
ga bigquery-links get -p PROPERTY_ID -l LINK_ID [-o json]
ga bigquery-links create -p PROPERTY_ID --project PROJECT --dataset-location LOC [--daily-export] [--streaming-export] [--export-streams IDS] [--excluded-events EVENTS]
ga bigquery-links update -p PROPERTY_ID -l LINK_ID [--daily-export|--no-daily-export] [--streaming-export|--no-streaming-export] [--export-streams IDS] [--excluded-events EVENTS]
ga bigquery-links delete -p PROPERTY_ID -l LINK_ID --yes
```
`--project` and `--dataset-location` are immutable (set at creation only). `--export-streams` accepts comma-separated stream IDs; `--excluded-events` accepts comma-separated event names.

### Channel Groups (alpha)
```bash
ga channel-groups list [-p PROPERTY_ID] [-o json]
ga channel-groups get -p PROPERTY_ID -g GROUP_ID [-o json]
ga channel-groups create -p PROPERTY_ID --config channel_group.json [-o json]
ga channel-groups update -p PROPERTY_ID -g GROUP_ID --config update.json [-o json]
ga channel-groups delete -p PROPERTY_ID -g GROUP_ID --yes
```
Create/update use `--config` JSON file (complex grouping rules with filter expressions). Max 50 rules per group.

### Calculated Metrics (alpha)
```bash
ga calculated-metrics list [-p PROPERTY_ID] [-o json]
ga calculated-metrics get -p PROPERTY_ID -m METRIC_ID [-o json]
ga calculated-metrics create -p PROPERTY_ID --calculated-metric-id ID --display-name NAME --formula FORMULA --metric-unit UNIT [--description TEXT]
ga calculated-metrics update -p PROPERTY_ID -m METRIC_ID [--display-name NAME] [--formula FORMULA] [--metric-unit UNIT] [--description TEXT]
ga calculated-metrics delete -p PROPERTY_ID -m METRIC_ID --yes
```
Metric units: `STANDARD`, `CURRENCY`, `FEET`, `METERS`, `KILOMETERS`, `MILES`, `MILLISECONDS`, `SECONDS`, `MINUTES`, `HOURS`

### Event Create Rules (alpha)
```bash
ga event-create-rules list -p PROPERTY_ID -s STREAM_ID [-o json]
ga event-create-rules get -p PROPERTY_ID -s STREAM_ID -r RULE_ID [-o json]
ga event-create-rules create -p PROPERTY_ID -s STREAM_ID --config rule.json [-o json]
ga event-create-rules update -p PROPERTY_ID -s STREAM_ID -r RULE_ID --config update.json [-o json]
ga event-create-rules delete -p PROPERTY_ID -s STREAM_ID -r RULE_ID --yes
```
Requires both `--property-id` and `--stream-id`. Create/update use `--config` JSON with `destinationEvent`, `eventConditions`, `sourceCopyParameters`, and `parameterMutations`.

### Event Edit Rules (alpha)
```bash
ga event-edit-rules list -p PROPERTY_ID -s STREAM_ID [-o json]
ga event-edit-rules get -p PROPERTY_ID -s STREAM_ID -r RULE_ID [-o json]
ga event-edit-rules create -p PROPERTY_ID -s STREAM_ID --config rule.json [-o json]
ga event-edit-rules update -p PROPERTY_ID -s STREAM_ID -r RULE_ID --config update.json [-o json]
ga event-edit-rules delete -p PROPERTY_ID -s STREAM_ID -r RULE_ID --yes
ga event-edit-rules reorder -p PROPERTY_ID -s STREAM_ID --rule-ids r1,r2,r3
```
Requires both `--property-id` and `--stream-id`. Create/update use `--config` JSON with `displayName`, `eventConditions`, and `parameterMutations`. Reorder requires all rule IDs in desired processing order.

### Reports
```bash
ga reports run [-p PROPERTY_ID] -m metrics -d dimensions --start-date DATE --end-date DATE [--limit N] [-o json]
ga reports pivot [-p PROPERTY_ID] -m metrics -d dimensions --pivot-field FIELD [--start-date DATE] [-o json]
ga reports check-compatibility [-p PROPERTY_ID] [-m metrics] [-d dimensions] [-o json]
ga reports metadata [-p PROPERTY_ID] [--type metrics|dimensions] [--search TEXT] [-o json]
ga reports realtime [-p PROPERTY_ID] [-m metrics] [-d dimensions] [--interval SECONDS]
```
Dates: `today`, `yesterday`, `7daysAgo`, `30daysAgo`, `90daysAgo`, or `YYYY-MM-DD`

### Upgrade
```bash
ga upgrade [--check] [--force]
```

### Completions
```bash
ga completions bash|zsh|fish
```

## Environment Variables
| Variable | Purpose |
|----------|---------|
| `GA_CLI_SERVICE_ACCOUNT` | Service account key path (non-interactive auth) |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP credential path (fallback) |
| `GA_CLI_CONFIG_DIR` | Override config directory |
| `NO_COLOR` | Disable colored output |

## Agent Workflow
Typical discover → act pattern:
```bash
# 1. Discover: find the right IDs
ACCT=$(ga accounts list -o json | jq -r '.[0].name' | grep -o '[0-9]*$')
ga config set default_account_id "$ACCT"

PROP=$(ga properties list -o json | jq -r '.[0].name' | grep -o '[0-9]*$')
ga config set default_property_id "$PROP"

# 2. Act: run reports, create resources, etc.
ga reports run -m sessions,users -d date --start-date 7daysAgo -o json
```

### Extracting IDs from JSON output
```bash
# Account ID from account name "accounts/123456789"
ga accounts list -o json | jq -r '.[].name' | grep -o '[0-9]*$'

# Property ID
ga properties list -o json | jq -r '.[].name' | grep -o '[0-9]*$'

# Stream ID
ga data-streams list -o json | jq -r '.[].name' | grep -o '[0-9]*$'
```

## Agent Best Practices
- **Set defaults first** — eliminates repetitive `--account-id` / `--property-id` flags from every command
- **Always use `-o json`** — structured output is easier to parse than tables
- **Use `check-compatibility` before complex reports** — avoids API errors from incompatible metric/dimension combos
- **Use `metadata` to discover available metrics/dimensions** — `ga reports metadata -p ID --search revenue -o json`
- **Parallelize independent operations** — run creates/deletes concurrently with `&` and `wait`
- **Avoid interactive commands** — skip `ga config setup` and `ga reports build`; use explicit flags instead

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Not authenticated" | No valid credentials | `ga auth login` |
| "Missing required option: property_id" | No `--property-id` and no default | `ga config set default_property_id ID` |
| "HttpError 403: …permission" | Account lacks GA4 access | Verify account/property IDs and permissions |
| "--url is required for WEB_DATA_STREAM" | Missing URL for web stream | Add `--url "https://…"` |
| "--bundle-id is required for …APP…" | Missing bundle ID for app stream | Add `--bundle-id "com.example.app"` |

Debugging steps: `ga auth status -o json` → `ga config get` → `ga accounts list -o json` → `ga properties list -o json`

Use `ga agent guide --section SECTION` for details on: `reports`, `admin`, `examples`
"""

_SECTION_REPORTS = r"""# Reports — Detailed Reference

## Common Metrics
| Metric | Description |
|--------|-------------|
| `sessions` | Total sessions |
| `users` | Total users |
| `newUsers` | New users |
| `screenPageViews` | Page/screen views |
| `eventCount` | Total events |
| `engagementRate` | Engaged sessions ratio |
| `averageSessionDuration` | Avg session duration (seconds) |
| `conversions` | Total conversions |
| `totalRevenue` | Total revenue |
| `activeUsers` | Active users (realtime only) |

## Common Dimensions
| Dimension | Description |
|-----------|-------------|
| `date` | Date (YYYYMMDD) |
| `country` | User country |
| `city` | User city |
| `deviceCategory` | desktop, mobile, tablet |
| `operatingSystem` | OS name |
| `browser` | Browser name |
| `sourceMedium` | Traffic source / medium |
| `sessionDefaultChannelGroup` | Channel grouping |
| `pagePath` | Page URL path |
| `pageTitle` | Page title |

## Pivot Reports
The `--pivot-field` must be one of the `--dimensions`. It becomes column headers in table output.
```bash
ga reports pivot -p 987654321 -m sessions,users -d country,deviceCategory --pivot-field deviceCategory --start-date 7daysAgo -o json
```

## Compatibility Check
Verify dimensions and metrics can be used together before running a report:
```bash
ga reports check-compatibility -p 987654321 -m sessions,conversions -d date,city -o json
```

## Real-Time Reports
Only support a subset of metrics (e.g., `activeUsers`). No date ranges.
```bash
ga reports realtime -p 987654321 -m activeUsers -d country -o json
ga reports realtime -p 987654321 --interval 10  # Poll every 10s
```

## Metadata
Browse available metrics and dimensions for a property:
```bash
ga reports metadata -p 987654321 -o json                    # All metrics and dimensions
ga reports metadata -p 987654321 --type metrics -o json     # Only metrics
ga reports metadata -p 987654321 --search page -o json      # Search by name
```

**Note**: `ga reports build` requires interactive input — avoid in automation. Use `ga reports run` instead.
"""

_SECTION_ADMIN = r"""# Admin — Properties, Streams, Dimensions, Metrics, Key Events, Links & More

## Properties
```bash
ga properties list [-a ACCOUNT_ID] [-o json]
ga properties get [-p PROPERTY_ID] [-o json]
ga properties create -a ACCOUNT_ID --name "Name" [--timezone TZ] [--currency CODE]
ga properties update -p PROPERTY_ID [--name NAME] [--timezone TZ] [--currency CODE] [--industry CAT]
ga properties delete -p PROPERTY_ID --yes
```
- Updatable fields: `displayName`, `timeZone`, `currencyCode`, `industryCategory`

## Custom Dimensions
```bash
ga custom-dimensions list [-p PROPERTY_ID] [-o json]
ga custom-dimensions get -p PROPERTY_ID -d DIMENSION_ID [-o json]
ga custom-dimensions create -p PROPERTY_ID --parameter-name NAME --display-name NAME --scope EVENT|USER|ITEM [--description TEXT]
ga custom-dimensions update -p PROPERTY_ID -d DIMENSION_ID [--display-name NAME] [--description TEXT]
ga custom-dimensions archive -p PROPERTY_ID -d DIMENSION_ID --yes
```
- Scopes: `EVENT`, `USER`, `ITEM`
- `parameterName` and `scope` cannot be changed after creation

## Custom Metrics
```bash
ga custom-metrics list [-p PROPERTY_ID] [-o json]
ga custom-metrics get -p PROPERTY_ID -m METRIC_ID [-o json]
ga custom-metrics create -p PROPERTY_ID --parameter-name NAME --display-name NAME --scope EVENT --measurement-unit UNIT
ga custom-metrics update -p PROPERTY_ID -m METRIC_ID [--display-name NAME] [--measurement-unit UNIT]
ga custom-metrics archive -p PROPERTY_ID -m METRIC_ID --yes
```
Measurement units: `STANDARD`, `CURRENCY`, `FEET`, `METERS`, `KILOMETERS`, `MILES`, `MILLISECONDS`, `SECONDS`, `MINUTES`, `HOURS`

## Key Events
Key events (formerly "conversions") mark significant user actions.
```bash
ga key-events list [-p PROPERTY_ID] [-o json]
ga key-events get -p PROPERTY_ID -k KEY_EVENT_ID [-o json]
ga key-events create -p PROPERTY_ID --event-name NAME [--counting-method ONCE_PER_EVENT|ONCE_PER_SESSION]
ga key-events update -p PROPERTY_ID -k KEY_EVENT_ID --counting-method METHOD
ga key-events delete -p PROPERTY_ID -k KEY_EVENT_ID --yes
```
Counting methods: `ONCE_PER_EVENT`, `ONCE_PER_SESSION`

## Data Streams
```bash
ga data-streams list [-p PROPERTY_ID] [-o json]
ga data-streams get -p PROPERTY_ID -s STREAM_ID [-o json]
ga data-streams create -p PROPERTY_ID --display-name "Name" [--type TYPE] [--url URL] [--bundle-id ID]
ga data-streams update -p PROPERTY_ID -s STREAM_ID [--display-name NAME]
ga data-streams delete -p PROPERTY_ID -s STREAM_ID --yes
```
| Type | Required Flag |
|------|--------------|
| `WEB_DATA_STREAM` (default) | `--url` |
| `ANDROID_APP_DATA_STREAM` | `--bundle-id` |
| `IOS_APP_DATA_STREAM` | `--bundle-id` |

## Measurement Protocol Secrets
Secrets for validating Measurement Protocol hits (server-side event collection).
```bash
ga mp-secrets list -p PROPERTY_ID -s STREAM_ID [-o json]
ga mp-secrets get -p PROPERTY_ID -s STREAM_ID --secret-id SECRET_ID [-o json]
ga mp-secrets create -p PROPERTY_ID -s STREAM_ID --display-name "Name" [-o json]
ga mp-secrets update -p PROPERTY_ID -s STREAM_ID --secret-id SECRET_ID [--display-name NAME]
ga mp-secrets delete -p PROPERTY_ID -s STREAM_ID --secret-id SECRET_ID --yes
```
- Nested under data streams: requires both `--property-id` and `--stream-id`
- Secret value is auto-generated by the API on create
- Only `displayName` can be updated

## Google Ads Links
```bash
ga google-ads-links list [-p PROPERTY_ID] [-o json]
ga google-ads-links create -p PROPERTY_ID --customer-id ID [--no-ads-personalization]
ga google-ads-links update -p PROPERTY_ID --link-id ID [--ads-personalization|--no-ads-personalization]
ga google-ads-links delete -p PROPERTY_ID --link-id ID --yes
```
- No `get` method — use `list` to see all links
- Only `adsPersonalizationEnabled` can be updated

## Firebase Links
```bash
ga firebase-links list [-p PROPERTY_ID] [-o json]
ga firebase-links create -p PROPERTY_ID --project "projects/FIREBASE_PROJECT"
ga firebase-links delete -p PROPERTY_ID --link-id ID --yes
```
- No `get` or `update` methods
- A property can have at most one Firebase link

## Access Bindings (alpha)
Manage user-role assignments at account or property level.
```bash
ga access-bindings list (-a ACCOUNT_ID | -p PROPERTY_ID) [-o json]
ga access-bindings get (-a ACCOUNT_ID | -p PROPERTY_ID) -b BINDING_ID [-o json]
ga access-bindings create (-a ACCOUNT_ID | -p PROPERTY_ID) --user EMAIL --roles viewer,editor [-o json]
ga access-bindings update (-a ACCOUNT_ID | -p PROPERTY_ID) -b BINDING_ID --roles viewer [-o json]
ga access-bindings delete (-a ACCOUNT_ID | -p PROPERTY_ID) -b BINDING_ID --yes
```
- Requires either `--account-id` (`-a`) or `--property-id` (`-p`), not both
- `--property-id` falls back to config default if not explicitly provided
- Valid roles: `viewer`, `analyst`, `editor`, `admin`, `no-cost-data`, `no-revenue-data`
- Short role names (e.g. `viewer`) are auto-prefixed to `predefinedRoles/viewer`
- Full role names (`predefinedRoles/viewer`) also accepted
- Uses v1alpha Admin API

## Annotations (alpha)
Annotations mark specific dates on GA4 reports with contextual notes.
```bash
ga annotations list [-p PROPERTY_ID] [-o json]
ga annotations get -p PROPERTY_ID -a ANNOTATION_ID [-o json]
ga annotations create -p PROPERTY_ID --title TEXT --annotation-date YYYY-MM-DD [--description TEXT] [--color COLOR]
ga annotations update -p PROPERTY_ID -a ANNOTATION_ID [--title TEXT] [--description TEXT] [--color COLOR]
ga annotations delete -p PROPERTY_ID -a ANNOTATION_ID --yes
```
- Updatable fields: `title`, `description`, `color`
- Uses v1alpha Admin API

## Audiences (alpha)
Define user segments for targeting and analysis.
```bash
ga audiences list [-p PROPERTY_ID] [-o json]
ga audiences get -p PROPERTY_ID -a AUDIENCE_ID [-o json]
ga audiences create -p PROPERTY_ID --config audience.json [-o json]
ga audiences update -p PROPERTY_ID -a AUDIENCE_ID --config update.json [-o json]
ga audiences archive -p PROPERTY_ID -a AUDIENCE_ID --yes
```
- Create/update use `--config` JSON file — audience filter clauses are deeply nested
- Only `displayName`, `description`, and `eventTrigger` can be updated after creation
- `membershipDurationDays` (max 540), `filterClauses`, and `exclusionDurationMode` are immutable
- Uses `archive` instead of `delete`
- Uses v1alpha Admin API

## BigQuery Links (alpha)
Link a GA4 property to a BigQuery project for data export.
```bash
ga bigquery-links list [-p PROPERTY_ID] [-o json]
ga bigquery-links get -p PROPERTY_ID -l LINK_ID [-o json]
ga bigquery-links create -p PROPERTY_ID --project PROJECT --dataset-location LOC [--daily-export] [--streaming-export] [--fresh-daily-export] [--include-advertising-id] [--export-streams IDS] [--excluded-events EVENTS]
ga bigquery-links update -p PROPERTY_ID -l LINK_ID [--daily-export|--no-daily-export] [--streaming-export|--no-streaming-export] [--fresh-daily-export|--no-fresh-daily-export] [--include-advertising-id|--no-include-advertising-id] [--export-streams IDS] [--excluded-events EVENTS]
ga bigquery-links delete -p PROPERTY_ID -l LINK_ID --yes
```
- `--project` and `--dataset-location` are immutable (set at creation only)
- `--export-streams` accepts comma-separated data stream IDs
- `--excluded-events` accepts comma-separated event names
- Uses v1alpha Admin API

## Channel Groups (alpha)
Custom channel groupings for categorizing traffic sources.
```bash
ga channel-groups list [-p PROPERTY_ID] [-o json]
ga channel-groups get -p PROPERTY_ID -g GROUP_ID [-o json]
ga channel-groups create -p PROPERTY_ID --config channel_group.json [-o json]
ga channel-groups update -p PROPERTY_ID -g GROUP_ID --config update.json [-o json]
ga channel-groups delete -p PROPERTY_ID -g GROUP_ID --yes
```
- Create/update use `--config` JSON file — grouping rules have nested filter expressions
- Maximum 50 grouping rules per channel group
- `displayName` (max 80 chars), `description`, `groupingRule`, and `primary` are updatable
- `systemDefined` channel groups (Google defaults) are read-only
- Uses v1alpha Admin API

## Calculated Metrics (alpha)
Derived metrics defined by a formula over existing metrics (e.g., revenue per user).
```bash
ga calculated-metrics list [-p PROPERTY_ID] [-o json]
ga calculated-metrics get -p PROPERTY_ID -m METRIC_ID [-o json]
ga calculated-metrics create -p PROPERTY_ID --calculated-metric-id ID --display-name NAME --formula FORMULA --metric-unit UNIT [--description TEXT]
ga calculated-metrics update -p PROPERTY_ID -m METRIC_ID [--display-name NAME] [--formula FORMULA] [--metric-unit UNIT] [--description TEXT]
ga calculated-metrics delete -p PROPERTY_ID -m METRIC_ID --yes
```
- Formula syntax uses `{{metricName}}` placeholders, e.g., `"{{totalRevenue}} / {{totalUsers}}"`
- Metric units: `STANDARD`, `CURRENCY`, `FEET`, `METERS`, `KILOMETERS`, `MILES`, `MILLISECONDS`, `SECONDS`, `MINUTES`, `HOURS`
- `calculatedMetricId` and `metricUnit` cannot be changed after creation
- Uses v1alpha Admin API

## Event Create Rules (alpha)
Create new events based on conditions matched against incoming events.
```bash
ga event-create-rules list -p PROPERTY_ID -s STREAM_ID [-o json]
ga event-create-rules get -p PROPERTY_ID -s STREAM_ID -r RULE_ID [-o json]
ga event-create-rules create -p PROPERTY_ID -s STREAM_ID --config rule.json [-o json]
ga event-create-rules update -p PROPERTY_ID -s STREAM_ID -r RULE_ID --config update.json [-o json]
ga event-create-rules delete -p PROPERTY_ID -s STREAM_ID -r RULE_ID --yes
```
- Requires both `--property-id` and `--stream-id` (nested under data streams)
- Create/update use `--config` JSON with: `destinationEvent`, `eventConditions` (1–10 conditions), `sourceCopyParameters`, `parameterMutations` (max 20)
- Condition comparison types: `EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `GREATER_THAN`, `LESS_THAN`, `REGULAR_EXPRESSION`, plus case-insensitive variants
- Uses v1alpha Admin API

## Event Edit Rules (alpha)
Modify existing events by mutating parameters based on matching conditions. Rules are applied in processing order.
```bash
ga event-edit-rules list -p PROPERTY_ID -s STREAM_ID [-o json]
ga event-edit-rules get -p PROPERTY_ID -s STREAM_ID -r RULE_ID [-o json]
ga event-edit-rules create -p PROPERTY_ID -s STREAM_ID --config rule.json [-o json]
ga event-edit-rules update -p PROPERTY_ID -s STREAM_ID -r RULE_ID --config update.json [-o json]
ga event-edit-rules delete -p PROPERTY_ID -s STREAM_ID -r RULE_ID --yes
ga event-edit-rules reorder -p PROPERTY_ID -s STREAM_ID --rule-ids r1,r2,r3
```
- Requires both `--property-id` and `--stream-id` (nested under data streams)
- Create/update use `--config` JSON with: `displayName` (max 255 chars), `eventConditions` (1–10 conditions), `parameterMutations` (max 20)
- Set `parameter` to `event_name` in a mutation to rename the event in place
- `reorder` requires all rule IDs in the desired processing order (comma-separated)
- `processingOrder` is output-only (set by the API, changed via `reorder`)
- Uses v1alpha Admin API
"""

_SECTION_EXAMPLES = r"""# Complete Examples

## Audit a GA4 Account
```bash
ACCOUNT_ID=123456789
ga accounts get -a $ACCOUNT_ID -o json
PROPERTIES=$(ga properties list -a $ACCOUNT_ID -o json)
echo "$PROPERTIES" | jq -r '.[].name' | while read -r prop; do
  PROP_ID=$(echo "$prop" | grep -o '[0-9]*$')
  ga data-streams list -p "$PROP_ID" -o json
done
```

## Traffic Report (Last 30 Days)
```bash
P=987654321
ga reports run -p $P -m sessions,users,engagementRate -d sessionDefaultChannelGroup --start-date 30daysAgo -o json
ga reports run -p $P -m sessions,users -d deviceCategory --start-date 30daysAgo -o json
ga reports run -p $P -m screenPageViews,users -d pagePath --start-date 30daysAgo --limit 20 -o json
```

## Create Property with Streams
```bash
PROP=$(ga properties create -a 123456789 --name "New Site" --timezone "Europe/Berlin" --currency "EUR" -o json)
PROP_ID=$(echo "$PROP" | jq -r '.name' | grep -o '[0-9]*$')
ga data-streams create -p "$PROP_ID" --display-name "Web" --url "https://example.com" &
ga data-streams create -p "$PROP_ID" --display-name "Android" --type ANDROID_APP_DATA_STREAM --bundle-id "com.example.app" &
wait
```
"""

_SECTIONS = {
    "reports": _SECTION_REPORTS,
    "admin": _SECTION_ADMIN,
    "examples": _SECTION_EXAMPLES,
}

VALID_SECTIONS = list(_SECTIONS.keys())


@agent_app.command("guide")
def guide(
    section: Optional[str] = typer.Option(
        None,
        "--section",
        "-s",
        help=f"Show a specific section: {', '.join(VALID_SECTIONS)}",
    ),
):
    """Print a reference guide for AI agents using the GA CLI."""
    if section is None:
        print(_SECTION_OVERVIEW)
        return

    key = section.lower().strip()
    if key not in _SECTIONS:
        print(
            f"Unknown section: '{section}'. "
            f"Valid sections: {', '.join(VALID_SECTIONS)}"
        )
        raise typer.Exit(code=0)

    print(_SECTIONS[key])
