# GA CLI

Command-line interface for Google Analytics 4.

Manage GA4 accounts, properties, data streams, and run reports — all from your terminal.

## Features

- **Authentication** — OAuth 2.0 (browser-based) and service account support
- **Account management** — List, inspect, update, delete accounts; view data sharing settings and change history
- **Account summaries** — Quick overview of all accounts and their properties
- **Property management** — List, create, inspect, update, delete properties; acknowledge user data collection; view API quotas
- **Data stream management** — List, create, inspect, update, and delete web, Android, and iOS data streams
- **Custom dimensions & metrics** — List, create, inspect, update, and archive custom definitions
- **Calculated metrics** — List, create, inspect, update, and delete calculated metrics
- **Key events** — List, create, inspect, update, and delete key events (conversions)
- **Audiences** — List, create, inspect, update, and archive audiences
- **Access bindings** — Manage user-role assignments at account and property level
- **Access reports** — Run data-access reports (who accessed what) at account or property level
- **Data retention** — View and update event and user data retention settings
- **Annotations** — Create, update, and delete reporting data annotations
- **Measurement Protocol secrets** — Manage MP API secrets per data stream
- **BigQuery links** — List, create, update, and delete BigQuery export links
- **Channel groups** — Manage custom channel groupings
- **Event create & edit rules** — Manage server-side event creation and modification rules
- **Firebase links** — List, create, and delete Firebase project links
- **Google Ads links** — List, create, update, and delete Google Ads account links
- **Property settings** — View and update attribution, Google Signals, and enhanced measurement settings
- **Reporting** — Run standard, pivot, batch, funnel, and real-time reports; check metric/dimension compatibility; browse metadata; build reports interactively
- **Flexible output** — Table (default), JSON, and compact output formats
- **Dry run** — Preview mutative requests (create, update, delete) without executing them
- **Self-update** — Check for and install updates via `ga upgrade`
- **Agent guide** — Built-in AI agent quick reference via `ga agent guide`
- **Schema introspection** — `ga --describe` outputs JSON Schema for all commands (agent/MCP-ready)
- **Shell completions** — Generate completion scripts for bash, zsh, and fish
- **Interactive setup** — Guided configuration wizard via `ga config setup`

## Installation

### From PyPI (recommended)

```bash
# pipx (recommended for CLI tools — isolated env)
pipx install google-analytics-cli

# uv
uv tool install google-analytics-cli

# pip
pip install google-analytics-cli
```

### Quick install (script)

```bash
curl -fsSL https://raw.githubusercontent.com/daidalytics/google-analytics-cli/master/install.sh | bash
```

### From GitHub

```bash
# With uv
uv pip install git+https://github.com/daidalytics/google-analytics-cli.git

# With pip
pip install git+https://github.com/daidalytics/google-analytics-cli.git
```

### From source

```bash
git clone https://github.com/daidalytics/google-analytics-cli.git
cd google-analytics-cli
uv sync
uv run ga --help
```

### One-off execution (no install)

```bash
uvx --from git+https://github.com/daidalytics/google-analytics-cli.git ga --help
```

## Quick Start

```bash
# 1. Authenticate
ga auth login

# 2. List your accounts
ga accounts list

# 3. List properties for an account
ga properties list --account-id 123456789

# 4. Run a report
ga reports run --property-id 987654321 \
  --metrics sessions,totalUsers \
  --dimensions date \
  --start-date 7daysAgo
```

## Setup

### 1. Create OAuth credentials

Create an OAuth 2.0 Client ID in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. Choose **Desktop app** as the application type
4. Download the JSON file

Make sure the following APIs are enabled in your GCP project:
- Google Analytics Admin API
- Google Analytics Data API

### 2. Configure client credentials

Copy the downloaded `client_secret.json` to the GA CLI config directory:

```bash
mkdir -p ~/.config/ga-cli
cp /path/to/client_secret.json ~/.config/ga-cli/client_secret.json
```

Alternatively, set environment variables:

```bash
export GA_CLI_CLIENT_ID="your-client-id"
export GA_CLI_CLIENT_SECRET="your-client-secret"
```

### 3. Authenticate

```bash
ga auth login
```

This opens your browser for Google OAuth consent and stores the token locally at `~/.config/ga-cli/credentials.json`.

#### Service account (alternative)

```bash
ga auth login --service-account /path/to/key.json
```

Or set an environment variable:

```bash
export GA_CLI_SERVICE_ACCOUNT="/path/to/key.json"
```

## Command Reference

