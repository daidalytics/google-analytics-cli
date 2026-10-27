# Command reference

Generated from `ga --describe`, so it matches the installed CLI exactly. **Use this instead of running `--help`** — a `--help` round-trip per command is the single biggest source of wasted turns when driving this tool, and everything you'd learn from it is below.

How to read an entry:

- `-x X` — a **required** flag.
- `[-a | -p]` — identity flags that are optional *only* because they fall back to `ga config` defaults. If no default is set and you don't pass one, the command fails. Pass them explicitly whenever you know the ID.
- `MUTATES` — changes the user's live GA4 setup. Preview with `--dry-run` first and get agreement before running for real. `--yes` skips the confirmation prompt.
- `opts:` — the useful optional flags, abbreviated. `-o json` is available on every read command and is omitted here.
- Positional arguments aren't listed. There are five: `ga config get [KEY]`, `ga config set KEY VALUE`, `ga config unset KEY`, `ga profiles delete NAME`, and `ga reports chat "QUESTION"`. Everything else, every ID included, is a flag.
- Root options aren't listed either. `--profile NAME`, `-q`, and `--no-color` go right after `ga`, before the group: `ga --profile client-a reports run …`. Placed after the subcommand they fail with "No such option".

## Short-flag collisions that will bite you

The same short flag means different things in different groups. These are the ones that actually differ from the obvious guess:

| Flag | Usually | But in… |
|---|---|---|
| `-a` | `--account-id` | `ga annotations *` it is `--annotation-id`; `ga audiences *` it is `--audience-id` |
| `-d` | `--dimensions` (reports) | `ga custom-dimensions *` it is `--dimension-id` |
| `-m` | `--metrics` (reports) | `ga custom-metrics *` / `ga calculated-metrics *` it is `--metric-id` |
| `-l` | `--limit` | `ga bigquery-links *` it is `--link-id` |
| `-b` | — | `ga access-bindings *` `--binding-id` |
| `-k` | — | `ga key-events *` `--key-event-id` |
| `-s` | `--section` (agent guide), `--search` (metadata) | `ga data-streams` / `enhanced-measurement` / `event-create-rules` / `event-edit-rules` / `mp-secrets` `--stream-id`; `ga auth login` `--service-account` |

When in doubt, spell out the long flag — `--property-id`, `--dimension-id` — since long forms never collide.

## Things the schema won't tell you

Each of these was hit by an agent driving this CLI and cost a wasted round-trip:

- **`ga property-settings` has no `get`.** Read attribution and Google Signals with `ga property-settings attribution -p PROP` and `ga property-settings google-signals -p PROP`.
- **IDs are positional-looking but aren't.** `ga properties get 250400352` fails; it is `ga properties get -p 250400352`. Every ID goes through a flag.
- **`accounts change-history --since/--until` needs full RFC3339 ending in `Z`.** Both `--since 2026-03-01` and `--since 180daysAgo` fail with an "Illegal timestamp format" API error; use `--since 2026-03-01T00:00:00Z`. The relative `NdaysAgo` keywords work for *report* date ranges only, not here. Omitting `--since` also works and returns recent history.
- **`ga user-provided-data get` is broken** in the current release — it fails with `'Resource' object has no attribute 'getUserProvidedDataSettings'`. Skip it during audits; there's no CLI-side workaround.
---

<!-- BEGIN GENERATED: ga --describe -->

### ga access-bindings

- `ga access-bindings create` -u X -r X [-a | -p]
- `ga access-bindings delete` -b X [-a | -p]
- `ga access-bindings get` -b X [-a | -p]
- `ga access-bindings list` [-a | -p]
- `ga access-bindings update` -b X -r X [-a | -p]

### ga access-reports

- `ga access-reports run-account` [-a]
  - opts: -d, -m, --start-date, --end-date, -l, --offset, --include-all-users, --expand-groups
- `ga access-reports run-property` [-p]
  - opts: -d, -m, --start-date, --end-date, -l, --offset, --include-all-users, --expand-groups

### ga account-summaries

- `ga account-summaries list`

### ga accounts

- `ga accounts change-history` [-a | -p]
  - opts: --resource-type, --action, --since, --until, -l
- `ga accounts delete` [-a]  _MUTATES, --dry-run_
- `ga accounts get` [-a]
- `ga accounts get-data-sharing` [-a]
- `ga accounts list`
- `ga accounts update` --name X [-a]  _MUTATES, --dry-run_

