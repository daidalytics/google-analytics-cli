# Spec: Surface `ResponseMetaData` in report commands

Status: **Implemented — pending release** (branch `feat/response-metadata`)
Target version: 0.4.0 (tentative)
API: `analyticsdata` v1beta / v1alpha, revision `20260909`

---

## Objective

`reports run`, `reports build`, `reports batch`, and `reports pivot` all call GA4 Data API
methods whose response carries a `ResponseMetaData` (aka `metadata`) object — sampling info,
thresholding flags, schema restrictions, empty-report reasons, and (newly, as of the 2026-09-09
API revision) `dataTruncationReasons`. Today this object is **silently discarded**:

- `run` and `build` output only the transformed `rows` array in every format, including
  `--output json` (`reports.py:334`, `:1517`) — there is currently no way to see this metadata
  at all through those two commands.
- `batch` and `pivot` already pass the raw API response through for `--output json`, but their
  table-mode rendering shows nothing for it.

**Users:**
1. **Humans at a terminal** running `ga reports run` — should see a plain-language warning when
   their numbers are sampled, thresholded, restricted, or truncated, without having to guess.
2. **AI agents / scripts** consuming `-o json` — should be able to detect these conditions
   programmatically instead of silently treating partial/sampled data as complete.

**Trigger:** the 2026-09-09 GA4 Discovery revision added `DataTruncationDateRange` and
`DataTruncationReason` schemas and a `dataTruncationReasons` array on `ResponseMetaData`
(`analyticsdata` v1beta/v1alpha only — `analyticsadmin` had a revision bump with no schema
diff). `.api-snapshots/analyticsdata_v1beta.json` and `_v1alpha.json` were already refreshed to
this revision in commit `5680e22`; **no `--update` run is needed for this work.**

**Success looks like:** running a report against a sampled or thresholded property shows a
metadata section under the results (table mode) or a `metadata` key in the JSON response,
without requiring any new flag.

### Assumptions

1. `reports realtime`'s response (`RunRealtimeReportResponse`) has **no `metadata` field** —
   confirmed against the v1beta snapshot. Real-time is out of scope for this feature entirely.
2. `reports funnel` (v1alpha `runFunnelReport`) is **not investigated** here — its response shape
   (`funnelTable`) was not checked for a `metadata` field. Treated as out of scope unless a
   follow-up confirms it needs the same treatment.
3. `reports check-compatibility` and `reports metadata` (the `getMetadata` endpoint, unrelated to
   `ResponseMetaData` despite the name collision) are out of scope — neither returns a report.
4. `reports chat` is unrelated (separate `ChatResponse` shape, already raw-passthrough for JSON)
   and untouched by this change.
5. Changing `run`/`build`'s JSON shape from a bare array to `{rows, metadata}` is an accepted
   **breaking change** for any existing script parsing `ga reports run -o json` as a flat array.
   This is a pre-1.0 CLI (`0.3.0`), so the project's version-bump convention (not semver-strict
   back-compat) applies; the change ships with a version bump and a release-notes callout.
6. Metadata display in table/compact mode is **automatic** whenever the API returns a non-empty
   `metadata` object — no new flag, consistent with how `_display_aggregations` already works
   whenever `--metric-aggregation` is passed. (Unlike `propertyQuota`, metadata isn't gated by a
   request-side opt-in flag on the GA4 API — the API returns it unconditionally when applicable.)