| Command | Subcommands | Description |
|---------|-------------|-------------|
| `ga auth` | `setup`, `login`, `logout`, `status` | Manage authentication |
| `ga config` | `setup`, `get`, `set`, `unset`, `path`, `reset` | Manage CLI configuration |
| `ga accounts` | `list`, `get`, `update`, `delete`, `get-data-sharing`, `change-history` | Manage GA4 accounts |
| `ga account-summaries` | `list` | Quick overview of all accounts and properties |
| `ga properties` | `list`, `get`, `create`, `update`, `delete`, `acknowledge-udc`, `quotas` | Manage GA4 properties |
| `ga custom-dimensions` | `list`, `get`, `create`, `update`, `archive` | Manage custom dimensions |
| `ga custom-metrics` | `list`, `get`, `create`, `update`, `archive` | Manage custom metrics |
| `ga calculated-metrics` | `list`, `get`, `create`, `update`, `delete` | Manage calculated metrics |
| `ga data-streams` | `list`, `get`, `create`, `update`, `delete` | Manage data streams |
| `ga key-events` | `list`, `get`, `create`, `update`, `delete` | Manage key events (conversions) |
| `ga audiences` | `list`, `get`, `create`, `update`, `archive` | Manage audiences |
| `ga access-bindings` | `list`, `get`, `create`, `update`, `delete` | Manage user-role assignments |
| `ga access-reports` | `run-account`, `run-property` | Run data-access reports |
| `ga data-retention` | `get`, `update` | View and update data retention settings |
| `ga annotations` | `list`, `get`, `create`, `update`, `delete` | Manage reporting annotations |
| `ga mp-secrets` | `list`, `get`, `create`, `update`, `delete` | Manage Measurement Protocol secrets |
| `ga bigquery-links` | `list`, `get`, `create`, `update`, `delete` | Manage BigQuery export links |
| `ga channel-groups` | `list`, `get`, `create`, `update`, `delete` | Manage custom channel groups |
| `ga event-create-rules` | `list`, `get`, `create`, `update`, `delete` | Manage event creation rules |
| `ga event-edit-rules` | `list`, `get`, `create`, `update`, `delete`, `reorder` | Manage event editing rules |
| `ga firebase-links` | `list`, `create`, `delete` | Manage Firebase links |
| `ga google-ads-links` | `list`, `create`, `update`, `delete` | Manage Google Ads links |
| `ga property-settings` | `attribution`, `google-signals`, `enhanced-measurement` | View and update property settings |
| `ga reports` | `run`, `pivot`, `batch`, `funnel`, `check-compatibility`, `metadata`, `realtime`, `build` | Run and build reports |
| `ga agent` | `guide` | AI agent quick reference |
| `ga upgrade` | `--check`, `--force` | Check for and install updates |
| `ga completions` | `bash`, `zsh`, `fish` | Generate shell completion scripts |

Use `ga <command> --help` for detailed usage of any command, or `ga --describe` for the full CLI schema as JSON.

### Output formats

All read commands support `--output` (`-o`) to control output format:

```bash
ga accounts list --output json      # JSON output
ga accounts list --output table     # Table output (default)
ga accounts list --output compact   # Minimal ID + name output
```

## Global Options

```
--help, -h      Show help
--version, -v   Show version
--quiet, -q     Suppress non-essential output
--no-color      Disable colored output
--describe      Show full CLI schema as JSON (for agents and tooling)
```

## Shell Completions

```bash
ga completions bash > ~/.bash_completion.d/ga
ga completions zsh > ~/.zsh/completions/_ga
ga completions fish > ~/.config/fish/completions/ga.fish
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GA_CLI_CLIENT_ID` | OAuth client ID (alternative to client_secret.json) |
| `GA_CLI_CLIENT_SECRET` | OAuth client secret (alternative to client_secret.json) |
| `GA_CLI_SERVICE_ACCOUNT` | Path to service account key file |
| `GOOGLE_APPLICATION_CREDENTIALS` | Standard GCP credential path (fallback) |
| `GA_CLI_CONFIG_DIR` | Override config directory |
| `NO_COLOR` | Disable colored output |

## CI/CD Integration

```yaml
jobs:
  ga-report:
    runs-on: ubuntu-latest
    steps:
      - name: Install GA CLI
        run: pip install google-analytics-cli

      - name: Export daily report
        run: |
          echo '${{ secrets.GA_SERVICE_ACCOUNT_KEY }}' > /tmp/sa-key.json
          ga auth login --service-account /tmp/sa-key.json
          ga reports run -p ${{ vars.GA_PROPERTY_ID }} \
            --metrics sessions,users --dimensions date \
            --start-date 7daysAgo -o json > report.json
          rm /tmp/sa-key.json
```

## Privacy

GA CLI stores authentication credentials locally on your machine. No data is sent to any third party — all communication is directly between your machine and Google's APIs.

## Development

```bash
# Install with dev dependencies
uv sync

# Run the CLI
uv run ga --help

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/
```

## License

MIT
