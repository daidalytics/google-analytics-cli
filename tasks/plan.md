# Implementation Plan: Surface `ResponseMetaData` in report commands

Companion to [SPEC.md](../SPEC.md). API revision `20260909`, snapshots already current (`5680e22`).

## Overview

Wire the GA4 Data API's `ResponseMetaData` object — sampling, thresholding, schema restrictions,
empty-report reasons, and the new `dataTruncationReasons` — into `reports run`, `build`, `batch`,
and `pivot`. Today it is silently discarded by `run`/`build` in every output format, and shown
nowhere in `batch`/`pivot` table mode. One shared rendering helper; automatic display (no new
flags); one deliberate breaking change to `run`/`build` JSON output (`{rows, metadata}` envelope
replacing the bare rows array).

**Constraint that shapes verification:** sampling, truncation, and thresholding cannot be forced
on demand against a live property, so behavior is verified by mock-based tests (the project norm —
every API call mocked). The live checks we *can* run are the no-op path (a normal report's output
must be unchanged in table mode) and the JSON envelope shape. Because `-o json` passes `metadata`
through losslessly, any real-world response that does trigger these conditions can validate the
renderer after the fact.

## Architecture Decisions

1. **One helper, prose not tables.** `_display_response_metadata()` in `reports.py`, shaped like
   `_display_quota()`: a strict no-op when the API returned nothing noteworthy. Warnings render as
   a "Data Notes" line list, not a Rich table — these are annotations about the report, not data.

2. **The JSON breaking change is isolated in its own task/commit.** `run`/`build` `-o json` moves
   from a bare rows array to `{"rows": [...], "metadata": {...}}`. Keeping that diff separate from
   the (additive) display work makes it individually revertable and reviewable, and gives the
   release notes one commit to point at. `batch`/`pivot` JSON already passes the raw response
   through — no change there.

3. **API-sourced text must be markup-escaped.** `dataTruncationMessage` is server-provided prose
   printed via `console.print` inside Rich markup (`[yellow]![/yellow] {line}`). A message
   containing `[` would be parsed as a style tag — the exact failure `chat` guards against with
   `markup=False` (`reports.py:1046`). Here the prefix *is* markup, so escape the API text with
   `rich.markup.escape()` instead. This corrects the sketch in SPEC.md's Code Style section, which
   has this bug.

4. **`emptyReason` lives in the helper; `output()` is untouched.** SPEC's "replaces the current
   unconditional 'No results found.'" is implemented as: the helper emits one `info()` line with
   the API's reason; the shared `output()` fallback stays as-is (SPEC Boundaries: shared helpers
   are ask-first).

5. **Funnel confirmed out of scope** — resolves SPEC Open Question 1. The v1alpha snapshot shows
   `RunFunnelReportResponse` has no `metadata` field (`funnelVisualization`, `kind`,
   `propertyQuota`, `funnelTable` only). Recorded in SPEC.md during T6.

6. **Sampling percentage: one decimal place** (`3.5%`) — resolves SPEC Open Question 2. No
   existing percent-formatting precedent in the CLI; one decimal balances precision against noise.
   `int64` fields arrive as JSON strings — convert with `int()` and guard
   `samplingSpaceSize == 0`.

## Dependency Graph

```
T1  helper (_display_response_metadata) + `run` table/compact wiring
 │        — first complete user-visible slice
 ├── T2  `run` + `build` JSON envelope {rows, metadata}   ← the breaking change, isolated
 ├── T3  `build` table/compact wiring
 ├── T4  `batch` per-sub-report wiring (table mode)
 └── T5  `pivot` wiring (table mode)
          │
          └── T6  docs: README breaking-change note, SPEC.md living-doc updates
```

T2–T5 are independent of each other but **all edit `reports.py`** — run them sequentially in one
session; there is no useful parallelization in this feature.

---

## Task List

### Phase 1: Core slice — `reports run`

---

## Task 1: Rendering helper + `run` table/compact display

**Description:** The first complete path: a user running `ga reports run` in table mode sees a
"Data Notes" section whenever the API reports truncation, thresholding, sampling, restrictions,
or an empty-reason — and sees nothing new otherwise. Adds `_humanize_truncation_type()` and
`_display_response_metadata()` (per SPEC Code Style, corrected to escape API text per Decision 3),
and calls it from `run_cmd` after the existing quota display. Compact mode sends the same lines to
stderr via `warn()`/`info()` so stdout stays pipeable.