### ga agent

- `ga agent guide`
  - opts: -s

### ga allowlist

- `ga allowlist show`

### ga annotations

- `ga annotations create` --title X --annotation-date X [-p]  _MUTATES, --dry-run_
  - opts: --description, --color
- `ga annotations delete` -a X [-p]  _MUTATES, --dry-run_
- `ga annotations get` -a X [-p]
- `ga annotations list` [-p]
- `ga annotations update` -a X [-p]  _MUTATES, --dry-run_
  - opts: --title, --description, --color

### ga audience-exports

- `ga audience-exports create` --audience-id X --dimensions X [-p]  _MUTATES, --dry-run_
  - opts: --wait, --timeout
- `ga audience-exports get` --export-id X [-p]
- `ga audience-exports list` [-p]
- `ga audience-exports query` --export-id X [-p]
  - opts: --limit, --offset

### ga audiences

- `ga audiences archive` -a X [-p]
- `ga audiences create` -c X [-p]
- `ga audiences get` -a X [-p]
- `ga audiences list` [-p]
- `ga audiences update` -a X -c X [-p]

### ga auth

- `ga auth login`
  - opts: -s
- `ga auth logout`
- `ga auth setup`
- `ga auth status`

### ga bigquery-links

- `ga bigquery-links create` --project X --dataset-location X [-p]
  - opts: --daily-export, --streaming-export, --fresh-daily-export, --include-advertising-id, --export-streams, --excluded-events
- `ga bigquery-links delete` -l X [-p]
- `ga bigquery-links get` -l X [-p]
- `ga bigquery-links list` [-p]
- `ga bigquery-links update` -l X [-p]
  - opts: --daily-export, --streaming-export, --fresh-daily-export, --include-advertising-id, --export-streams, --excluded-events

### ga calculated-metrics

- `ga calculated-metrics create` --calculated-metric-id X --display-name X --formula X --metric-unit X [-p]  _MUTATES, --dry-run_
  - opts: --description
- `ga calculated-metrics delete` -m X [-p]  _MUTATES, --dry-run_
- `ga calculated-metrics get` -m X [-p]
- `ga calculated-metrics list` [-p]
- `ga calculated-metrics update` -m X [-p]  _MUTATES, --dry-run_
  - opts: --display-name, --description, --formula, --metric-unit

### ga channel-groups

- `ga channel-groups create` -c X [-p]
- `ga channel-groups delete` -g X [-p]
- `ga channel-groups get` -g X [-p]
- `ga channel-groups list` [-p]
- `ga channel-groups update` -g X -c X [-p]

### ga completions

- `ga completions bash`
- `ga completions fish`
- `ga completions zsh`

### ga config

- `ga config get`
- `ga config path`
- `ga config reset`
- `ga config set`
- `ga config setup`
- `ga config unset`

### ga custom-dimensions

- `ga custom-dimensions archive` -d X [-p]  _MUTATES, --dry-run_
- `ga custom-dimensions create` --parameter-name X --display-name X --scope X [-p]  _MUTATES, --dry-run_
  - opts: --description, --disallow-ads
- `ga custom-dimensions get` -d X [-p]
- `ga custom-dimensions list` [-p]
- `ga custom-dimensions update` -d X [-p]  _MUTATES, --dry-run_
  - opts: --display-name, --description

### ga custom-metrics

- `ga custom-metrics archive` -m X [-p]  _MUTATES, --dry-run_
- `ga custom-metrics create` --parameter-name X --display-name X --scope X --measurement-unit X [-p]  _MUTATES, --dry-run_
  - opts: --description
- `ga custom-metrics get` -m X [-p]
- `ga custom-metrics list` [-p]
- `ga custom-metrics update` -m X [-p]  _MUTATES, --dry-run_
  - opts: --display-name, --description, --measurement-unit

### ga data-retention

- `ga data-retention get` [-p]
- `ga data-retention update` [-p]  _MUTATES, --dry-run_
  - opts: --event-data-retention, --user-data-retention, --reset-on-new-activity

### ga data-streams

- `ga data-streams create` --display-name X [-p]  _MUTATES, --dry-run_
  - opts: -t, --url, --bundle-id
- `ga data-streams delete` -s X [-p]  _MUTATES, --dry-run_
- `ga data-streams get` -s X [-p]
- `ga data-streams list` [-p]
- `ga data-streams update` -s X [-p]  _MUTATES, --dry-run_
  - opts: --display-name

