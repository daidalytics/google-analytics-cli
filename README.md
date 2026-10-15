# GA CLI

Command-line interface for Google Analytics 4.

Manage GA4 accounts, properties, data streams, and run reports — all from your terminal.

Read an introductory blog post on the GA CLI on [gunnargriese.com](https://gunnargriese.com/posts/google-analytics-cli/).

## Use with AI agents

GA CLI ships an agent skill, `ga-cli`, that teaches coding agents to run reports and manage GA4 through the CLI.

```bash
# Run without installing (needs uv)
uvx google-analytics-cli --help

# Add the skill to Claude Code, Cursor, Codex, …
npx skills add daidalytics/google-analytics-cli
```

```
# Or as a Claude Code plugin
/plugin marketplace add daidalytics/google-analytics-cli
/plugin install google-analytics-cli@daidalytics
```

## Features

### Authentication

- **OAuth 2.0** — Browser-based login flow with automatic token refresh
- **Service accounts** — Key-file authentication for CI/CD and server environments
- **Named profiles** — One flag (`--profile`, or `GA_CLI_PROFILE`) switches client identity and default property together, for working across several clients' GA4 setups
- **gcloud ADC fallback** — Uses gcloud Application Default Credentials when nothing else is configured, including keyless Workload Identity Federation in CI

### [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)

- **Reporting** — Run standard, pivot, batch, funnel, and real-time reports
- **Chat** — Ask questions in plain language via `ga reports chat` (built on the `v1alpha` API)
- **Report builder** — Interactive metric/dimension selection via `ga reports build`
- **Compatibility checks** — Validate metric/dimension combinations before running reports
- **Metadata** — Browse and search available metrics and dimensions
- **Audience exports** — Export the users in an audience (e.g. device and user IDs) as a snapshot, then page through them

### [GA4 Admin API](https://developers.google.com/analytics/devguides/config/admin/v1)

- **Accounts** — List, inspect, update, delete accounts; view data sharing settings and change history
- **Account summaries** — Quick overview of all accounts and their properties
- **Properties** — List, create, inspect, update, delete properties; acknowledge user data collection; view API quotas
- **Data streams** — List, create, inspect, update, and delete web, Android, and iOS data streams
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
- **Property settings** — View and update attribution and Google Signals settings
- **Enhanced measurement** — View and update enhanced measurement settings per data stream

### Interactive usage

- **Flexible output** — Table (default), JSON, and compact output formats
- **Shell completions** — Generate completion scripts for bash, zsh, and fish
- **Interactive setup** — Guided configuration wizard via `ga config setup`
- **Self-update** — Check for and install updates via `ga upgrade`

### Automation & agent integration

- **Schema introspection** — `ga --describe` outputs JSON Schema for all commands (MCP/agent-ready)
- **Dry run** — Preview mutative requests (create, update, delete) without executing them
- **Structured errors** — Categorized exit codes and JSON error output for programmatic handling
- **Agent guide** — Built-in AI agent quick reference via `ga agent guide`

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

With [uv](https://docs.astral.sh/uv/), swap `ga` for `uvx google-analytics-cli` in any command:

```bash
uvx google-analytics-cli accounts list
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

### Multiple clients: named profiles

A profile bundles one client's credentials with that client's defaults (default property, default account, output format), so switching profile switches identity and target property together. Profiles share one OAuth client (`client_secret.json`), and each is created by the first `auth login` or `config set` that names it.

```bash
# Log in once per profile (OAuth or service account)
ga --profile client-a auth login
ga --profile client-b auth login --service-account /path/to/client-b-key.json

# Give each profile its own default property
ga --profile client-a config set default_property_id 123456789
ga --profile client-b config set default_property_id 987654321

# Pick a profile per command...
ga --profile client-a reports run --metrics sessions --dimensions date

# ...or per shell session
export GA_CLI_PROFILE=client-b
ga reports run --metrics sessions --dimensions date

# See every profile, its auth method, its default property, and which one is active
ga profiles list

# Remove a profile's stored credentials and config (a service account key file is left alone)
ga profiles delete old-client
```

- **`--profile` goes right after `ga`**, before the command group: `ga --profile client-a reports run …`. `ga reports run --profile client-a` fails with "No such option". `--profile` overrides `GA_CLI_PROFILE`.
- **Nothing is saved as an "active profile".** Selection lasts for one command (`--profile`) or one shell (`GA_CLI_PROFILE`), so a new shell always starts on the default profile unless your shell config exports `GA_CLI_PROFILE`.
- **A named profile never falls back.** It uses only its own stored credentials and ignores `GA_CLI_SERVICE_ACCOUNT`, `GOOGLE_APPLICATION_CREDENTIALS`, the default profile, and gcloud ADC. An unknown profile name is an error (exit code 2) that lists the known profiles.
- **The default profile is your existing setup:** the files directly in `~/.config/ga-cli/`. Nothing is migrated, and without `--profile` everything works as before. Named profiles live in `~/.config/ga-cli/profiles/NAME/`, and `ga --profile NAME config path` prints a profile's config file.
- Profile names use letters, digits, `.`, `_`, and `-`, starting with a letter or digit. `default` means the default profile.

### gcloud Application Default Credentials

If you use the gcloud CLI, GA CLI can authenticate with [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) instead of its own login.

A plain `gcloud auth application-default login --scopes=…analytics.readonly…` does **not** work: Google blocks gcloud's built-in OAuth client from the Analytics scopes ("This app is blocked"). Use one of these instead.

**Option 1: your own OAuth client.** Pass the Desktop-app `client_secret.json` you created for `ga auth login`:

```bash
gcloud auth application-default login \
  --client-id-file=PATH/TO/client_secret.json \
  --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform
```

The `--scopes` flag matters: gcloud user credentials carry only the scopes they were created with. The command above covers reading. For admin changes, add `https://www.googleapis.com/auth/analytics.edit` to `--scopes` (plus `analytics.manage.users` for access bindings, `analytics.chatbot.read` for `ga reports chat`). If your Google Workspace blocks unverified third-party apps, an admin has to trust the OAuth client first, or use option 2.

**Option 2: impersonate a service account.** No consent screen and no scopes at login. GA CLI requests the scopes it needs. The service account needs access to your GA4 properties, and your Google account needs the Service Account Token Creator role on it:

```bash
gcloud iam service-accounts add-iam-policy-binding SA_EMAIL \
  --member="user:YOU@example.com" \
  --role=roles/iam.serviceAccountTokenCreator
gcloud auth application-default login --impersonate-service-account=SA_EMAIL
```

With either option, Google may ask for a project to use for quota and billing. The Analytics Admin and Data APIs must be enabled in it:

```bash
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

If a call fails for missing scopes while using ADC, the error includes both login commands. Add the extra scopes to option 1 if the failing command needs them.

ADC is the last resort. It is only used by the default profile, and only when nothing else is configured: no `GA_CLI_SERVICE_ACCOUNT`, no service-account `GOOGLE_APPLICATION_CREDENTIALS`, and no `ga auth login`. Named profiles never use it. `ga auth status` shows `adc` as the method when it's in use.

## Command Reference

| Command | Subcommands | Description |
|---------|-------------|-------------|
| `ga auth` | `setup`, `login`, `logout`, `status` | Manage authentication |
| `ga config` | `setup`, `get`, `set`, `unset`, `path`, `reset` | Manage CLI configuration |
| `ga profiles` | `list`, `delete` | Manage named credential profiles |
| `ga accounts` | `list`, `get`, `update`, `delete`, `get-data-sharing`, `change-history` | Manage GA4 accounts |
| `ga account-summaries` | `list` | Quick overview of all accounts and properties |
| `ga properties` | `list`, `get`, `create`, `update`, `delete`, `acknowledge-udc`, `quotas` | Manage GA4 properties |
| `ga custom-dimensions` | `list`, `get`, `create`, `update`, `archive` | Manage custom dimensions |
| `ga custom-metrics` | `list`, `get`, `create`, `update`, `archive` | Manage custom metrics |
| `ga calculated-metrics` | `list`, `get`, `create`, `update`, `delete` | Manage calculated metrics |
| `ga data-streams` | `list`, `get`, `create`, `update`, `delete` | Manage data streams |
| `ga key-events` | `list`, `get`, `create`, `update`, `delete` | Manage key events (conversions) |
| `ga audiences` | `list`, `get`, `create`, `update`, `archive` | Manage audiences |
| `ga audience-exports` | `list`, `get`, `query`, `create` | Export the users in an audience |
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
| `ga enhanced-measurement` | `get`, `update` | Manage enhanced measurement settings |
| `ga property-settings` | `attribution`, `google-signals` | View and update property settings |
| `ga reports` | `run`, `pivot`, `batch`, `funnel`, `chat`, `check-compatibility`, `metadata`, `realtime`, `build` | Run and build reports |
| `ga agent` | `guide` | AI agent quick reference |
| `ga upgrade` | `--check`, `--force` | Check for and install updates |
| `ga completions` | `bash`, `zsh`, `fish` | Generate shell completion scripts |

Use `ga <command> --help` for detailed usage of any command, or `ga --describe` for the full CLI schema as JSON.

### Output formats

All read commands support `--output` (`-o`) to control output format:

```bash
ga accounts list --output json      # JSON output (default when piped)
ga accounts list --output table     # Table output (default in a terminal)
ga accounts list --output compact   # Minimal ID + name output
```

Without `-o`, output is a table in a terminal and JSON when piped. A configured
`output_format` (`ga config set output_format …`) overrides that default, except
that a configured `table` is ignored on a pipe. *(Changed after 0.4.0: previously
`table` — configured, or written to the config file as a default — also applied
to pipes.)*

For report commands (`run`, `realtime`, `pivot`, `funnel`, `metadata`,
`check-compatibility`), `-o compact` prints TSV: a header line of field names,
then one line per row, with tabs, newlines and backslashes in values escaped as
`\t`, `\n`, `\\`. Aggregation rows, quota and data notes go to stderr, so
stdout holds only rows.

`ga reports run` defaults to `--start-date 7daysAgo --end-date yesterday`, which
matches the GA4 UI's "Last 7 days" and leaves out today's incomplete data. Without
`--end-date`, a range starting `today` also ends `today`. *(Changed after 0.4.0:
the end date used to be `today`.)*

> **Breaking change (post-0.3.0):** `ga reports run` and `ga reports build` with
> `-o json` return a `{"rows": [...], "metadata": {...}}` envelope instead of a
> bare rows array. `metadata` is the API's
> [`ResponseMetaData`](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/ResponseMetaData)
> — sampling, thresholding, and data-truncation information that was previously
> discarded. In table output the same information renders as a **Data Notes**
> section under the results whenever present; unaffected reports look exactly as
> before.
>
> **Breaking change (post-0.4.0):** `ga reports realtime -o json` now returns the
> same envelope. Every envelope also carries `rowCount` (total rows before
> `--limit`; with several date ranges, total dimension combinations, each of
> which appears once per range), plus `totals` / `minimums` / `maximums` when `--metric-aggregation`
> is used (each row labelled with `dateRange` when several date ranges are
> requested), and `propertyQuota` with `--return-property-quota`. Previously
> aggregations were printed as a second JSON document. The Realtime API returns
> no `ResponseMetaData`, so realtime's `metadata` is always `{}`.
>
> ```json
> {"rows": [...], "metadata": {...}, "rowCount": 652,
>  "totals": [{"dateRange": "current", "sessions": "800"}], "propertyQuota": {...}}
> ```

## Chat

Ask questions about a property in plain language:

```bash
ga reports chat "how many users did I have last week?"
ga reports chat "now break that down by country" --continue
ga reports chat --interactive          # multi-turn conversation
ga reports chat "top pages" -o json    # raw ChatResponse for scripts
```

| Flag | Effect |
|------|--------|
| `--session-id ID` | Continue a specific conversation |
| `--continue` | Continue this property's most recent conversation |
| `--interactive` / `-i` | Multi-turn REPL; quota shown per turn |
| `--return-property-quota` | Show token quota (on by default in `--interactive`) |

> **Built on the `v1alpha` Data API.** Google announced GA for `properties.chat`
> on 2026-09-17; it now works end-to-end on live GA4 properties. The method
> still lives under the `v1alpha` API version, so its shape may still change.
> If you do hit a `403`, it means either you lack access to the property or
> chat isn't enabled for your account — the API returns the same generic
> message for both, so the CLI names both possibilities.
>
> Chat requires the `analytics.chatbot.read` scope, added in 0.3.0. **If you
> authenticated with an earlier version, run `ga auth login` again** — a
> refresh token cannot gain a scope it was never granted. Other commands are
> unaffected.
>
> Uses AI and may return inaccurate information.

## Global Options

```
--help, -h      Show help
--version, -v   Show version
--quiet, -q     Suppress non-essential output
--no-color      Disable colored output
--describe      Show full CLI schema as JSON (for agents and tooling)
--profile NAME  Use a named profile (credentials + config); also GA_CLI_PROFILE
```

Global options go right after `ga`, before the command group: `ga --profile client-a reports run …`.

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
| `GA_CLI_SERVICE_ACCOUNT` | Path to service account key file (default profile only) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Standard GCP credential path (default profile only): a service account key, or any other ADC credential file such as a Workload Identity Federation config, which is used via ADC |
| `GA_CLI_PROFILE` | Named profile to use, like `--profile` (which takes precedence) |
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

To avoid storing a key, use Workload Identity Federation instead: [`google-github-actions/auth`](https://github.com/google-github-actions/auth) (with `id-token: write` permission, impersonating a service account that has access to the GA4 property) sets `GOOGLE_APPLICATION_CREDENTIALS` to an `external_account` credential file, which GA CLI picks up through ADC. Skip `ga auth login` and use the default profile.

## Troubleshooting

**`ga` runs `git add` instead of GA CLI.** You have a shell alias shadowing the command — commonly `alias ga='git add'` in `~/.gitconfig`-style setups or `~/.zshrc`/`~/.bashrc`. Run `type ga` to confirm, then `unalias ga` (or remove the alias from your shell config) and restart your shell. The same CLI is also installed as `google-analytics-cli`, which sidesteps the alias entirely.

**`ga: command not found` after install.** Your Python user bin directory isn't on `PATH`. For `pip install --user`, `pipx`, or `uv tool install`, the binary lives in `~/.local/bin` on Linux/macOS. Add it to your shell config:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc  # or ~/.bashrc
```

Then restart your shell. `pipx ensurepath` and `uv tool update-shell` can do this automatically.

**Upgrading from 0.2.1 or earlier on macOS.** Older versions stored config at `~/Library/Application Support/ga-cli/`. GA CLI now uses `~/.config/ga-cli/` on all platforms and will migrate the directory automatically the first time you run any command. No action required.

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
uv run ruff check src/ tests/ scripts/
```

## License

MIT
