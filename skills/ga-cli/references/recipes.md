# Worked patterns

Command shapes for the analyses people actually ask for. `PROP` is the numeric property ID; omit `-p` entirely if `default_property_id` is set. All of these are read-only except the `create` step in [Export the users in an audience](#export-the-users-in-an-audience), which charges quota tokens.

Contents:
- [Traffic trend over time](#traffic-trend-over-time)
- [Period-over-period comparison](#period-over-period-comparison)
- [Channel and campaign attribution](#channel-and-campaign-attribution)
- [Page and landing-page performance](#page-and-landing-page-performance)
- [Key events and conversion rate](#key-events-and-conversion-rate)
- [Segmenting with filters](#segmenting-with-filters)
- [Realtime](#realtime)
- [Funnels](#funnels)
- [Auditing an account's configuration](#auditing-an-accounts-configuration)
- [Investigating a drop](#investigating-a-drop)
- [Export the users in an audience](#export-the-users-in-an-audience)

## Traffic trend over time

```bash
ga reports run -p PROP \
  -m sessions,totalUsers,screenPageViews \
  -d date --start-date 30daysAgo --end-date yesterday \
  --order-by date:asc --limit 100 -o json
```

`--order-by date:asc` is not optional — without it rows arrive sorted by `sessions` descending and the series is meaningless. Ending at `yesterday` avoids today's partial data.

Dates come back as `YYYYMMDD` strings (`"20260827"`). Reformat them before showing the user.

Relative date keywords the API accepts: `today`, `yesterday`, `NdaysAgo`. Absolute dates are `YYYY-MM-DD`. For whole months, compute the explicit boundaries — there is no `lastMonth` keyword.

## Period-over-period comparison

One call, two named ranges, so the periods are aligned and returned together:

```bash
ga reports run -p PROP -m sessions,keyEvents \
  -d sessionDefaultChannelGroup \
  --date-range 14daysAgo,8daysAgo,prior \
  --date-range 7daysAgo,yesterday,recent \
  -o json
```

Each row carries a `dateRange` field with your name, so you get one row per dimension value per period:

```json
{"sessionDefaultChannelGroup": "Direct", "dateRange": "prior",  "sessions": "172"}
{"sessionDefaultChannelGroup": "Direct", "dateRange": "recent", "sessions": "95"}
```

Compute the deltas yourself and lead with them — the user wants "Direct fell 45%", not two columns to subtract.

Keep the windows equal in length, and be careful with day-of-week effects: a 7-day window compared against a 7-day window is sound; 7 days against 30 is not.

## Channel and campaign attribution

```bash
# Channels
ga reports run -p PROP -m sessions,engagedSessions,keyEvents \
  -d sessionDefaultChannelGroup --start-date 30daysAgo --end-date yesterday \
  --order-by sessions:desc -o json

# Source/medium detail
ga reports run -p PROP -m sessions,keyEvents \
  -d sessionSourceMedium --start-date 30daysAgo --end-date yesterday \
  --order-by sessions:desc --limit 25 -o json

# One campaign
ga reports run -p PROP -m sessions,keyEvents -d sessionCampaignName,date \
  --dim-filter 'sessionCampaignName==spring_sale' \
  --start-date 30daysAgo --order-by date:asc -o json
```

Use `session*` dimensions here. For "where did our users originally come from", switch to `firstUserDefaultChannelGroup` with `totalUsers` — see the scope table in `fields.md`.

## Page and landing-page performance

```bash
# Most-viewed pages
ga reports run -p PROP -m screenPageViews,totalUsers \
  -d pagePath --start-date 28daysAgo --end-date yesterday \
  --order-by screenPageViews:desc --limit 20 -o json

# Landing pages, with engagement
ga reports run -p PROP -m sessions,engagementRate,keyEvents \
  -d landingPage --start-date 28daysAgo --end-date yesterday \
  --order-by sessions:desc --limit 20 -o json

# One section of the site
ga reports run -p PROP -m screenPageViews -d pagePath \
  --dim-filter 'pagePath begins_with /blog' \
  --start-date 28daysAgo --order-by screenPageViews:desc --limit 20 -o json
```

`pagePath` is high-cardinality — always bound it with `--order-by` plus `--limit`, or you'll pull a large, mostly-zero tail and may hit the `(other)` bucket.

## Key events and conversion rate

```bash
# All key events over time
ga reports run -p PROP -m keyEvents,sessionKeyEventRate \
  -d date --start-date 30daysAgo --end-date yesterday --order-by date:asc -o json

# Which key events fire
ga reports run -p PROP -m eventCount -d eventName \
  --dim-filter 'isKeyEvent==true' --start-date 30daysAgo \
  --order-by eventCount:desc -o json

# One specific conversion by channel
ga reports run -p PROP -m 'keyEvents:purchase,sessionKeyEventRate:purchase' \
  -d sessionDefaultChannelGroup --start-date 30daysAgo -o json
```

**Sorting by a colon-containing metric needs that metric in `-m`.** `--order-by 'keyEvents:purchase:desc'` works because `keyEvents:purchase` is one of the requested metrics, and the parser uses `-m`/`-d` to tell the field name from the direction. Without it, `purchase` is read as the direction and fails with "Invalid sort direction". Results already default to the first metric descending, so `--order-by` is often unnecessary here.

Check which per-event metrics the property actually has before using them:

```bash
ga reports metadata -p PROP --type metrics -o json | jq -r '.[].apiName' | grep '^keyEvents:'
```

Prefer `sessionKeyEventRate` over dividing `keyEvents` by `sessions` yourself.

## Segmenting with filters

```bash
# Mobile only
--dim-filter 'deviceCategory==mobile'

# Exclude internal/direct noise
--dim-filter 'sessionMedium!=none'

# Two conditions (ANDed)
--dim-filter 'country==Germany' --dim-filter 'deviceCategory==mobile'

# Only meaningful rows
--metric-filter 'sessions>50'
```

Repeated filter flags AND together — there is no OR in the DSL.

**OR across one field** is covered by `in`:

```bash
--dim-filter 'sessionDefaultChannelGroup in Organic Social,Referral'
```

**OR across different fields** needs a raw `FilterExpression`. Write it to a file and pass `@file`, which avoids shell-quoting pain:

```json
{
  "orGroup": {
    "expressions": [
      {"filter": {"fieldName": "sessionDefaultChannelGroup",
                  "stringFilter": {"matchType": "EXACT", "value": "Organic Social"}}},
      {"filter": {"fieldName": "landingPage",
                  "stringFilter": {"matchType": "BEGINS_WITH", "value": "/blog"}}}
    ]
  }
}
```

```bash
ga reports run -p PROP -m sessions,keyEvents -d sessionDefaultChannelGroup \
  --filter-json @or_filter.json --start-date 30daysAgo --end-date yesterday -o json
```

The JSON is the Data API's `FilterExpression` verbatim, so `andGroup`, `notExpression`, `inListFilter` and `numericFilter` all work the same way.

## Realtime

```bash
ga reports realtime -p PROP -m activeUsers -d country -o json
ga reports realtime -p PROP -m activeUsers -d unifiedScreenName -o json
```

Realtime covers roughly the last 30 minutes, supports a much smaller field set, and takes no date range. `--interval N` polls continuously — don't use it in a non-interactive session, it won't terminate.

## Funnels

Funnel reports (v1alpha) take a JSON request body rather than flags, and the date range lives inside the JSON:

```bash
ga reports funnel -p PROP -c funnel_config.json -o json
```

```json
{
  "dateRanges": [{"startDate": "30daysAgo", "endDate": "yesterday"}],
  "funnel": {
    "steps": [
      {"name": "Viewed product", "filterExpression": {"funnelEventFilter": {"eventName": "product_page_view"}}},
      {"name": "Purchased",      "filterExpression": {"funnelEventFilter": {"eventName": "purchase"}}}
    ]
  }
}
```

Write the config to a file first. Table output gives step name, active users, completion and abandonment rate.

## Auditing an account's configuration

```bash
ga account-summaries list -o json          # accounts + their properties in one call
ga properties list -a ACCT -o json
ga data-streams list -p PROP -o json
ga custom-dimensions list -p PROP -o json
ga custom-metrics list -p PROP -o json
ga key-events list -p PROP -o json
ga data-retention get -p PROP -o json
ga property-settings attribution -p PROP -o json      # there is no `property-settings get`
ga property-settings google-signals -p PROP -o json
ga bigquery-links list -p PROP -o json
ga access-bindings list -p PROP -o json    # who has access
ga enhanced-measurement get -p PROP -s STREAM -o json
```

Access bindings are the part worth reading closely: service accounts holding Editor or Admin, especially default Compute Engine ones, are a common and genuine finding.

`account-summaries list` is the cheapest way to map the whole estate — it returns accounts with their properties nested, avoiding a list-then-loop.

Resource names come back as `properties/250400352`; extract the numeric ID with `jq -r '.[].name' | grep -o '[0-9]*$'`.

## Investigating a drop

A structured sequence, because "traffic dropped" has a small number of usual causes:

1. **Confirm it's real.** Trend the metric with `--order-by date:asc`, ending at `yesterday`. A dip in the last day or two is normally processing lag.
2. **Find the segment.** Break the same period comparison down by `sessionDefaultChannelGroup` — most genuine drops are concentrated in one channel rather than spread evenly.
3. **Narrow it.** If one channel moved, go to `sessionSourceMedium` within it; if organic, check `landingPage` for pages that lost traffic.
4. **Rule out measurement.** A drop across *all* channels simultaneously usually means tracking broke, not that demand vanished. Check `ga data-streams list` and whether `eventCount` for `page_view` fell in step.
5. **Check for config changes.** `ga accounts change-history -a ACCT -o json` shows who changed what and when — a tracking change on the right date explains a lot. `ga annotations list -p PROP -o json` may record a known event (a migration, a campaign launch).

Report the finding, not the process: which segment moved, by how much, and what the evidence points to.

## Export the users in an audience

For "give me the device IDs in my Purchasers audience". This spans two turns, because an export takes ~15 minutes to build. SKILL.md's "Audience exports" section explains each rule.

```bash
# 1. Find the audience. `name` ends in the audience ID.
ga audiences list -p PROP -o json | jq -r '.[] | "\(.name)\t\(.displayName)"'

# 2. Preview the request, show the user, get agreement
ga audience-exports create -p PROP --audience-id AUDIENCE \
  --dimensions deviceId,userId --dry-run

# 3. Create it. No --wait: it would outlive your tool-call timeout.
ga audience-exports create -p PROP --audience-id AUDIENCE \
  --dimensions deviceId,userId -o json | jq -r '.exportId'
```

Report the export ID and stop. Tell the user it typically takes ~15 minutes and that you'll check when they're back. If `exportId` is `null`, find the export with `ga audience-exports list -p PROP -o json` instead of creating another one; each `create` charges quota tokens again.

On a later turn:

```bash
# 4. Is it ready?
ga audience-exports get -p PROP --export-id EXPORT -o json \
  | jq '{state, percentageCompleted, rowCount, errorMessage}'
```

`CREATING` means not yet: report `percentageCompleted` and check again later. `FAILED` carries an `errorMessage`; a common cause is quota exhaustion. Report it, and ask before creating a replacement. Only `ACTIVE` can be queried.

```bash
# 5. Page through the users, one file per page
ga audience-exports query -p PROP --export-id EXPORT \
  --limit 10000 --offset 0 -o json > users_0.json
jq '{rowCount, returned: (.audienceRows | length)}' users_0.json

# Next page: advance --offset by `returned`, until it reaches rowCount
ga audience-exports query -p PROP --export-id EXPORT \
  --limit 10000 --offset 10000 -o json > users_1.json

# Flatten to CSV; .audienceExport.dimensions names the columns, in order
jq -r '.audienceRows[] | [.dimensionValues[].value] | @csv' users_*.json > users.csv
```

`--limit` defaults to 10,000 and is capped at 250,000 per request, and a page can come back shorter than `--limit`, so step by `returned`, not by `--limit`. Thousands of IDs don't belong in your context or in the reply. Report `rowCount`, where the file is, and a few sample rows if the user wants them.