### ga enhanced-measurement

- `ga enhanced-measurement get` -s X [-p]
- `ga enhanced-measurement update` -s X [-p]  _MUTATES, --dry-run_
  - opts: --stream-enabled, --scrolls, --outbound-clicks, --site-search, --video-engagement, --file-downloads, --page-changes, --form-interactions, --search-query-parameter, --uri-query-parameter

### ga event-create-rules

- `ga event-create-rules create` -s X -c X [-p]
- `ga event-create-rules delete` -s X -r X [-p]
- `ga event-create-rules get` -s X -r X [-p]
- `ga event-create-rules list` -s X [-p]
- `ga event-create-rules update` -s X -r X -c X [-p]

### ga event-edit-rules

- `ga event-edit-rules create` -s X -c X [-p]
- `ga event-edit-rules delete` -s X -r X [-p]
- `ga event-edit-rules get` -s X -r X [-p]
- `ga event-edit-rules list` -s X [-p]
- `ga event-edit-rules reorder` -s X --rule-ids X [-p]
- `ga event-edit-rules update` -s X -r X -c X [-p]

### ga firebase-links

- `ga firebase-links create` --project X [-p]  _MUTATES, --dry-run_
- `ga firebase-links delete` --link-id X [-p]  _MUTATES, --dry-run_
- `ga firebase-links list` [-p]

### ga google-ads-links

- `ga google-ads-links create` --customer-id X [-p]  _MUTATES, --dry-run_
  - opts: --ads-personalization
- `ga google-ads-links delete` --link-id X [-p]  _MUTATES, --dry-run_
- `ga google-ads-links list` [-p]
- `ga google-ads-links update` --link-id X [-p]  _MUTATES, --dry-run_
  - opts: --ads-personalization

### ga key-events

- `ga key-events create` -e X [-p]  _MUTATES, --dry-run_
  - opts: --counting-method
- `ga key-events delete` -k X [-p]  _MUTATES, --dry-run_
- `ga key-events get` -k X [-p]
- `ga key-events list` [-p]
- `ga key-events update` -k X [-p]  _MUTATES, --dry-run_
  - opts: --counting-method

### ga mp-secrets

- `ga mp-secrets create` -s X --display-name X [-p]  _MUTATES, --dry-run_
- `ga mp-secrets delete` -s X --secret-id X [-p]  _MUTATES, --dry-run_
- `ga mp-secrets get` -s X --secret-id X [-p]
- `ga mp-secrets list` -s X [-p]
- `ga mp-secrets update` -s X --secret-id X [-p]  _MUTATES, --dry-run_
  - opts: --display-name

### ga profiles

- `ga profiles delete`
- `ga profiles list`

### ga properties

- `ga properties acknowledge-udc` [-p]  _MUTATES, --dry-run_
- `ga properties create` --name X [-a]  _MUTATES, --dry-run_
  - opts: --timezone, --currency
- `ga properties delete` [-p]  _MUTATES, --dry-run_
- `ga properties get` [-p]
- `ga properties list` [-a]
- `ga properties quotas` [-p]
- `ga properties update` [-p]  _MUTATES, --dry-run_
  - opts: --name, --timezone, --currency, --industry

### ga property-settings

- `ga property-settings attribution` [-p]
  - opts: --acquisition-lookback, --other-lookback, --attribution-model, --ads-export-scope
- `ga property-settings google-signals` [-p]
  - opts: --state

### ga reports

- `ga reports batch` -c X [-p]
- `ga reports build` [-p]
- `ga reports chat` [-p]
  - opts: --session-id, --continue, -i, --return-property-quota
- `ga reports check-compatibility` [-p]
  - opts: -m, -d
- `ga reports funnel` -c X [-p]
- `ga reports metadata` [-p]
  - opts: -t, -s
- `ga reports pivot` -m X -d X --pivot-field X [-p]
  - opts: --start-date, --end-date, -l, --pivot-limit
- `ga reports realtime` [-p]
  - opts: -m, -d, --interval, --dim-filter, --metric-filter, --filter-json, --order-by, --minute-range, --metric-aggregation, --return-property-quota
- `ga reports run` [-p]
  - opts: -m, -d, --start-date, --end-date, --limit, --dim-filter, --metric-filter, --filter-json, --order-by, --offset, …

### ga user-provided-data

- `ga user-provided-data get` [-p]

<!-- END GENERATED -->

