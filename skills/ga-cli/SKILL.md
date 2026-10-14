---
name: ga-cli
description: "Answer Google Analytics 4 questions and manage GA4 configuration by driving the `ga` command-line tool (google-analytics-cli) instead of guessing or asking the user to check the GA interface. Use this whenever the user asks about website or app traffic, sessions, users, pageviews, conversions or key events, traffic sources, channels, campaigns, landing pages, bounce/engagement rate, realtime visitors, or \"how is the site doing\" — and also for GA4 admin work: properties, data streams, custom dimensions and metrics, audiences, key events, BigQuery links, access bindings, or auditing an account's setup. Use it even when the user never says \"GA4\", \"Google Analytics\", or \"ga\" — a question about site traffic or marketing performance is enough."
---

# Driving the GA CLI

`ga` is a command-line client for Google Analytics 4 covering the Data API (reports) and the Admin API (configuration). You already know GA4 as a product; what you can't know from the outside is this CLI's exact surface and its sharp edges. That's what this skill carries.

## Invocation

Use `ga` if it's on PATH (`command -v ga`). Otherwise substitute `uvx google-analytics-cli` for `ga` in every command in this skill and its references: `ga reports run …` becomes `uvx google-analytics-cli reports run …`. Auth and config live in `~/.config/ga-cli/` either way, so the two are interchangeable. Substitute in each command rather than setting an alias or variable — shell state doesn't persist between your tool calls.

If neither `ga` nor `uv` exists, tell the user to install one (`uv tool install google-analytics-cli` or `curl -LsSf https://astral.sh/uv/install.sh | sh`) and stop.

## Get the syntax from the reference, not from `--help`

`references/commands.md` is generated from `ga --describe` and lists every command with its required flags, its identity flags, and which ones mutate. **Read it before composing commands** for anything beyond a plain `reports run`.

This matters more than it sounds: probing with `--help` is the main way turns get wasted here, and the CLI has real traps that a guess will hit — `ga properties get 250400352` fails (IDs are flags, never positional), `ga property-settings get` doesn't exist, and `-a` means `--annotation-id` rather than `--account-id` inside `ga annotations`. Fall back to `--help` only when the reference genuinely lacks something.

## Orient before you query

A report against the wrong property looks exactly like an answer, which is what makes it dangerous:

```bash
ga auth status -o json    # authenticated? whose account?
ga config get             # is there a default_property_id?
```

If unauthenticated, tell the user to run `ga auth login` — it opens a browser and you can't complete it for them. If no default property is set and the user hasn't named one, list what's there (`ga account-summaries list -o json`) and ask which they mean. Don't silently pick the first one.

Use `-o json` for anything you parse, and pipe through `jq`. Table output is for humans. Avoid `-o compact` on reports specifically — it currently renders blank rows.

## The working loop

1. **Pick fields.** `references/fields.md` covers scope rules and the metric names this CLI's own docs get wrong. When you're unsure a field exists on *this* property, ask it: `ga reports metadata -p PROP --search revenue -o json`. Metadata includes the property's custom dimensions and configured key events, so it settles questions no static list can.
2. **Check exotic combinations.** `ga reports check-compatibility -p PROP -m ... -d ... -o json` is cheap and beats a confusing API error.
3. **Run it, ordered and bounded.** `--limit` defaults to 100, and rows come back sorted by the first metric descending — not by your dimension.
4. **Answer in prose.** The user asked a question in English; lead with the number and the direction, then support it. A table where an answer belongs makes them do the work they delegated.

## Defaults that keep answers honest

**End at `yesterday` unless the user explicitly asks about today.** GA4 is still processing recent data, so the last day or two reads artificially low and a drop at the right edge of the range is usually lag, not decline. Make `--end-date yesterday` your habitual default rather than something you remember to add when a range looks suspicious — this is the rule most easily lost in the middle of an interesting analysis. If you do include today, say the final point is partial.

**Sort explicitly whenever order carries meaning.** Default sorting is by the first metric descending, so a `date` report arrives shuffled and any trend read off it is noise. Pass `--order-by date:asc` for time series.

## CLI-specific traps

These are properties of this tool, not of GA4, so nothing else will warn you:

- **`--order-by` can't take a colon-containing metric.** The sort DSL splits on `:`, so `--order-by 'keyEvents:purchase:desc'` parses `purchase` as the direction and fails. Omit it (results already default to first-metric-descending) or sort client-side with `jq`.
- **The filter DSL has no OR.** Repeated `--dim-filter` flags AND together. For OR across *one* field use `in`: `--dim-filter 'country in United States,Canada'`. For OR across *different* fields you must drop to raw JSON: `--filter-json '{"orGroup":{"expressions":[...]}}'` or `--filter-json @file.json`.
- **Interactive commands will hang a non-interactive session.** `ga reports build`, `ga config setup`, and `ga reports realtime --interval` never return. Use `ga reports run` with explicit flags and `ga config set KEY VALUE`.
- **`ga reports chat` is alpha and gated** — a 403 means either no access or not enabled, indistinguishable — and it's token-metered. Prefer `ga reports run`.

## Reading results without over-claiming

`(other)` means the dimension blew past cardinality limits and the tail was bucketed — top-N is still valid, per-row totals are not. `(not set)` means the value was missing. Neither is a category; report them as data-quality facts. And with Google Signals on, rows below a user-count threshold are withheld entirely, so demographic reports can under-total against the same report without those dimensions — don't narrate that gap as a traffic change.

## Mutations

Admin commands marked `MUTATES` in the reference change the user's production analytics setup. `--dry-run` previews the exact request for free:

```bash
ga properties create -a ACCT --name "New Site" --timezone Europe/Berlin --dry-run
```

Dry-run, show the user what it would do, get agreement, then run it. `--yes` skips the confirmation prompt — that flag is a commitment, so don't reach for it just to get past a stall. Reports are read-only and safe to run freely.

## Reference files

- `references/commands.md` — every command, its flags, and the short-flag collisions. Read before composing non-obvious commands.
- `references/fields.md` — metric and dimension choice, scope rules, corrections to the CLI's built-in metric table.
- `references/recipes.md` — worked patterns: trends, period comparison, attribution, landing pages, funnels, account audits, investigating a drop.
