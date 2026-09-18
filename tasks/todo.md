# TODO: Surface `ResponseMetaData` in report commands

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md)

## Phase 1 — Core slice (`reports run`)

- [x] **T1 · `_display_response_metadata()` helper + `run` table/compact display** — M · `71cf37d`
- [x] **T2 · `run` + `build` JSON envelope `{rows, metadata}` (breaking change, isolated commit)** — S · `444490d`

- [x] **CHECKPOINT** — 987 tests green · ruff clean · live smoke on `250400352` passed:
      table output unchanged, JSON returns the envelope · regression test added (`b2d2988`)
      for a live finding: **the API returns `currencyCode`/`timeZone` in `metadata` on every
      response** — real-world `metadata` is never empty; the helper's empty-`lines` guard
      (not the empty-dict check) carries the no-op guarantee · human review: pending

## Phase 2 — Remaining commands

- [x] **T3 · `build` table/compact wiring** — S · `3fb35b5`
- [x] **T4 · `batch` per-sub-report metadata (table mode) + JSON regression guard** — S · `38bc9c1`
- [x] **T5 · `pivot` table-mode metadata + JSON regression guard** — S · `6093877`

- [x] **CHECKPOINT** — 995 tests green · ruff clean · SPEC Success Criteria 1–6 each covered
      by a named test · realtime/funnel untouched (their tests unchanged)

## Phase 3 — Docs

- [x] **T6 · README breaking-change note · agent-guide shape check · SPEC.md living updates
      (status → Implemented, Open Q1–Q3 resolved)** — S
      · found + fixed a stale jq recipe in the agent guide (`.[]` → `.rows[]`)

- [x] **FINAL** — 995 tests green · ruff clean · version bump/release NOT performed (ask
      first) · `.api-snapshots/` untouched

---

## Decisions to make

- [x] **Open Q (plan §1):** breaking-change note → README "Output formats" section (done);
      repeat it in the GitHub release notes at tag time (pending release).

## Decisions already made (from spec review + planning)

- [x] Full `ResponseMetaData` scope, not just `dataTruncationReasons`
- [x] JSON envelope `{rows, metadata}` for `run`/`build` — accepted breaking change
- [x] Automatic display, no new flag
- [x] Commands: `run`, `build`, `batch`, `pivot` · realtime excluded (no `metadata` field) ·
      **funnel excluded** (snapshot-confirmed during planning: `RunFunnelReportResponse` has no
      `metadata` field — resolves SPEC Open Q1)
- [x] Sampling percentage: one decimal place (resolves SPEC Open Q2)
- [x] API-sourced text markup-escaped inside styled lines (corrects the SPEC Code Style sketch)

## Carry-over notes from the chat cycle

- `click` 8.3: `Result.output` merges stdout **and** stderr — assert on `Result.stdout` when
  verifying a stream stays pipeable (matters for T1's compact-mode tests).
- Live-test property `250400352` has no revenue tracking — use `sessions`/`activeUsers`.