**Acceptance criteria:**
- [ ] Each `metadata` field renders per SPEC's rules: one line per truncation reason (type
      humanized, message, `(before DATE)` when present), fixed thresholding line only when `true`,
      sampling percentage with zero-guard, one line per restricted metric, `emptyReason` via
      `info()`
- [ ] Absent or empty `metadata` produces **no** "Data Notes" output at all; existing table-mode
      tests using `SAMPLE_REPORT_RESPONSE` (no `metadata` key) pass unchanged
- [ ] A `dataTruncationMessage` containing Rich markup (e.g. `[bold]`) renders literally, styled
      prefix intact
- [ ] Compact mode: notes go to stderr, stdout is row-only (assert via `Result.stdout` —
      `Result.output` merges streams under click 8.3)

**Verification:**
- [ ] `pytest tests/test_reports.py -k "MetadataDisplay or MetadataCompact" -v`
- [ ] `pytest tests/test_reports.py` — full file green (no regressions)
- [ ] `ruff check src/ tests/`

**Dependencies:** None
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports.py`
**Scope:** M

---

## Task 2: `run` + `build` JSON envelope — the breaking change

**Description:** `run_cmd` and `build_cmd` `-o json` currently print the transformed rows as a
bare array, discarding metadata entirely. Both switch to
`{"rows": [...], "metadata": {...}}` — `metadata` present even when empty (`{}`), so consumers
get a stable shape. Table/compact paths are untouched by this task. Deliberately one commit so
the breaking diff is isolated (Decision 2).

**Acceptance criteria:**
- [ ] `run -o json` and `build -o json` emit a top-level object with exactly `rows` and
      `metadata` keys; `rows` content is unchanged from the previous array
- [ ] `metadata` carries the API's object verbatim when present, `{}` when absent
- [ ] Existing `test_run_json_output` updated for the envelope; no other JSON-consuming test
      regresses

**Verification:**
- [ ] `pytest tests/test_reports.py -k "json or Json" -v`
- [ ] `pytest` — full suite green
- [ ] Manual: `ga reports run -p <id> -m sessions -o json | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d))"` prints `['metadata', 'rows']`

**Dependencies:** Task 1 (shares fixtures)
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports.py`
**Scope:** S

---

### Checkpoint: Core slice
- [ ] Full `pytest` green, `ruff check src/ tests/` clean
- [ ] Live smoke on property `250400352` (use `sessions`/`activeUsers` — no revenue tracking
      there): table output of a normal report is byte-identical in spirit to pre-change (no
      "Data Notes"), JSON returns the envelope
- [ ] Review with human — the breaking change is now real; last cheap moment to reverse it

---

### Phase 2: Remaining commands

---

## Task 3: `build` table/compact display

**Description:** `build_cmd` runs the same `runReport` call as `run_cmd`; wire the same
`_display_response_metadata()` call into its result path (after its `_display_quota` call), making
the interactive builder's output consistent with `run`.

**Acceptance criteria:**
- [ ] `build` table mode renders "Data Notes" from a mocked `metadata` response; nothing when
      absent
- [ ] Existing `build` tests pass unchanged

**Verification:**
- [ ] `pytest tests/test_reports.py -k "build or Build" -v`
- [ ] `ruff check src/ tests/`

**Dependencies:** Task 1
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports.py`
**Scope:** S

---

## Task 4: `batch` — per-sub-report metadata

**Description:** Each entry in `BatchRunReportsResponse.reports` is a full `RunReportResponse`
with its own `metadata` (confirmed against the snapshot). In table mode, call the helper inside
the existing per-report loop, right after the sub-report's row-count line (`reports.py:808`), so
notes attach visibly to the sub-report they describe. JSON mode already passes the raw response
through — add a regression assertion only.

**Acceptance criteria:**
- [ ] Two-sub-report config where only the second has `dataTruncationReasons`: "Data Notes"
      appears under the second `--- Report N ---` block only
- [ ] `batch -o json` raw passthrough still includes each sub-report's `metadata` (regression
      guard, no behavior change)

**Verification:**
- [ ] `pytest tests/test_reports.py -k "Batch" -v` (or the batch test file/class as organized)
- [ ] `ruff check src/ tests/`

