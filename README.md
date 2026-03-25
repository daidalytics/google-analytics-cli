# GA CLI

Command-line interface for Google Analytics 4.

Manage GA4 accounts, properties, data streams, and run reports — all from your terminal.

## Features

- **Authentication** — OAuth 2.0 (browser-based) and service account support
- **Account management** — List, inspect, and update GA4 accounts
- **Property management** — List, create, inspect, update, and delete GA4 properties
- **Data stream management** — List, create, inspect, update, and delete web, Android, and iOS data streams
- **Custom dimensions & metrics** — List, create, update, and archive custom definitions
- **Key events** — List, create, update, and delete key events (conversions)
- **Reporting** — Run custom reports, pivot reports, real-time reports with live polling, check compatibility, and build reports interactively
- **Flexible output** — Table (default), JSON, and compact output formats
- **Self-update** — Check for and install updates via `ga upgrade`
- **Shell completions** — Generate completion scripts for bash, zsh, and fish
- **Interactive setup** — Guided configuration wizard via `ga config setup`

## Installation

### Quick install

```bash
curl -fsSL https://raw.githubusercontent.com/gunnargriese/ga-cli/master/install.sh | bash
```

### From GitHub

```bash
# With uv
uv pip install git+https://github.com/gunnargriese/ga-cli.git

# With pip
pip install git+https://github.com/gunnargriese/ga-cli.git
```

### From source

```bash
git clone https://github.com/gunnargriese/ga-cli.git
cd ga-cli
uv sync
uv run ga --help
```

### One-off execution (no install)

```bash
uvx --from git+https://github.com/gunnargriese/ga-cli.git ga --help
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
| `ga auth` | `login`, `logout`, `status` | Manage authentication |
| `ga config` | `setup`, `get`, `set`, `unset`, `path`, `reset` | Manage CLI configuration |
| `ga accounts` | `list`, `get`, `update` | List, inspect, and update GA4 accounts |
| `ga account-summaries` | `list` | Quick overview of all accounts and properties |
| `ga properties` | `list`, `get`, `create`, `update`, `delete` | Manage GA4 properties |
| `ga custom-dimensions` | `list`, `get`, `create`, `update`, `archive` | Manage custom dimensions |
| `ga custom-metrics` | `list`, `get`, `create`, `update`, `archive` | Manage custom metrics |
| `ga data-streams` | `list`, `get`, `create`, `update`, `delete` | Manage data streams |
| `ga key-events` | `list`, `get`, `create`, `update`, `delete` | Manage key events (conversions) |
| `ga reports` | `run`, `pivot`, `check-compatibility`, `metadata`, `realtime`, `build` | Run and build reports |
| `ga upgrade` | `--check`, `--force` | Check for and install updates |
| `ga completions` | `bash`, `zsh`, `fish` | Generate shell completion scripts |

Use `ga <command> --help` for detailed usage of any command.

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
| `GA_CLI_SERVICE_ACCOUNT` | Path to service account key file |
| `GOOGLE_APPLICATION_CREDENTIALS` | Standard GCP credential path (fallback) |
| `GA_CLI_CONFIG_DIR` | Override config directory |
| `GA_CLI_CLIENT_ID` | OAuth client ID (dev override) |
| `GA_CLI_CLIENT_SECRET` | OAuth client secret (dev override) |
| `NO_COLOR` | Disable colored output |

## CI/CD Integration

```yaml
jobs:
  ga-report:
    runs-on: ubuntu-latest
    steps:
      - name: Install GA CLI
        run: pip install ga-cli

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
