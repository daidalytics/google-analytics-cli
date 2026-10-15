# TODO: Agent distribution, named profiles, and audience exports

> **Shipped in 0.6.0 (2026-10-14)** via #35 (lanes A + B) and #36 (lane C). #37 then corrected the ADC login that B/D1 had specified. Remaining items are under [Follow-ups](#follow-ups).
>
> **2026-10-14:** all lanes rebased onto `origin/master` v0.5.0 (`225822f`). They had been cut from a stale local `master` (0.4.0). Pre-rebase state is kept in `backup/pre-rebase-0.5.0/*`.

Task detail in [plan.md](plan.md) · design in [SPEC.md](../SPEC.md) · baseline 997 tests green

Legend: `∥` = runs in parallel with its siblings, each in its own worktree agent.

## Wave 0 (orchestrator)

- [x] Resolve Q1 → root-only `--profile`; Q2 → suppress the notice under uvx (O1 runs in wave 1)
- [x] Commit SPEC.md + `tasks/`; cut `feat/agent-distribution`, `feat/profiles`, `feat/audience-exports`
- [x] Edit `CLAUDE.md` (local, gitignored): fix the auth-priority line; add `plugin.json` to the release steps

## Wave 1 (6 agents in parallel)

- [x] ∥ **A1** · Console-script alias + plugin manifests + version-sync test (S) · `58a8324`
- [x] ∥ **A2 → A3** · `build_cli_schema()` (XS) → skill in repo + generator + guard tests (M) (one agent) · `bb3a7b8` `46caed5`
      · the draft's 35 commands all exist; short-flag table had 4 corrections
- [x] ∥ **A4** · README "Use with AI agents" section (XS) · `f73928d`
- [x] ∥ **B1** · Profile foundation: selection, paths, implicit creation, conftest (M) · `25eb01b` (lane B)
      · invalid name → exit 1 (not Click's 2); explicit `--profile ""` rejected; config cache keyed by path
- [x] ∥ **C1 → C2 → C3** · audience-exports list/get (S) → query (S) → create + `--dry-run` + `--wait` (M) (one long-running agent) · `3eaf1f2` `0087858` `e46a16a` (lane C)
- [x] ∥ **O1** · Suppress the update notice under an ephemeral uvx env (XS) (approved; lane A) · `07129e8`

- [x] **CHECKPOINT A**: merge A1–A4 · `uv build` + uvx wheel smoke test · `claude plugin validate .` · `npx skills add ./ --list` · review agent · **human review → PR A, decide on 0.4.1**
      - [x] merged; 1070 tests green; ruff clean; drift check clean
      - [x] uvx from the built wheel → `ga-cli 0.4.0`; `claude plugin validate` passes (only warning: local gitignored CLAUDE.md)
      - [x] `npx skills add ./ --list` initially found **no skills**: the unquoted `: ` in the SKILL.md description broke strict YAML → fixed + regression test (`f5e9cd4`); now lists `ga-cli`
      - [x] review agent: no correctness issues; one README duplication finding judged acceptable (one uvx form, shown in agents section + install list); CI doesn't lint `scripts/` (follow-up, ask-first)
      - [x] human review → no separate PR A or 0.4.1; lane A shipped with lane B in #35 (0.6.0)

## Wave 2 (after B1 is merged into `feat/profiles`)

- [x] ∥ **B2** · Credential resolution table + ADC fallback + `ProfileNotFoundError` (M)
      · guard-removal check: each safety guard removed → 1–10 tests fail; ADC tripwire run → 0 real ADC hits
- [x] ∥ **B3** · `ga profiles list` / `delete` (S) · `c9629a1` (lane B)

## Wave 3

- [x] **B4** · `auth status` profile/adc · `config path` · ADC scope hint (M)
      · fixed: status misreported env-var SA under named profiles / non-SA GAC; a missing key file was shown as authenticated

- [x] **CHECKPOINT B**: merge B1–B4 · live default-profile parity on `250400352` · SA profile · `--profile typo` → exit 2 · ADC (human) · review agent · **human review**
      - [x] merged; 1213 tests on lane; review agent: no issues ≥80 confidence (invariant, traversal, compat, perms, exit codes, test isolation)
      - [x] live (real config): `profiles list` offline · `--profile clinet-a` → exit 2 before any API call · `../x` → exit 1 · `auth status` = default/oauth · default-profile parity: `account-summaries list` byte-identical vs pre-profiles code
      - [x] live ADC: tested by the human. It found that Google blocks gcloud's built-in client for the Analytics scopes, which was fixed in #37
      - [ ] live SA-keyed named profile: not recorded (see Follow-ups)
      - [x] human review → #35 merged
- [x] **CHECKPOINT C**: merge C1–C3 · live list/get/query · live create **ask-first** (resolves Q3) · review agent · **human review**
      - [x] merged; review agent: clean (no issues ≥80 confidence)
      - [ ] live list/get/query: not recorded (the stored login has no access to `250400352`; see Follow-ups)
      - [ ] live create (ask-first) → would confirm SPEC Q3 (see Follow-ups)
      - [x] human review → #36 merged

## Wave 4

- [x] ∥ **D1** · Profiles + ADC in SKILL.md / README; regenerate reference (S) · behaviour checked by running the CLI against a scratch config
- [x] ∥ **D2** · Audience exports in SKILL.md / recipes / README; regenerate reference (S)

- [x] **FINAL CHECKPOINT**
      - [x] trial merge of all three lanes on 0.5.0: no conflicts, 1445 tests, drift check clean, ruff clean
      - [x] #35 and #36 green on CI and merged; v0.6.0 released (release workflow success; PyPI 0.6.0)
      - [x] published artifacts checked live: `uvx google-analytics-cli --version` → `ga-cli 0.6.0` from PyPI; `npx skills add daidalytics/google-analytics-cli --list` → `ga-cli`
      - [x] SPEC.md living updates: status shipped; ADC login corrected per #37
      - [ ] Success Criteria 1–15 not formally mapped to tests (each workstream's tasks cover them; not tabulated)

## Follow-ups

- [ ] Live SA-keyed named profile end to end (e.g. `ga --profile personal auth login --service-account KEY`)
- [ ] Live `audience-exports list/get/query` on a test property, and one live `create` (charges quota, ask first) to settle SPEC Q3 (does the v1beta `Operation.response.name` carry the export name?)
- [ ] CI doesn't lint `scripts/` (`ruff check src/ tests/` only), so `scripts/gen_skill_reference.py` isn't linted in CI
- [ ] `~/.claude/skills-dev/ga-cli/SKILL.md` (the author's draft) still has the unquoted-`: ` description that breaks strict YAML
- [ ] SPEC Q4: `ga agent guide` and the skill are two hand-maintained agent references