7. `batch`'s per-sub-report metadata (each item in `RunReportResponse.metadata`) is displayed
   per sub-report, directly under that sub-report's `--- Report N ---` block — consistent with
   how `batch` already repeats `_display_aggregations`-style output per sub-report today (it
   doesn't currently, but `row_count` is shown per sub-report at `reports.py:808`).
→ Correct any of these now or I'll proceed with them.

---

## API Surface (from `.api-snapshots/analyticsdata_v1beta.json`)

```jsonc
// ResponseMetaData (RunReportResponse.metadata / RunPivotReportResponse.metadata)
{
  "samplingMetadatas": [ SamplingMetadata ],       // one per date range, only if sampled
  "schemaRestrictionResponse": SchemaRestrictionResponse,
  "subjectToThresholding": boolean,
  "dataTruncationReasons": [ DataTruncationReason ], // NEW in 2026-09-09 revision
  "emptyReason": string                             // enum-like; only set when report is empty
}

// SamplingMetadata (per date range)
{ "samplingSpaceSize": string /* int64 */, "samplesReadCount": string /* int64 */ }

// SchemaRestrictionResponse
{ "activeMetricRestrictions": [
    { "metricName": string, "restrictedMetricTypes": ["COST_DATA" | "REVENUE_DATA" | ...] }
] }

// DataTruncationReason  (the field driving this spec)
{
  "dataTruncationType": "DATA_TRUNCATION_TYPE_RULES_BASED_MODELS" | "...DATA_DRIVEN_ATTRIBUTION"
    | "...DV360" | "...CM360" | "...ITEM_SCOPED_ECOMMERCE_METRICS"
    | "...EVENT_SCOPED_ECOMMERCE_METRICS" | "...DATE_RANGE" | "...PROPERTY"
    | "...CONVERSIONS" | "...GOOGLE_ADS" | "...UNSPECIFIED",
  "dataTruncationMessage": string,
  "dataTruncationDate": string,          // YYYY-MM-DD — data before this date is truncated
  "dataTruncationDateRanges": [ { "startDate": string, "endDate": string } ]
}
```

Notes that drive the design:
- `RunReportResponse.metadata` and `RunPivotReportResponse.metadata` both `$ref` the same
  `ResponseMetaData` schema — one rendering helper covers `run`, `build`, `batch`, and `pivot`.
- Every field on `ResponseMetaData` is optional/absent when not applicable. The common case
  (a small, unsampled, unrestricted, untruncated report) has an empty or near-empty `metadata`
  object — the display helper must render **nothing** in that case, not an empty section.
- `dataTruncationReasons` can contain multiple entries (e.g. both a `DATE_RANGE` truncation and a
  `GOOGLE_ADS` retention truncation on the same report) — render as a list, not a single line.
- `samplingMetadatas` is parallel to `dateRanges` by index, not named — if there are 2 date
  ranges, expect at most 2 entries in the same order.

---

## Design Decisions

### 1. One shared helper: `_display_response_metadata()`

New module-level function in `reports.py`, same shape as the existing `_display_quota()` /
`_display_aggregations()`:

```python
def _display_response_metadata(metadata: dict | None, effective_format: str) -> None:
    """Render sampling/thresholding/restriction/truncation warnings, if present.

    Mirrors _display_quota(): a no-op when the API didn't return anything
    interesting, so unaffected reports see no new output.
    """
```

Called from `run_cmd`, `build_cmd` (after the existing `_display_quota` call), from `batch_cmd`
once per sub-report, and from `pivot_cmd`'s table-mode branch. Table/compact and JSON share the
same gating logic (render only if `metadata` is non-empty) but different output paths (see below).

### 2. Table/compact rendering

Printed as a `[bold]Data Notes[/bold]` section (mirroring the existing `\n[bold]Aggregations[/bold]`
header at `reports.py:232`), after aggregations/quota, using `warn()`/`info()`-style lines rather
than a table — these are prose warnings, not tabular data:

```
[dim]150 total rows[/dim]

Data Notes
  ⚠ Truncated (DATE_RANGE): Query date range may not be fully served.
  ⚠ Truncated (GOOGLE_ADS): Google Ads data is truncated due to a 36-month retention policy
    (before 2023-09-01).
  ⚠ Subject to data thresholds — some low-volume data may be withheld.
  ℹ Sampled: 42,103 of 1,204,500 events analyzed (3.5%).
```

Rendering rules:
- `dataTruncationReasons`: one line per entry, `dataTruncationType` humanized (strip the
  `DATA_TRUNCATION_TYPE_` prefix, title-case) + `dataTruncationMessage`; append
  `(before {dataTruncationDate})` when the date is present.
- `subjectToThresholding`: one fixed line when `true`. Omit entirely when `false`/absent — a
  `false` is not noteworthy.
- `samplingMetadatas`: one line per entry with the computed percentage
  (`samplesReadCount / samplingSpaceSize`), guarding divide-by-zero.
- `schemaRestrictionResponse.activeMetricRestrictions`: one line per restricted metric, e.g.
  `⚠ Metric 'purchaseRevenue' restricted (REVENUE_DATA) — values withheld by your role.`
- `emptyReason`: shown as a single `info()` line when the report has zero rows and this is set —
  replaces the current unconditional "No results found." with the API's actual reason where
  available (table renderer's existing fallback stays for when it's absent).
- **compact format:** same content, one tab-free line per item to stderr via `warn()`/`info()`
  (keeping stdout pipeable, matching how `chat`'s session ID and quota already go to stderr in
  compact mode).

### 3. JSON rendering — breaking shape change for `run`/`build`

`run_cmd` and `build_cmd` currently do:
```python
output(rows, effective_format, columns=columns, headers=headers)
```
which for JSON prints `rows` as a bare array. This becomes:
```python
if effective_format == "json":
    output({"rows": rows, "metadata": result.get("metadata", {})}, effective_format)
else:
    output(rows, effective_format, columns=columns, headers=headers)
    _display_response_metadata(result.get("metadata"), effective_format)
```
Table/compact keep the existing flat-rows path (metadata rendered separately, as prose, not
merged into row data). Only the JSON shape changes: `{"rows": [...], "metadata": {...}}` instead
of a bare array.

`batch_cmd` and `pivot_cmd` already return the *entire* raw API response for `-o json`
(`output(result, effective_format); return` at `reports.py:525`, `:800`), which already includes
`metadata` — **no JSON-side change needed for those two**, only their table-mode branches gain
the new `_display_response_metadata()` call.

### 4. `batch` — per-sub-report metadata

Each item in `BatchRunReportsResponse.reports` is itself a `RunReportResponse` with its own
`metadata`. In table mode, call `_display_response_metadata(report.get("metadata"), ...)` right
after that sub-report's row count line (`reports.py:808-809`), inside the existing per-report
loop — so metadata attaches visibly to the sub-report it describes, not lumped at the end.

### 5. Why automatic, not flag-gated

`--return-property-quota` needs a flag because `propertyQuota` is only populated when the
*request* sets `returnPropertyQuota: true` — it's an opt-in on the wire. `ResponseMetaData`
fields have no such request-side toggle; the API includes them whenever applicable regardless of
what the CLI asks for. Gating display behind a new flag would mean users silently miss sampling/
truncation warnings unless they already knew to ask — the opposite of what this feature is for.
Precedent: `_display_aggregations()` already renders unconditionally whenever its trigger
condition (`metric_aggregations` truthy) is met, no separate display flag.

---

## Commands

No new flags or command signatures. Behavior changes only:

```bash
ga reports run -p 123 -m sessions,totalRevenue -d date          # table: may show "Data Notes"
ga reports run -p 123 -m sessions -o json                       # {"rows": [...], "metadata": {...}}
ga reports build -p 123                                          # same table-mode addition
ga reports batch -p 123 -c batch.json                            # per-sub-report "Data Notes"
ga reports pivot -p 123 -m sessions -d date --pivot-field date   # table-mode addition
```

### Dev commands (unchanged)

```bash
pytest
pytest tests/test_reports.py -v
ruff check src/ tests/
uv sync
uv build
```

---

## Project Structure

```
src/ga_cli/
└── commands/reports.py   # MODIFY — add _display_response_metadata(); wire into
                           #          run_cmd, build_cmd, batch_cmd, pivot_cmd

tests/
└── test_reports.py       # MODIFY — new metadata fixtures + assertions (see Testing Strategy)
```

No new files, no new dependencies, no config/auth changes — this is a pure `reports.py` rendering
change plus a JSON-shape change on two existing commands.

---

## Code Style

Follows existing `reports.py` conventions: `_`-prefixed module-level helpers, `.get()` with
defaults throughout (API fields are optional), `console.print` with a leading `\n[bold]...[/bold]`
header for table sections, `warn()`/`info()` for compact/non-table prose.

```python
_TRUNCATION_TYPE_PREFIX = "DATA_TRUNCATION_TYPE_"


def _humanize_truncation_type(raw: str) -> str:
    """DATA_TRUNCATION_TYPE_GOOGLE_ADS -> Google Ads."""
    stripped = raw.removeprefix(_TRUNCATION_TYPE_PREFIX)
    return stripped.replace("_", " ").title()


def _display_response_metadata(metadata: dict | None, effective_format: str) -> None:
    """Render sampling/thresholding/restriction/truncation notes, if present.

    A no-op when metadata is empty or absent, matching _display_quota()'s
    behavior for reports that don't trigger any of these conditions.
    """
    if not metadata:
        return

    lines: list[str] = []

    for reason in metadata.get("dataTruncationReasons", []):
        kind = _humanize_truncation_type(reason.get("dataTruncationType", ""))
        message = reason.get("dataTruncationMessage", "")
        date = reason.get("dataTruncationDate")
        suffix = f" (before {date})" if date else ""
        lines.append(f"Truncated ({kind}): {message}{suffix}")

    if metadata.get("subjectToThresholding"):
        lines.append("Subject to data thresholds — some low-volume data may be withheld.")

    for sm in metadata.get("samplingMetadatas", []):
        space = int(sm.get("samplingSpaceSize", 0) or 0)
        read = int(sm.get("samplesReadCount", 0) or 0)
        pct = f"{(read / space * 100):.1f}%" if space else "?"
        lines.append(f"Sampled: {read:,} of {space:,} events analyzed ({pct}).")

    for restriction in metadata.get("schemaRestrictionResponse", {}).get(
        "activeMetricRestrictions", []
    ):
        types = ", ".join(restriction.get("restrictedMetricTypes", []))
        lines.append(
            f"Metric '{restriction.get('metricName')}' restricted ({types}) — "
            "values withheld by your role."
        )

    if not lines:
        return

    if effective_format == "table":
        console.print("\n[bold]Data Notes[/bold]")
        for line in lines:
            console.print(f"  [yellow]![/yellow] {line}")
    elif effective_format == "compact":
        for line in lines:
            warn(line)
```

**Conventions this encodes:**
- `.get(..., [])` / `.get(..., {})` chains throughout — every `ResponseMetaData` field is
  optional, matching the defensive style already used for `dimensionHeaders`/`metricHeaders` in
  `_transform_report_rows`.
- Divide-by-zero guarded (`if space else "?"`) rather than assumed present, per `int64` fields
  arriving as strings from the JSON API (`NumericValue`-style string-encoded integers elsewhere
  in this schema family).
- No new Rich `Table` — a warnings list is prose, not tabular, unlike `_display_aggregations`.

---

## Testing Strategy

`pytest` + `typer.testing.CliRunner`, class-based grouping, all API calls mocked via
`unittest.mock.patch`, per existing `tests/test_reports.py` conventions. **No real API calls.**

New fixtures needed in `tests/test_reports.py`: a `SAMPLE_REPORT_RESPONSE_WITH_METADATA` (or
per-field variants) alongside the existing `SAMPLE_REPORT_RESPONSE`.

| Class | Cases |
|---|---|
| `TestResponseMetadataDisplay` | table mode: `dataTruncationReasons` renders one line per entry with type+message+date; `subjectToThresholding: true` renders its fixed line, `false`/absent renders nothing; `samplingMetadatas` renders a correct percentage, and handles `samplingSpaceSize: "0"` without a ZeroDivisionError; `activeMetricRestrictions` renders per-metric; empty/absent `metadata` renders **no** "Data Notes" section at all (regression guard against the always-on trigger from Design Decision 5) |
| `TestResponseMetadataJson` | `run -o json` returns `{"rows": [...], "metadata": {...}}` (not a bare array) — update the existing `test_run_json_output` assertion for the new envelope; `metadata` key present-but-empty (`{}`) when the API returns none; `build -o json`, `batch -o json`, `pivot -o json` already raw-passthrough — assert `metadata` key survives unchanged (regression guard, not new behavior) |
| `TestBatchPerReportMetadata` | two sub-reports, only the second has `dataTruncationReasons` — table output shows "Data Notes" attached to the second block only, not the first |
| `TestResponseMetadataCompact` | `-o compact` sends truncation/thresholding/sampling lines to stderr via `warn()`, stdout stays exactly the row-only output |

Also verify (no new test needed, but confirm during implementation): `test_run_default_metrics`
and other existing table-mode tests that use `SAMPLE_REPORT_RESPONSE` (no `metadata` key) still
pass unchanged — the no-op path must not alter output for responses that predate this field.

---

## Boundaries

**Always:**
- Run `pytest` and `ruff check src/ tests/` before committing.
- Mock every API call in tests; add fixtures rather than hitting a real property.
- Treat every `ResponseMetaData` sub-field as optional (`.get()` with a default), since GA4 only
  populates fields that apply to that specific report.
- Keep the "no metadata → no output" no-op guarantee — this must be silent for the overwhelming
  majority of reports that trigger none of these conditions.

**Ask first:**
- Adding `reports realtime` or `reports funnel` to this feature (both were scoped out above;
  realtime's response has no `metadata` field at all, funnel wasn't investigated).
- Any dependency addition (none should be needed — this is stdlib dict traversal + existing Rich
  console).
- Reformatting `_transform_report_rows`/`_transform_pivot_rows` beyond what's needed to thread
  `metadata` through — this spec's diff should stay additive.
- Bumping the version or tagging a release.

**Never:**
- Merge `metadata` fields into individual row dicts — it describes the whole report, not any one
  row, and must stay a sibling key (`{"rows": ..., "metadata": ...}`), not inlined per-row.
- Silently swallow the JSON shape change — the release notes/CHANGELOG must call out that
  `ga reports run -o json` and `ga reports build -o json` now return an object, not a bare array.
- Run `scripts/check_api_changes.py --update` as part of this work — the snapshots are already
  current (commit `5680e22`); re-running it is out of scope and risks picking up unrelated drift.

---

## Success Criteria

1. `ga reports run` against a sampled property (or a mocked response with `samplingMetadatas`)
   shows a "Data Notes" section with a correct percentage in table mode.
2. `ga reports run -o json` against the same mocked response returns
   `{"rows": [...], "metadata": {"samplingMetadatas": [...]}}`.
3. `ga reports run` against an unsampled, unrestricted, untruncated property shows **no** "Data
   Notes" section and JSON output has `"metadata": {}` — output for existing users is otherwise
   unchanged.
4. A mocked `dataTruncationReasons` response renders each reason as a separate, human-readable
   line including the truncation date when present.
5. `ga reports batch` with a two-report config where only one sub-report has metadata attaches
   the "Data Notes" section to the correct sub-report block.
6. `ga reports pivot -o json` and `ga reports batch -o json` continue to raw-passthrough
   `metadata` unchanged (no regression from this change, since they already did).
7. `pytest` and `ruff check src/ tests/` pass, including the new/updated cases in the table above.
8. `ga reports run --help` / `ga reports build --help` require no changes (no new flags) but the
   CHANGELOG documents the JSON shape change as breaking.

---

## Implementation Order

1. **Shared helper** — `_display_response_metadata()` + `_humanize_truncation_type()` in
   `reports.py`, unit-tested in isolation against hand-built `metadata` dicts covering each field
   and the empty case. *Verify:* `TestResponseMetadataDisplay`.
2. **Wire into `run_cmd`** — JSON envelope change + table-mode call. *Verify:*
   `TestResponseMetadataJson` (run cases), update `test_run_json_output`.
3. **Wire into `build_cmd`** — same pattern, reusing the helper. *Verify:* existing `build` tests
   still pass; add a JSON+table case.
4. **Wire into `batch_cmd`** — per-sub-report call inside the existing loop. *Verify:*
   `TestBatchPerReportMetadata`.
5. **Wire into `pivot_cmd`** — table-mode call only (JSON already passes through). *Verify:*
   pivot table-mode test with a mocked `metadata` key.
6. **Compact-mode pass + CHANGELOG entry** — `TestResponseMetadataCompact`; document the JSON
   breaking change. *Verify:* full `pytest` + `ruff check src/ tests/`.

Steps 2–5 are independent once step 1 lands (each touches a different command) and could be done
in any order or in parallel; step 6 depends on all of them.

---

## Open Questions — all resolved

1. ~~**`reports funnel` scope.**~~ **Resolved during planning:** the v1alpha snapshot shows
   `RunFunnelReportResponse` has no `metadata` field at all (`funnelVisualization`, `kind`,
   `propertyQuota`, `funnelTable`). Funnel is definitively out of scope.
2. ~~**Percentage formatting.**~~ **Resolved:** one decimal place (`3.5%`), no existing
   precedent to match.
3. ~~**CHANGELOG mechanics.**~~ **Resolved:** breaking-change note lives in README's
   "Output formats" section; the GitHub release notes carry it again at tag time. No
   `CHANGELOG.md` introduced.

## Implementation Notes (2026-09-18)

Deviations and findings recorded while implementing (`tasks/plan.md`, `tasks/todo.md`):

- **The live API populates `metadata` on every response** with `currencyCode` and `timeZone`
  (verified against a real property) — real-world `metadata` is never an empty dict. The
  no-op guarantee therefore rests on the helper's *rendered-lines* guard, not the empty-dict
  check; pinned by `test_currency_and_timezone_only_render_no_data_notes`.
- **`emptyReason` renders as a regular Data Notes line**, not the separate `info()` line this
  spec proposed — uniform with the other notes, and it composes naturally under the table
  renderer's existing "No results found." fallback, which stays untouched.
- **The Code Style sketch above under-escapes:** interpolating API text directly into a
  markup-styled `console.print` line would let a message containing `[bold]` be parsed as a
  style tag. The implementation wraps API-sourced text in `rich.markup.escape()`; pinned by
  `test_api_text_with_rich_markup_renders_literally`.
- Truncation-type humanization keeps words containing digits uppercase (`DV360`, `CM360`)
  rather than title-casing them into `Dv360`.
