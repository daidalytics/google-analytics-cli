# TODO: Output escaping and input validation fixes

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md) · branch `fix/escape-and-validation`

## Phase 1: High-impact fixes
- [x] T1 Table output renders report values literally (issue 1). `90d9b07`
- [x] T2 Message helpers print API text literally (issue 4 + `handle_error`). `480babc`
- [x] T3 Filter values may contain operator symbols (issue 2). `433c09d`
- [x] **Checkpoint A:** suite + ruff green (1089 passed) · live on 250400352 · reviewed.
      Real data has no values that trigger issues 1/2 (no `[tag]`-style brackets, no `>`/`<`/`==`/`!=`
      in 17 text dims); covered by unit tests. MP test hits declined.

## Phase 2: Consistency and validation
- [x] T4 `ga auth status` follows the pipe default (issue 3). `21e41d3`
- [x] T5 Reject extra `--order-by` segments (issue 5). `2b8f80c`
- [x] T6 Bound `reports run --limit` to 1..250,000 (issue 6). `045daa2`
- [x] **Checkpoint B:** suite + ruff green (1099 passed); live on 250400352 for T4–T6

## Phase 3: Release prep
- [x] T7 Refresh API snapshots (re-check first, stop on semantic changes). `54e77fc`
      Revision bumps + reworded EmptyFilter descriptions only (CLI doesn't use emptyFilter)
- [x] T8 Agent guide Filters note; SPEC status → implemented
- [ ] T9 Push, open PR, CI green. **Merge only on the human's go**
- [ ] **Checkpoint: complete**
