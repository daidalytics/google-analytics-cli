# TODO: Output escaping and input validation fixes

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md) · branch `fix/escape-and-validation`

## Phase 1: High-impact fixes
- [ ] T1 Table output renders report values literally (issue 1). *In progress: tests written*
- [ ] T2 Message helpers print API text literally (issue 4 + `handle_error`)
- [ ] T3 Filter values may contain operator symbols (issue 2)
- [ ] **Checkpoint A:** suite + ruff green, live smoke on 250400352, human review

## Phase 2: Consistency and validation
- [ ] T4 `ga auth status` follows the pipe default (issue 3)
- [ ] T5 Reject extra `--order-by` segments (issue 5)
- [ ] T6 Bound `reports run --limit` to 1..250,000 (issue 6)
- [ ] **Checkpoint B:** suite + ruff green

## Phase 3: Release prep
- [ ] T7 Refresh API snapshots (re-check first, stop on semantic changes)
- [ ] T8 Agent guide Filters note; SPEC status → implemented
- [ ] T9 Push, open PR, CI green. **Merge only on the human's go**
- [ ] **Checkpoint: complete**
