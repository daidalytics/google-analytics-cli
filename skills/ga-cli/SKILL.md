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
ga profiles list -o json  # which client identities exist, and which is active
```

If unauthenticated, tell the user to run `ga auth login` — it opens a browser and you can't complete it for them. If no default property is set and the user hasn't named one, list what's there (`ga account-summaries list -o json`) and ask which they mean. Don't silently pick the first one.

Use `-o json` for anything you parse, and pipe through `jq`. Piped output already defaults to JSON, but pass `-o json` anyway so a user's configured `output_format` can't change it. Table output is for humans. `-o compact` on reports prints TSV with a header line, which is fine for a quick look.

## Profiles

A profile is one client's credentials plus its defaults (`default_property_id`, `default_account_id`, `output_format`). Switching profile switches identity and target property together, so the wrong profile doesn't fail: it returns another client's real numbers.

**Never pick or switch to a profile the user didn't name.** If the request names a client ("how did Acme do last week?"), map it to a profile with `ga profiles list -o json` (`name`, `service_account_email`, `default_property_id`). If no profile clearly matches, or more than one could, ask. Running against the wrong client returns plausible numbers, so neither of you will notice the mistake. If the user names no client, don't add `--profile` at all; `"active": true` shows what bare commands use (`GA_CLI_PROFILE` may already be exported in their shell).

**`--profile NAME` goes right after `ga`, before the command group, never after the subcommand.** `ga --profile client-a reports run …` works; `ga reports run … --profile client-a` fails with "No such option: --profile". The per-command env prefix `GA_CLI_PROFILE=client-a ga reports run …` is equivalent and often safer, because it can't be misplaced. Either way, repeat it on every command, orientation included. Nothing persists between your tool calls, so a command without it quietly runs on whatever profile is active, usually the default.

```bash
ga profiles list -o json                     # map the client the user named to a profile
ga --profile client-a auth status -o json    # its identity
ga --profile client-a config get             # its default_property_id
GA_CLI_PROFILE=client-a ga reports run -m sessions -d date --end-date yesterday --order-by date:asc -o json
```

**A named profile never falls back.** It uses only its own stored credentials and ignores `GA_CLI_SERVICE_ACCOUNT`, `GOOGLE_APPLICATION_CREDENTIALS`, and gcloud ADC. An unknown profile exits 2 with `Profile 'X' does not exist. Known profiles: …`, and a profile without credentials also exits 2. A typo is therefore loud, not silent: report it, don't guess a fix. Two places stay quiet: `ga auth status` reports an unknown profile as `"authenticated": false` (exit 0) with that same message, and writes (`auth login`, `config set`) create the profile they name. Check a name against `ga profiles list` before writing to it.

**Creating or deleting a profile needs the user.** `ga --profile X auth login` opens a browser, so tell the user to run it. `ga --profile X auth login --service-account KEY` works non-interactively, but only with a key path the user gave you; then `ga --profile X config set default_property_id PROP`. `ga profiles delete NAME` removes that profile's stored credentials and config, which is destructive. Ask first, and pass `--yes` only once they've agreed.

**gcloud ADC is the default profile's last resort**, used only when no service account or `ga auth login` is configured. `ga auth status -o json` then shows `"method": "adc"`. gcloud user ADC carries only the scopes it was created with. If a call fails with insufficient scopes, the JSON error includes a `hint` field with the exact `gcloud auth application-default login --scopes=…` command. Relay it to the user: it's a browser login you can't run. Two follow-ups may be needed. If Google asks for a quota project, the user runs `gcloud auth application-default set-quota-project PROJECT`. And since the hinted scopes are read-only, admin writes need `https://www.googleapis.com/auth/analytics.edit` added to that login's `--scopes`.

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

- **A colon-containing field in `--order-by` must also be in `-m` or `-d`.** `--order-by 'keyEvents:purchase:desc'` works when `keyEvents:purchase` is one of your `-m` metrics: the parser uses `-m`/`-d` to tell the field name from the direction. If it isn't listed, `purchase` is read as the direction and the command fails with "Invalid sort direction". The format is `field[:asc|desc[:alpha|ialpha|numeric]]`; anything more is rejected.
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

## Audience exports

`ga audience-exports` pulls the *users* in an existing audience: one row per user, carrying the dimensions you ask for (`deviceId`, `userId`). It's a Data API snapshot, a different thing from `ga audiences`, which manages audience *definitions*. `list`, `get` and `query` are read-only; only `create` needs agreement. Find the audience ID first with `ga audiences list -p PROP -o json`; `--audience-id` takes the numeric ID or the full `properties/PROP/audiences/ID` name.

**Dry-run `create` first, even though it changes no GA config.** The reference marks it `MUTATES` because it creates a server-side resource and charges quota tokens, so the Mutations rule applies in full: `--dry-run`, show the user, get agreement. It has no confirmation prompt and no `--yes`, so your agreement step is the only gate. Every `create` charges again, so don't re-run it to recover an ID (if `exportId` comes back `null`, find it with `ga audience-exports list -p PROP -o json`), and ask before retrying a `FAILED` export.

**Never pass `--wait` in an agent session, which is every session you run.** An export typically takes ~15 minutes to become `ACTIVE`, which outlives your tool-call timeout. A `sleep`-and-`get` loop is the same mistake. Run `create` without it, report the `exportId` from its JSON to the user, and check on a later turn with `ga audience-exports get -p PROP --export-id EXPORT -o json`. If the user wants to block until it's done, that's `--wait` in their own terminal, not yours.

**Run `query` only once `state` is `ACTIVE`.** Before that it fails with "still CREATING (N%) — try again later". Page with `--limit` and `--offset`: the default is 10,000 rows and the maximum is 250,000 per request. Advance `--offset` by the rows actually returned until you reach `rowCount`. A page of IDs is too big to read into your context, so write it to a file and report counts.

The ID flags are long-only: `--export-id`, `--audience-id`. There are no short forms (`-a` is `--audience-id` in `ga audiences`, not here).

Only request dimension names you can verify. `deviceId` and `userId` are safe. Export dimensions are their own schema, not report dimensions, and the CLI passes `--dimensions` through unchecked, so for anything else check Google's list at https://developers.google.com/analytics/devguides/reporting/data/v1/audience-list-api-schema#dimensions rather than guessing.

```bash
ga audiences list -p PROP -o json      # find the audience ID
ga audience-exports create -p PROP --audience-id AUDIENCE --dimensions deviceId,userId --dry-run
ga audience-exports create -p PROP --audience-id AUDIENCE --dimensions deviceId,userId -o json   # after agreement; NO --wait
ga audience-exports get -p PROP --export-id EXPORT -o json      # a later turn: is state ACTIVE?
ga audience-exports query -p PROP --export-id EXPORT --limit 10000 --offset 0 -o json > users_0.json
```

`references/recipes.md` has the full sequence, with paging.

## Reference files

- `references/commands.md` — every command, its flags, and the short-flag collisions. Read before composing non-obvious commands.
- `references/fields.md` — metric and dimension choice, scope rules, corrections to the CLI's built-in metric table.
- `references/recipes.md` — worked patterns: trends, period comparison, attribution, landing pages, funnels, account audits, investigating a drop.
