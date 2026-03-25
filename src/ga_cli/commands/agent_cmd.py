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

_SECTION_ADMIN = r"""# Admin — Properties, Data Streams, Custom Dimensions, Custom Metrics & Key Events

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
