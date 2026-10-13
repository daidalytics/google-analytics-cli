# Implementation Plan: Output escaping and input validation fixes

Companion to [SPEC.md](../SPEC.md). Branch `fix/escape-and-validation`, one PR, one commit per
task. Ships in 0.5.0. Previous plan (ResponseMetaData): `git show 72e3a4f:tasks/plan.md`.

## Overview

Fix six bugs plus an API snapshot refresh. Two bugs change or break output for real-world
data: Rich markup in table values (1) and filter operator precedence (2). One root cause,
untrusted API text reaching Rich unescaped, covers issues 1 and 4. The rest are small and
independent.

## Architecture decisions

- **Escape at the Rich boundary, in `utils/output.py`.** Cells, headers and object keys are
  escaped in the renderer. The message helpers (`success`/`error`/`warn`/`info`) escape
  `message` themselves, which also protects `handle_error()`. None of the 101 helper call
  sites passes intentional markup. The CLI's own markup (boolean Yes/No) is added after
  escaping.
- **`rich.markup.escape`, not `Text` objects.** `reports.py` already uses it, it leaves
  non-tag brackets like `[3 items]` untouched, and it keeps `_format_value` returning `str`.
- **Filters: match the field name first, then the operator right after it.** The field must
  match `[A-Za-z][A-Za-z0-9_]*(:[A-Za-z0-9_]+)*`, which the user confirmed covers every field
  in use. Output dicts and #29's metric rules are unchanged.
- **Validation via Typer (`min`/`max`)** where possible, so errors are usage errors (exit 2)
  raised before any API call, matching pivot.

## Dependency graph

```
utils/output.py ── T1 table escaping ──► T2 message-helper escaping  (same file: sequential)
utils/filters.py ─ T3 filter parser ───► T5 order-by segments        (same file: sequential)
commands/auth_cmd.py ─ T4                                            (independent)
commands/reports.py ── T6                                            (independent)
.api-snapshots/ ────── T7                                            (independent)
                           all ──► T8 docs/spec ──► T9 PR
```

The two high-risk, high-value fixes come first (T1–T3) so problems show up early.

## Task list

### Phase 1: High-impact fixes

#### Task 1: Table output renders report values literally (issue 1)
**Status:** in progress. 8 tests written and failing. `escape` is imported and headers are
escaped; `_format_value` and object keys are still to do.

**Acceptance criteria:**
- [ ] `/search?q=[foo]bar` renders as is; `Docs [/admin] x` renders without `MarkupError`
- [ ] Bracketed pivot headers and dict values render literally; booleans keep their green/red
- [ ] `_format_value` output is unchanged for values without brackets (`[3 items]`, `[]`, JSON)

**Verification:** `uv run pytest tests/test_output.py -q -k TableMarkupEscaping`, then the
full `tests/test_output.py`

**Files:** `src/ga_cli/utils/output.py`, `tests/test_output.py` · **Scope:** S · **Deps:** none

#### Task 2: Messages print API text literally (issue 4, plus `handle_error`)
**Acceptance criteria:**
- [ ] `warn`/`error`/`info`/`success` print `[/x]` and `[foo]` literally, without raising
- [ ] `reports run -o compact` with a data note containing `[/docs]` exits 0, and the note
      is on stderr verbatim
- [ ] In terminal mode, an API error whose message contains `[/x]` prints a clean
      `Error:` line with exit code 3, not a traceback

**Verification:** `uv run pytest tests/test_output.py tests/test_reports.py tests/test_errors*.py -q`

**Files:** `src/ga_cli/utils/output.py`, `src/ga_cli/commands/reports.py` (comment only),
`tests/test_output.py`, `tests/test_reports.py` · **Scope:** S · **Deps:** T1 (same file)

#### Task 3: Filter values may contain operator symbols (issue 2)
**Acceptance criteria:**
- [ ] Every row of SPEC's issue 2 table parses as specified: `contains Home > Blog`,
      `contains a != b`, `begins_with /a==b`, `in A<B,C`, `==A > B`, `customEvent:plan==pro`
- [ ] `page title==x` and `nosuchop` raise `BadParameter` listing the operators
- [ ] All existing `TestParseSingleFilter`/`TestParseMetricFilters` tests pass unchanged,
      including `"  country == US  "` and case-insensitive `CONTAINS`

**Verification:** `uv run pytest tests/test_filters.py -q`; `ga reports build` still works,
since its expressions are `field + op + value`

**Files:** `src/ga_cli/utils/filters.py`, `tests/test_filters.py` · **Scope:** S · **Deps:** none