**Dependencies:** Task 1
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports.py`
**Scope:** S

---

## Task 5: `pivot` — table-mode metadata

**Description:** `RunPivotReportResponse.metadata` `$ref`s the same `ResponseMetaData`. Call the
helper in `pivot_cmd`'s table-mode branch after the pivot rows render. JSON mode already raw-
passes the response — regression assertion only.

**Acceptance criteria:**
- [ ] `pivot` table mode renders "Data Notes" from a mocked `metadata`; nothing when absent
- [ ] `pivot -o json` passthrough still includes `metadata` (regression guard)

**Verification:**
- [ ] `pytest tests/test_reports.py -k "Pivot" -v` (or wherever pivot tests live)
- [ ] `ruff check src/ tests/`

**Dependencies:** Task 1
**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports.py`
**Scope:** S

---

### Checkpoint: All commands wired
- [ ] Full `pytest` green, `ruff` clean
- [ ] Every SPEC Success Criterion 1–6 demonstrably met by a named test
- [ ] `reports realtime` and `reports funnel` behavior untouched (their tests unchanged)

---

### Phase 3: Documentation

---

## Task 6: Docs + SPEC living-document updates

**Description:** Record the breaking change where users will find it, and close the spec's open
questions. Check whether `ga agent guide` (`agent_cmd.py`) documents `run`'s JSON output shape —
if it claims a bare array, correct it; agents are the primary `-o json` consumers.

**Acceptance criteria:**
- [ ] README documents the `{rows, metadata}` JSON shape for `run`/`build` and the "Data Notes"
      behavior; breaking change called out for the next release's notes
- [ ] `agent_cmd.py` guide checked for stale JSON-shape claims and corrected if any
      (`ga agent guide` output greps clean)
- [ ] SPEC.md updated: status → Implemented, Open Q1 resolved (funnel has no `metadata` field),
      Open Q2 resolved (one decimal place), Open Q3 resolved per the human's call on where the
      breaking-change note lives
- [ ] tasks/todo.md checkpoints filled in with final test counts and commit hashes

**Verification:**
- [ ] `pytest` full suite, `ruff check src/ tests/`
- [ ] `ga agent guide | grep -A3 -i "reports run"` shows the new shape (if the guide covers it)

**Dependencies:** Tasks 1–5
**Files:** `README.md`, `SPEC.md`, `src/ga_cli/commands/agent_cmd.py` (conditionally),
`tasks/todo.md`
**Scope:** S

---

### Checkpoint: Ready for review
- [ ] All acceptance criteria met, `pytest` and `ruff` green
- [ ] Version bump and release **not** performed — ask first (SPEC Boundaries)
- [ ] `.api-snapshots/` untouched; `scripts/check_api_changes.py --update` **not** run
      (snapshots already at rev `20260909`)

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| JSON shape change breaks existing scripts parsing `run`/`build` output as a bare array | **High** | Isolated in T2's single commit; stable envelope (`metadata` always present); README + release-note callout (T6); human checkpoint immediately after T2 |
| Rich markup injection from API-sourced `dataTruncationMessage` | **Med** | `rich.markup.escape()` on all API text inside styled lines (Decision 3); explicit test with `[bold]` in the fixture |
| Cannot trigger sampling/truncation/thresholding live to validate rendering | **Med** | Mock-first per project norm; JSON passthrough is lossless, so a real triggering response can validate the renderer later — same strategy that worked for `chat` |
| Always-on display leaks new lines into scripted table/compact pipelines | **Med** | Compact sends notes to **stderr** (suppressed by `--quiet` via `warn()`/`info()`); table mode is human-facing; explicit `Result.stdout` assertions |
| `int64`-as-string arithmetic (`samplingSpaceSize`) → `TypeError`/`ZeroDivisionError` | **Low** | `int()` conversion + zero-guard in the helper; dedicated test with `"0"` |
| `click` 8.3 `Result.output` merges stdout+stderr, masking stream regressions | **Low** | Known from the chat cycle — assert on `Result.stdout` wherever stream separation matters |
| Helper drifts from `batch`/`pivot` response nuances | **Low** | Both `$ref` the identical `ResponseMetaData` schema — verified against the snapshot before planning |

## Parallelization

None worth taking: every task edits `reports.py`. T3/T4/T5 are logically independent after T1 but
should land sequentially to avoid same-file conflicts. Single session, T1→T6 in order.

## Open Questions

1. **Where does the breaking-change note live?** (SPEC Open Q3.) No `CHANGELOG.md` exists.
   Recommendation: a short "Breaking changes" note in README's reports section now, plus the
   GitHub release notes at tag time. Decide at T6 — does not block T1–T5.
2. **Does `ga agent guide` document `run -o json`'s current bare-array shape?** Unchecked;
   resolved by inspection during T6.
