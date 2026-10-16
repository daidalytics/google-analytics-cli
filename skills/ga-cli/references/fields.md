# Choosing metrics and dimensions

Contents:
- [Corrections to the built-in guide](#corrections-to-the-built-in-guide)
- [Dimension scope — the big one](#dimension-scope--the-big-one)
- [Question to field mapping](#question-to-field-mapping)
- [Metric meanings that get confused](#metric-meanings-that-get-confused)
- [Filter and sort syntax](#filter-and-sort-syntax)
- [Verifying against the property](#verifying-against-the-property)

## Corrections to the built-in guide

`ga agent guide --section reports` prints a "Common Metrics" table that predates GA4's 2024 rename of conversions to key events. Where this file and that table disagree, this file is correct — it was checked against live API metadata.

| Guide says | Use instead | Why |
|---|---|---|
| `conversions` | `keyEvents` | `conversions` still works as a legacy alias, but it no longer appears in metadata, so it won't survive a `metadata --search` check and may eventually go away. `keyEvents` is the current name. |
| — | `keyEvents:purchase` | Per-event variants exist for each key event configured on the property (`keyEvents:signup`, `sessionKeyEventRate:purchase`, …). Use these when the user asks about one specific conversion rather than all of them. |
| — | `sessionKeyEventRate`, `userKeyEventRate` | Conversion *rate* per session or per user. Don't hand-divide `keyEvents / sessions`; the API's definition handles attribution correctly. |
| `activeUsers` "(realtime only)" | `activeUsers` works in standard reports too | It is not realtime-exclusive. It's the closest thing GA4 has to the UI's headline "Users". |

The set of `keyEvents:*` metrics is property-specific. Confirm with:

```bash
ga reports metadata -p PROP --type metrics -o json | jq -r '.[].apiName' | grep keyEvent
```

## Dimension scope — the big one

Every GA4 dimension is scoped to an event, a session, or a user. Metrics are scoped too. Combining mismatched scopes doesn't error — it returns numbers that look reasonable and are wrong, because the API fans one scope's rows across another's.

The rule: **match the dimension's scope to the metric you care about.**

| Asking about | Metric | Correct dimension | Wrong choice |
|---|---|---|---|
| Which channel drove sessions | `sessions` | `sessionDefaultChannelGroup`, `sessionSourceMedium`, `sessionSource`, `sessionMedium`, `sessionCampaignName` | `sourceMedium`, `source` (event-scoped) |
| How users were first acquired | `totalUsers`, `newUsers` | `firstUserDefaultChannelGroup`, `firstUserSourceMedium` | `sessionSourceMedium` (that's per-session, not per-user's-origin) |
| Which page was viewed | `screenPageViews` | `pagePath`, `pageTitle` | `landingPage` |
| Where sessions started | `sessions`, `bounceRate` | `landingPage` | `pagePath` (splits a session across every page it touched) |

Three prefixes to internalise:

- **`session*`** — the attribution as of that session. Pair with `sessions`, `engagedSessions`, `bounceRate`, `keyEvents`.
- **`firstUser*`** — how this user first ever arrived, fixed for their lifetime. Pair with `totalUsers`, `newUsers`. Answers "where do our users originally come from".
- **no prefix** (`sourceMedium`, `source`, `campaignName`) — event-scoped, last-touch at event level. Rarely what someone means in a traffic report; it's for attribution analysis of specific events.

If the user asks a loose question like "where does our traffic come from", session scope is the safe default and matches what the GA4 UI's Acquisition → Traffic acquisition report shows.

## Question to field mapping

| The user asks | Metrics | Dimensions |
|---|---|---|
| "how much traffic did we get" | `sessions,totalUsers,screenPageViews` | `date` (+ `--order-by date:asc`) |
| "where does traffic come from" | `sessions,engagedSessions` | `sessionDefaultChannelGroup` or `sessionSourceMedium` |
| "which pages are most popular" | `screenPageViews,totalUsers` | `pagePath` (+ `--order-by screenPageViews:desc --limit 20`) |
| "which pages do people land on" | `sessions,bounceRate` | `landingPage` |
| "how are conversions doing" | `keyEvents,sessionKeyEventRate` | `date` or `sessionDefaultChannelGroup` |
| "did campaign X work" | `sessions,keyEvents` | `sessionCampaignName` (+ `--dim-filter 'sessionCampaignName==X'`) |
| "mobile vs desktop" | `sessions,engagementRate,keyEvents` | `deviceCategory` |
| "where are users located" | `totalUsers,sessions` | `country`, `city` |
| "what events fire" | `eventCount,totalUsers` | `eventName` |
| "who's on the site right now" | `activeUsers` | `country`, `unifiedScreenName` — use `ga reports realtime` |
| "how engaged are people" | `engagementRate,averageSessionDuration,engagedSessions` | `date` or `sessionDefaultChannelGroup` |

## Metric behaviours that trip up arithmetic

Standard GA4 semantics are assumed. These are worth stating because they break *calculations*, not just wording:

- **`newUsers` is not additive.** Summed over sub-periods it exceeds `newUsers` for the whole period, because "new" is relative to the window. Don't total it across weeks.
- **`eventCount` unfiltered** includes `page_view` and `session_start`, so it's a large, mostly meaningless number. Filter to a specific `eventName`.
- **`engagementRate` and `bounceRate` are exact complements.** Quoting both reads as padding.
- **Prefer `sessionKeyEventRate` to dividing `keyEvents` by `sessions` yourself** — the API definition handles attribution correctly and a hand division won't.

## Filter and sort syntax

The CLI parses a small DSL rather than requiring raw JSON.

```bash
--dim-filter 'country==United States'          # exact
--dim-filter 'pagePath contains /blog'         # substring
--dim-filter 'sessionMedium!=none'             # negated exact
--dim-filter 'pagePath =~ ^/products/.*'       # full regex match
--dim-filter 'country in United States,Canada' # value list
--dim-filter 'pagePath begins_with /docs'      # also: ends_with
--metric-filter 'sessions>100'                 # also >= < <=
--metric-filter 'sessions between 10,100'
```

Repeating a filter flag ANDs the conditions. There's no OR in the DSL — for OR, pass a raw `FilterExpression` via `--filter-json '{...}'` or `--filter-json @file.json` using the Data API's `orGroup` structure.

Sorting is `field:direction[:type]`, repeatable, direction defaulting to `desc`:

```bash
--order-by sessions:desc
--order-by date:asc
--order-by pagePath:asc:alpha    # alpha | ialpha | numeric, dimensions only
```

## Verifying against the property

Metadata is the authority for what a given property supports, including its custom dimensions and metrics:

```bash
ga reports metadata -p PROP -o json                     # everything
ga reports metadata -p PROP --type metrics -o json
ga reports metadata -p PROP --search checkout -o json   # name search
```

Custom dimensions appear with `"custom": "True"` and are referenced by their API name (typically `customEvent:param_name` or `customUser:param_name`). If a user asks about a business-specific field — plan tier, content category, logged-in state — search metadata before concluding it doesn't exist.