### Checkpoint A: high-impact fixes
- [ ] `uv run pytest` and `uv run ruff check src/ tests/` pass
- [ ] Live on 250400352: `--dim-filter 'pageTitle contains >'` (or a real title with `>`)
      runs without a parse error; `-o table` reports render normally
- [ ] Live data notes: `--start-date 2015-08-14 --end-date 2016-12-31 -o compact` on 250400352
      gives a real DATE_RANGE truncation note on stderr, printed verbatim
- [ ] Three commits on the branch (T1, T2, T3)
- [ ] **Review with the human before Phase 2**

### Phase 2: Consistency and validation

#### Task 4: `ga auth status` follows the pipe default (issue 3)
**Acceptance criteria:**
- [ ] `-o` defaults to `None` and goes through `resolve_output_format()`
- [ ] Piped (CliRunner, not a TTY) with no `-o`: stdout is valid JSON with `authenticated`
- [ ] `-o table` still gives a table; terminal default unchanged

**Verification:** `uv run pytest tests/test_auth_cmd.py -q`; live `ga auth status | jq .authenticated`

**Files:** `src/ga_cli/commands/auth_cmd.py`, `tests/test_auth_cmd.py` · **Scope:** XS · **Deps:** none

#### Task 5: Reject extra `--order-by` segments (issue 5)
**Acceptance criteria:**
- [ ] `country:asc:alpha:bogus` raises `BadParameter` naming the expression and the format
- [ ] Colon field names still work: `customEvent:plan_type:asc:ialpha` is accepted
      (4 parts, the field takes 2)

**Verification:** `uv run pytest tests/test_filters.py -q -k OrderBy`

**Files:** `src/ga_cli/utils/filters.py`, `tests/test_filters.py` · **Scope:** XS · **Deps:** T3 (same file)

#### Task 6: Bound `reports run --limit` (issue 6)
**Acceptance criteria:**
- [ ] `--limit 0` and `--limit -5` exit 2 with a usage error and make no API call
- [ ] `--limit 250000` is accepted; `250001` exits 2
- [ ] `--describe` still shows `limit` as `integer` (`IntRange`, covered since #28)

**Verification:** `uv run pytest tests/test_reports.py tests/test_describe.py -q`

**Files:** `src/ga_cli/commands/reports.py`, `tests/test_reports.py` · **Scope:** XS · **Deps:** none

### Checkpoint B: all six issues
- [ ] Full suite and ruff pass
- [ ] Six fix commits on the branch

### Phase 3: Release prep

#### Task 7: Refresh API snapshots
**Acceptance criteria:**
- [ ] Re-run `python3 scripts/check_api_changes.py` first. If it shows only revision bumps,
      run it with `--update`; if it shows semantic changes, stop and report them
- [ ] A re-check afterwards reports no changes
- [ ] Separate `chore:` commit containing only `.api-snapshots/`

**Files:** `.api-snapshots/*.json` · **Scope:** XS · **Deps:** none

#### Task 8: Docs and spec status
**Acceptance criteria:**
- [ ] Agent guide's Filters section says values may contain operator symbols (one line);
      no other doc claims change
- [ ] SPEC.md status set to "Implemented: pending release"; `tasks/todo.md` all checked

**Files:** `src/ga_cli/commands/agent_cmd.py`, `SPEC.md`, `tasks/todo.md` · **Scope:** XS · **Deps:** T1–T7

#### Task 9: Open the PR
**Acceptance criteria:**
- [ ] Branch pushed and PR opened against master, with each commit mapped to a spec issue
- [ ] CI is green on 3.10, 3.12 and 3.13
- [ ] **Merge only after the human says so**

**Deps:** T8

### Checkpoint: complete
- [ ] All SPEC success criteria (1–6) met
- [ ] PR green and ready for review

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| A caller relies on markup passing through a message helper | Med | Checked all 101 call sites: none do. T2 tests cover each helper |
| Double escaping (`\[` visible) where text is already escaped | Low | Only `_display_response_metadata`'s table branch escapes, and it calls `console.print`, not a helper |
| Field-name regex rejects a valid field | Med | User confirmed the grammar; error message lists operators so it's diagnosable |
| `escape()` changes `_format_value` strings compared in existing tests | Low | Rich only escapes tag-like brackets; existing `TestFormatValue` must pass unchanged |
| Snapshot gains semantic changes before T7 | Low | T7 re-checks first and stops on semantic changes |

## Open questions

None. Spec decisions are recorded in SPEC.md.
