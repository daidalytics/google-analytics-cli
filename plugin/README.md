# google-analytics-cli plugin

A Claude Code plugin with one skill, `ga-cli`. The skill teaches Claude to answer Google Analytics 4 questions and manage GA4 configuration by running the [`ga` command-line tool](https://github.com/daidalytics/google-analytics-cli) on your machine.

The plugin contains only Markdown: the skill and its command reference. It ships no scripts, hooks, or MCP servers. See [Privacy](#privacy) for what data is read and where it goes. The `ga` CLI is installed separately:

```bash
uv tool install google-analytics-cli
```

## What the skill does

- Runs GA4 reports (standard, realtime, pivot, funnel) through the Data API.
- Reads and changes GA4 configuration through the Admin API: properties, data streams, custom dimensions and metrics, audiences, key events, links, and access bindings.
- Dry-runs every change and asks you before applying it.

## Privacy

The plugin has no service of its own. Nothing is sent to the plugin's author, and there is no telemetry.

When Claude runs `ga`, the CLI talks directly from your machine to these hosts:

| Host | Purpose |
|---|---|
| `analyticsdata.googleapis.com` | GA4 Data API: reports |
| `analyticsadmin.googleapis.com` | GA4 Admin API: configuration |
| `accounts.google.com`, `oauth2.googleapis.com` | Google sign-in, token exchange, refresh, and revocation |
| `www.googleapis.com` | The signed-in account's email address, for `ga auth status` |
| `pypi.org` | A daily check for a newer CLI version. It sends no account or analytics data, and it does not run under `uvx`. |

Personal data: GA4 access bindings contain the email addresses of users with access to an account or property, and `ga auth status` shows the email address of the signed-in Google account. The CLI reads these from Google and prints them; they are not stored or sent anywhere else.

Stored on your machine, in `~/.config/ga-cli/`: OAuth credentials, your CLI settings, and a cache of which accounts and properties your login can see.

Access to Google Analytics uses your own Google account or service account, with your own OAuth client. Which accounts and properties the CLI may touch can be limited with an allowlist; see the [main README](https://github.com/daidalytics/google-analytics-cli#readme).

## License

MIT
