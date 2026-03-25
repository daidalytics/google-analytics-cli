"""Agent guide command: prints a comprehensive guide for AI agents using the GA CLI."""

import typer

agent_app = typer.Typer(name="agent", help="AI agent utilities", no_args_is_help=True)

AGENT_GUIDE = r"""# AI Agent Guide to GA CLI

## Table of Contents
1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [Configuration Management](#configuration-management)
4. [Accounts & Properties](#accounts--properties)
5. [Data Streams](#data-streams)
6. [Reports](#reports)
7. [Upgrade & Maintenance](#upgrade--maintenance)
8. [Shell Completions](#shell-completions)
9. [Environment Variables](#environment-variables)
10. [Performance Optimization](#performance-optimization)
11. [Troubleshooting](#troubleshooting)
12. [Complete Examples](#complete-examples)

---

## Quick Start

### Initial Setup
```bash
# Authenticate
ga auth login

# List accounts to get IDs
ga accounts list

# List properties for an account
ga properties list --account-id 123456789

# Set defaults to avoid repeating IDs
ga config set default_account_id 123456789
ga config set default_property_id 987654321
ga config set output_format json  # Recommended for AI agents
```

### Global Flags
```bash
--quiet, -q     # Suppress non-essential output (info, warnings, success messages)
--no-color      # Disable colored output (useful for log parsing)
```

**AI Agent Tip**: Use `--quiet` to reduce noise when parsing command output programmatically. Errors are never suppressed.

### Verify Configuration
```bash
ga config get
```

---

## Core Concepts

### Resource Hierarchy
```
Account (e.g., 123456789)
└── Property (e.g., 987654321)
    └── Data Stream (e.g., 1234567890)
        ├── Web (WEB_DATA_STREAM)
        ├── Android (ANDROID_APP_DATA_STREAM)
        └── iOS (IOS_APP_DATA_STREAM)
```

### ID Types
- **Account ID**: Numeric (e.g., `123456789`)
- **Property ID**: Numeric (e.g., `987654321`)
- **Data Stream ID**: Numeric (e.g., `1234567890`)

### Output Formats
```bash
# Table (default, human-readable)
ga accounts list

# JSON (for programmatic parsing)
ga accounts list -o json

# Compact (minimal output)
ga accounts list -o compact
```

### Authentication Methods
```bash
# OAuth 2.0 (interactive, browser-based)
ga auth login

# Service account (non-interactive, for automation)
ga auth login --service-account /path/to/key.json

# Check current auth status
ga auth status
```

---

## Configuration Management

### Config Keys
| Key | Description | Example |
|-----|-------------|---------|
| `default_account_id` | Default GA4 Account ID | `123456789` |
| `default_property_id` | Default GA4 Property ID | `987654321` |
| `output_format` | Default output format | `json`, `table`, `compact` |

### Essential Commands
```bash
# View all config
ga config get

# Set defaults (recommended for AI agents)
ga config set default_account_id 123456789
ga config set default_property_id 987654321
ga config set output_format json

# Get specific config value
ga config get default_property_id

# Remove a config value
ga config unset default_property_id

# Interactive setup wizard
ga config setup

# Reset everything
ga config reset
```

### Best Practice for AI Agents
**Always set defaults at the start of your session** to avoid repetitive `--account-id` and `--property-id` flags on every command.

```bash
ga config set default_account_id 123456789
ga config set default_property_id 987654321
ga config set output_format json
```

With defaults set, commands simplify:
```bash
# Without defaults
ga properties list --account-id 123456789
ga reports run --property-id 987654321 --metrics sessions

# With defaults
ga properties list
ga reports run --metrics sessions
```

---

## Accounts & Properties

### Accounts

#### List All Accounts
```bash
ga accounts list -o json
```

#### Get Account Details
```bash
ga accounts get --account-id 123456789 -o json
```

#### Update Account Display Name
```bash
ga accounts update --account-id 123456789 --name "New Account Name" -o json
```

### Properties

#### List Properties for an Account
```bash
ga properties list --account-id 123456789 -o json
# Or with defaults set:
ga properties list -o json
```

#### Get Property Details
```bash
ga properties get --property-id 987654321 -o json
```

#### Create a Property
```bash
ga properties create \
  --account-id 123456789 \
  --name "My New Property" \
  --timezone "America/New_York" \
  --currency "USD"
```

#### Delete a Property
```bash
# With confirmation prompt
ga properties delete --property-id 987654321

# Skip confirmation (for automation)
ga properties delete --property-id 987654321 --yes
```

---

## Data Streams

### Stream Types
| Type | Flag Value | Required Extra Flag |
|------|-----------|-------------------|
| Web | `WEB_DATA_STREAM` (default) | `--url` |
| Android | `ANDROID_APP_DATA_STREAM` | `--bundle-id` |
| iOS | `IOS_APP_DATA_STREAM` | `--bundle-id` |

### List Data Streams
```bash
ga data-streams list --property-id 987654321 -o json
```

### Get Data Stream Details
```bash
ga data-streams get --property-id 987654321 --stream-id 1234567890 -o json
```

### Create Data Streams

#### Web Stream
```bash
ga data-streams create \
  --property-id 987654321 \
  --display-name "Company Website" \
  --type WEB_DATA_STREAM \
  --url "https://example.com"
```

#### Android App Stream
```bash
ga data-streams create \
  --property-id 987654321 \
  --display-name "Android App" \
  --type ANDROID_APP_DATA_STREAM \
  --bundle-id "com.example.app"
```

#### iOS App Stream
```bash
ga data-streams create \
  --property-id 987654321 \
  --display-name "iOS App" \
  --type IOS_APP_DATA_STREAM \
  --bundle-id "com.example.app"
```

### Delete a Data Stream
```bash
ga data-streams delete --property-id 987654321 --stream-id 1234567890 --yes
```

---

## Reports

### Run a Custom Report
```bash
ga reports run \
  --property-id 987654321 \
  --metrics sessions,users,screenPageViews \
  --dimensions date,country \
  --start-date 7daysAgo \
  --end-date today \
  --limit 100 \
  -o json
```

### Common Metrics
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

### Common Dimensions
| Dimension | Description |
|-----------|-------------|
| `date` | Date (YYYYMMDD format) |
| `country` | User country |
| `city` | User city |
| `deviceCategory` | desktop, mobile, tablet |
| `operatingSystem` | OS name |
| `browser` | Browser name |
| `sourceMedium` | Traffic source / medium |
| `sessionDefaultChannelGroup` | Channel grouping |
| `pagePath` | Page URL path |
| `pageTitle` | Page title |

### Date Formats
- Relative: `today`, `yesterday`, `7daysAgo`, `30daysAgo`, `90daysAgo`
- Absolute: `2024-01-01` (YYYY-MM-DD)

### Real-Time Reports
```bash
# Single snapshot
ga reports realtime --property-id 987654321 -o json

# With dimensions
ga reports realtime \
  --property-id 987654321 \
  --metrics activeUsers \
  --dimensions country

# Live polling (refresh every 10 seconds)
ga reports realtime \
  --property-id 987654321 \
  --metrics activeUsers \
  --interval 10
```

**Note**: Real-time reports only support a subset of metrics (e.g., `activeUsers`) and dimensions. They do not support date ranges.

### Interactive Report Builder
```bash
# Opens an interactive wizard to select metrics, dimensions, and date range
ga reports build --property-id 987654321
```

**AI Agent Tip**: Prefer `ga reports run` with explicit parameters over `ga reports build` — the builder requires interactive input which agents cannot provide.

---

## Upgrade & Maintenance

### Check for Updates
```bash
ga upgrade --check
```

### Install Latest Version
```bash
ga upgrade
```

### Force Reinstall
```bash
ga upgrade --force
```

**Note**: `ga upgrade` automatically detects your package manager (pipx, uv, or pip) and uses the appropriate upgrade command.

---

## Shell Completions

Generate completion scripts for your shell. Useful for agents that set up development environments.

```bash
# Bash
ga completions bash > ~/.bash_completion.d/ga

# Zsh
ga completions zsh > ~/.zsh/completions/_ga

# Fish
ga completions fish > ~/.config/fish/completions/ga.fish
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GA_CLI_SERVICE_ACCOUNT` | Path to service account key file |
| `GOOGLE_APPLICATION_CREDENTIALS` | Standard GCP credential path (fallback) |
| `GA_CLI_CONFIG_DIR` | Override config directory location |
| `GA_CLI_CLIENT_ID` | OAuth client ID (dev override) |
| `GA_CLI_CLIENT_SECRET` | OAuth client secret (dev override) |
| `NO_COLOR` | Disable colored output (standard convention) |

**AI Agent Tip**: For non-interactive automation, use `GA_CLI_SERVICE_ACCOUNT` or `GOOGLE_APPLICATION_CREDENTIALS` to authenticate without browser-based OAuth.

---

## Performance Optimization

### 1. Set Defaults First
```bash
ga config set default_account_id 123456789
ga config set default_property_id 987654321
ga config set output_format json
```
**Impact**: Eliminates repetitive flags from every command.

### 2. Use JSON Output for Parsing
```bash
# Parse with jq
ga accounts list -o json | jq -r '.[].name'
ga properties list -o json | jq -r '.[] | .name + " " + .displayName'
```

### 3. Parallel Operations
When operations are independent, run them in parallel:
```bash
# Good: parallel execution
ga data-streams create --display-name "Web" --url "https://a.com" &
ga data-streams create --display-name "Web 2" --url "https://b.com" &
wait

# Bad: sequential when not needed
ga data-streams create --display-name "Web" --url "https://a.com"
ga data-streams create --display-name "Web 2" --url "https://b.com"
```

### 4. Skip Confirmation Prompts
Use `--yes` (`-y`) for delete operations in automated workflows:
```bash
ga properties delete --property-id 987654321 --yes
ga data-streams delete --property-id 987654321 --stream-id 123 --yes
```

---

## Troubleshooting

### Common Errors and Solutions

#### 1. "Not authenticated"
```bash
# Check current status
ga auth status

# Re-authenticate
ga auth login
```

#### 2. "Missing required option: property_id"
**Problem**: No `--property-id` flag and no default set.
**Solution**: Either pass the flag or set a default:
```bash
ga config set default_property_id 987654321
```

#### 3. "HttpError 403: The caller does not have permission"
**Problem**: The authenticated account lacks access to the requested resource.
**Solution**: Verify you have the correct account/property IDs and that your Google account has GA4 access.

#### 4. "--url is required for WEB_DATA_STREAM type"
**Problem**: Creating a web stream without specifying the URL.
**Solution**: Add the `--url` flag:
```bash
ga data-streams create --display-name "Site" --url "https://example.com"
```

#### 5. "--bundle-id is required for ANDROID_APP_DATA_STREAM type"
**Problem**: Creating an app stream without specifying the bundle ID.
**Solution**: Add the `--bundle-id` flag:
```bash
ga data-streams create --display-name "App" --type ANDROID_APP_DATA_STREAM --bundle-id "com.example.app"
```

### Debugging Workflow
```bash
# 1. Verify authentication
ga auth status -o json

# 2. Verify configuration
ga config get

# 3. List available resources
ga accounts list -o json
ga properties list -o json
ga data-streams list -o json

# 4. Inspect a specific resource
ga properties get --property-id 987654321 -o json
```

---

## Complete Examples

### Example 1: Audit a GA4 Account

```bash
#!/bin/bash
# Audit all properties and data streams for an account

ACCOUNT_ID=123456789

echo "=== Account Details ==="
ga accounts get --account-id $ACCOUNT_ID -o json

echo "=== Properties ==="
PROPERTIES=$(ga properties list --account-id $ACCOUNT_ID -o json)
echo "$PROPERTIES" | jq -r '.[].name'

echo "=== Data Streams per Property ==="
echo "$PROPERTIES" | jq -r '.[].name' | while read -r prop_name; do
  PROP_ID=$(echo "$prop_name" | grep -o '[0-9]*$')
  echo "--- Property $PROP_ID ---"
  ga data-streams list --property-id "$PROP_ID" -o json
done
```

### Example 2: Quick Traffic Report

```bash
#!/bin/bash
# Get a traffic overview for the last 30 days

PROPERTY_ID=987654321

echo "=== Traffic by Channel ==="
ga reports run \
  --property-id $PROPERTY_ID \
  --metrics sessions,users,engagementRate \
  --dimensions sessionDefaultChannelGroup \
  --start-date 30daysAgo \
  -o json

echo "=== Traffic by Device ==="
ga reports run \
  --property-id $PROPERTY_ID \
  --metrics sessions,users \
  --dimensions deviceCategory \
  --start-date 30daysAgo \
  -o json

echo "=== Top Pages ==="
ga reports run \
  --property-id $PROPERTY_ID \
  --metrics screenPageViews,users \
  --dimensions pagePath \
  --start-date 30daysAgo \
  --limit 20 \
  -o json
```

### Example 3: Set Up a New Property with Data Streams

```bash
#!/bin/bash
# Create a new property and add web + app streams

ACCOUNT_ID=123456789

# Create the property
PROP=$(ga properties create \
  --account-id $ACCOUNT_ID \
  --name "New Website" \
  --timezone "Europe/Berlin" \
  --currency "EUR" \
  -o json)

PROP_ID=$(echo "$PROP" | jq -r '.name' | grep -o '[0-9]*$')
echo "Created property: $PROP_ID"

# Create streams in parallel
ga data-streams create \
  --property-id "$PROP_ID" \
  --display-name "Website" \
  --type WEB_DATA_STREAM \
  --url "https://example.com" &

ga data-streams create \
  --property-id "$PROP_ID" \
  --display-name "Android App" \
  --type ANDROID_APP_DATA_STREAM \
  --bundle-id "com.example.app" &

ga data-streams create \
  --property-id "$PROP_ID" \
  --display-name "iOS App" \
  --type IOS_APP_DATA_STREAM \
  --bundle-id "com.example.app" &

wait

echo "=== All Streams ==="
ga data-streams list --property-id "$PROP_ID" -o json
```

---

## Quick Reference Card

### Setup
```bash
ga auth login
ga config set default_account_id ID
ga config set default_property_id ID
ga config set output_format json
```

### Accounts
```bash
ga accounts list -o json
ga accounts get --account-id ID -o json
ga accounts update --account-id ID --name "New Name"
```

### Properties
```bash
ga properties list [-a ACCOUNT_ID] -o json
ga properties get [-p PROPERTY_ID] -o json
ga properties create -a ACCOUNT_ID --name "Name" [--timezone TZ] [--currency CODE]
ga properties delete -p PROPERTY_ID --yes
```

### Data Streams
```bash
ga data-streams list [-p PROPERTY_ID] -o json
ga data-streams get -p PROPERTY_ID -s STREAM_ID -o json
ga data-streams create -p PROPERTY_ID --display-name "Name" [--type TYPE] [--url URL] [--bundle-id ID]
ga data-streams delete -p PROPERTY_ID -s STREAM_ID --yes
```

### Reports
```bash
ga reports run [-p PROPERTY_ID] -m metrics -d dimensions --start-date DATE --end-date DATE --limit N -o json
ga reports realtime [-p PROPERTY_ID] -m metrics [-d dimensions] [--interval SECONDS]
ga reports build [-p PROPERTY_ID]  # Interactive — avoid in automation
```

### Upgrade
```bash
ga upgrade --check   # Check for updates
ga upgrade           # Install latest version
ga upgrade --force   # Force reinstall
```

### Completions
```bash
ga completions bash
ga completions zsh
ga completions fish
```

### Flag Shortcuts
| Long | Short | Description |
|------|-------|-------------|
| `--account-id` | `-a` | Account ID |
| `--property-id` | `-p` | Property ID |
| `--stream-id` | `-s` | Data Stream ID |
| `--output` | `-o` | Output format |
| `--metrics` | `-m` | Report metrics |
| `--dimensions` | `-d` | Report dimensions |
| `--yes` | `-y` | Skip confirmation |
| `--quiet` | `-q` | Suppress non-essential output |
| `--no-color` | | Disable colored output |
"""


@agent_app.command("guide")
def guide():
    """Print a comprehensive guide for AI agents using the GA CLI."""
    print(AGENT_GUIDE)
