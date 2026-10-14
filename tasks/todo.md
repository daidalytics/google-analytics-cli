# TODO: Agent distribution, named profiles, and audience exports

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md) · baseline 997 tests green

Legend: `∥` = runs in parallel with its siblings, each in its own worktree agent.

## Wave 0 (orchestrator)

- [x] Resolve Q1 → root-only `--profile`; Q2 → suppress the notice under uvx (O1 runs in wave 1)
- [x] Commit SPEC.md + `tasks/`; cut `feat/agent-distribution`, `feat/profiles`, `feat/audience-exports`
- [x] Edit `CLAUDE.md` (local, gitignored): fix the auth-priority line; add `plugin.json` to the release steps

## Wave 1 (6 agents in parallel)

- [ ] ∥ **A1** · Console-script alias + plugin manifests + version-sync test (S)
- [ ] ∥ **A2 → A3** · `build_cli_schema()` (XS) → skill in repo + generator + guard tests (M) (one agent)
- [ ] ∥ **A4** · README "Use with AI agents" section (XS)
- [ ] ∥ **B1** · Profile foundation: selection, paths, implicit creation, conftest (M)
- [ ] ∥ **C1 → C2 → C3** · audience-exports list/get (S) → query (S) → create + `--dry-run` + `--wait` (M) (one long-running agent)
- [ ] ∥ **O1** · Suppress the update notice under an ephemeral uvx env (XS) (approved; lane A)

- [ ] **CHECKPOINT A**: merge A1–A4 · `uv build` + uvx wheel smoke test · `claude plugin validate .` · `npx skills add ./ --list` · review agent · **human review → PR A, decide on 0.4.1**

## Wave 2 (after B1 is merged into `feat/profiles`)

- [ ] ∥ **B2** · Credential resolution table + ADC fallback + `ProfileNotFoundError` (M)
- [ ] ∥ **B3** · `ga profiles list` / `delete` (S)

## Wave 3

- [ ] **B4** · `auth status` profile/adc · `config path` · ADC scope hint (M)

- [ ] **CHECKPOINT B**: merge B1–B4 · live default-profile parity on `250400352` · SA profile · `--profile typo` → exit 2 · ADC (human) · review agent · **human review**
- [ ] **CHECKPOINT C**: merge C1–C3 · live list/get/query · live create **ask-first** (resolves Q3) · review agent · **human review**

## Wave 4 (after PR A is on `master`; rebase B and C lanes onto it)

- [ ] ∥ **D1** · Profiles + ADC in SKILL.md / README; regenerate reference (S)
- [ ] ∥ **D2** · Audience exports in SKILL.md / recipes / README; regenerate reference (S)

- [ ] **FINAL CHECKPOINT**: PRs B + C green on CI · second merge regenerates `commands.md` · Success Criteria 1–15 mapped · SPEC.md living updates · **ask about the 0.5.0 bump** (`pyproject.toml` + `plugin.json`)

