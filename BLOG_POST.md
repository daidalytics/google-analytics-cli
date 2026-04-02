# Blog Post Outline: Announcing GA CLI

## 1. Introduction / Hook
- The GA4 UI is great for exploration, but breaks down at scale (many properties, repetitive config, reporting pipelines)
- Introduce GA CLI: a command-line interface for Google Analytics 4
- Inspiration: the GTM CLI (`@owntag/gtm-cli`) by Justus Blümer / owntag — an open-source CLI wrapping the GTM API, built in TypeScript/Deno, explicitly designed with AI agents as a first-class user (ships `gtm agent guide`, auto-JSON when piped). It proved that a CLI for Google Marketing Platform tools is valuable and that agent-readiness is a killer feature. GA CLI brings the same philosophy to Google Analytics 4.

## 2. What Is a CLI (and Why Should You Care)?
- Brief explainer for the analytics audience: a CLI is a text-based interface to a system
- Key properties: scriptable, composable (pipes), automatable, version-controllable
- Analogy: the GA4 UI is like driving manual; a CLI is like having a chauffeur you can give written instructions to

## 3. CLIs in the Age of AI Agents
- Framing via Justin Poehnelt's article ["You Need to Rewrite Your CLI for AI Agents"](https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/) — Poehnelt (Senior DevRel at Google) built Google Workspace's CLI with agents as the primary consumer from day one
- His core insight: "Human DX optimizes for discoverability. Agent DX optimizes for predictability."
- Key agent-DX principles (from the article) and how GA CLI implements them:
  - **Structured output** → `--output json` on every command; agents parse JSON, not tables
  - **Structured errors** → JSON errors on stderr with classified exit codes (0=success, 1=client error, 2=auth error, 3=API error, 4=network error). Agents branch on failure type programmatically instead of parsing human-readable strings.
  - **Context window discipline** → concise, predictable responses; `--output compact` for minimal ID+name output
  - **Agent-specific documentation** → `ga agent guide` ships a reference (like Poehnelt's "SKILL.md" concept) encoding invariants agents can't intuit
  - **Schema introspection** → `ga --describe` outputs JSON Schema for all 115 commands in a single call — parameter names, types, flags, aliases, defaults, required fields, plus metadata (`mutative`, `supports_dry_run`). An agent calls this once, caches the result, and knows exactly how to construct any command. This is also the bridge to auto-generating MCP tool definitions from the CLI.
  - **Safe mutations / dry-run** → `--dry-run` on every create, update, and delete command previews the exact API request as JSON without executing. Agents can verify parameters and catch mistakes before they become live changes. Example: `ga properties create --name "EU Site" --timezone Europe/Berlin --dry-run` outputs the request body and exits.
  - **Composable** → agents chain commands just like shell scripts; no browser/UI automation needed
  - **Safety rails** → confirmation prompts on destructive operations (`--yes` to skip in automation)
- GA CLI was designed with this in mind: the `ga agent guide` command ships a reference specifically for AI agents

## 4. CLI vs MCP Servers — Where Does Each Fit?
- **MCP Servers**: Tight integration with MCP-compatible hosts (e.g., Claude Desktop). Rich bidirectional protocol. But: locked to MCP ecosystem, more complex to build and deploy.
- **CLIs**: Universal — works with any agent framework, shell script, CI pipeline, or human. Portable, installable via pip/pipx, zero infrastructure. Trade-off: stateless per invocation, no streaming protocol.
- **The sweet spot**: CLIs are more opinionated than raw APIs (less boilerplate) but more portable than MCP (works everywhere). They complement each other — a CLI can power an MCP server under the hood.
- Table/diagram comparing: CLI vs MCP vs raw API on dimensions like portability, agent compatibility, setup complexity, human usability

## 5. From CLI to Custom Skills — Making Agent Workflows Reliable
- **Key insight**: A CLI or MCP server alone isn't enough — without proper instructions tailored to your use case, agents fumble. The real value comes from pairing tools with **skills**: structured, reusable agent playbooks.
- Skills are one of the most powerful ways to customize AI agents (e.g., Claude) for specific, repeatable analytics workflows.
- **Recommendation**: Use Anthropic's official `skill-creator` meta skill to let Claude guide you through building your own — don't just copy someone else's.

### The four pillars of a well-crafted skill
1. **Structure & conventions** — Follow the open Agent Skills standard (`SKILL.md` format, YAML frontmatter, etc.)
2. **Tools** — Equip the skill with the right tool access (CLI commands, MCP servers, APIs)
3. **Data & context** — Fill `SKILL.md` with instructions, additional reference files, and executable code snippets that teach the agent about the custom intricacies of your setup
4. **Trigger & objective** — Skills are invoked via `/skill-name` commands or automatically based on natural-language matching against the skill description

### Playbooks: The missing reliability layer
- Write "playbooks" as Markdown files with explicit checkpoints and step-by-step instructions for repeatable tasks (GA property management, GTM standard implementations, etc.)
- These playbooks make task execution reliable and consistent — the agent follows a defined path rather than improvising each time
- Evaluate your skills: test with purpose-built skill-evaluation tools or manual eval sets

### Example: Stape-hosted GTM workflows
- Use Stape's official MCP servers to equip skills with tools for repeatable GTM workflows — container management, billing, access rights, tag/trigger/variable implementation
- Reference MCP servers in `SKILL.md` frontmatter via `allowed-tools`
- Add context files that capture the custom intricacies of your specific Stape + GTM setup

### Extending the skill library: End-to-end validation
- Combine implementation skills with **data validation skills** that hook into your destinations and retrieve the data stakeholders actually see
- Example: Pair a GTM implementation skill with the Piano Analytics MCP — which provides unsampled, real-time, fully processed reporting data from a native Stape & Piano integration
- Such skill combinations enable true end-to-end analytics implementation workflows: configure → deploy → validate

## 6. GA CLI Feature Tour
- **Auth**: OAuth 2.0 + service account support
- **Account & property management**: list, get, create, update, delete accounts and properties
- **Configuration resources**: custom dimensions, custom metrics, key events, data streams, data retention, MP secrets, Google Ads links, Firebase links
- **Reporting**: custom reports, pivot reports, real-time, batch reports, compatibility checks, metadata browsing, interactive report builder
- **Access reports**: audit who accessed what data and when
- **Developer experience**: shell completions (bash/zsh/fish), self-update (`ga upgrade`), `--output json|table|compact`
- **Agent-ready**:
  - `ga agent guide` — concise reference with sections for reports, admin, and worked examples
  - `ga --describe` — JSON Schema for all 115 commands in one call (parameter types, flags, defaults, required fields)
  - `--dry-run` — preview any mutation as JSON before executing
  - Structured JSON errors on stderr with classified exit codes (auth vs API vs network)
  - Auto-JSON output when piped (non-TTY detection)

## 7. Application Scenarios

### 7a. GA4 Audit
- Problem: Auditing a GA4 property's configuration is tedious in the UI — clicking through dozens of screens
- Solution: Script a full config dump in seconds
- Example commands: list custom dimensions, custom metrics, key events, data streams, data retention settings, Google Ads links, access reports
- Output as JSON for diffing, archiving, or feeding into a report

### 7b. Configuration Syncing Across Properties
- Problem: Organizations with multiple properties need consistent setup (same custom dimensions, key events, etc.)
- Solution: Export config from a "golden" property, apply to others
- Example: read custom dimensions from property A → create matching ones on property B
- Enables infrastructure-as-code patterns for analytics

### 7c. Automated Property Provisioning
- Problem: Spinning up new GA4 properties for new brands/sites/apps involves many manual steps
- Solution: A single script that creates property → data stream → custom dimensions → custom metrics → key events → MP secrets
- Show a shell script or agent workflow that does this end-to-end

### 7d. Compliance & Access Auditing
- Problem: "Who accessed our analytics data last quarter?" is a hard question to answer in the UI
- Solution: `ga access-reports run-account` / `run-property` with date ranges
- Use case: GDPR/privacy reviews, internal access audits, detecting unusual access patterns

### 7e. Reporting Pipelines & Dashboards
- Problem: Pulling recurring reports from GA4 requires either Looker Studio or custom API scripts
- Solution: `ga reports run` / `ga reports batch` with JSON output piped to downstream tools
- Examples: daily traffic summary to Slack, weekly performance CSV export, feeding data into a BI tool or spreadsheet

### 7f. Real-Time Monitoring
- Problem: Need a quick pulse check on live site activity without opening the GA4 UI
- Solution: `ga reports realtime --interval 30` for a live-updating terminal dashboard
- Use case: monitoring during launches, campaigns, or incidents

### 7g. Configuration Drift Detection
- Problem: Properties that should be identical slowly diverge over time
- Solution: Dump configs from multiple properties as JSON, diff them
- Detect missing custom dimensions, inconsistent key events, different data retention settings

### 7h. Agent-Driven Property Setup
- Problem: An AI agent needs to create and configure a GA4 property but doesn't know the CLI's interface
- Solution: The agent uses the CLI's built-in introspection to discover, preview, and execute — zero external docs needed
- Example workflow:
  1. `ga --describe` → agent discovers all commands, parameters, types, and which commands are mutative
  2. `ga properties create --name "EU Website" --account-id 123456 --timezone Europe/Berlin --dry-run` → agent previews the request body as JSON
  3. Agent verifies the dry-run output, then executes without `--dry-run`
  4. If the API returns an error, the agent reads the structured JSON error on stderr (with exit code 3 for API errors) and adjusts
- Rationale: `--describe` + `--dry-run` + structured errors form a complete agent feedback loop — discover → preview → execute → handle errors — without any external documentation or human intervention

## 8. Getting Started
- Installation (`pipx install ga-cli`)
- Quick auth setup (`ga auth login`)
- First commands to try
- Link to docs / GitHub repo

## 9. What's Next
- Roadmap teasers (if any)
- Call to action: try it, star the repo, file issues
- Community / contribution invitation

## MEDIA

- Screenshots
- Record a video of an audit

---

## Notes / Ideas to Revisit
- GA API nuggets: Discovery endpoint `curl -s "https://analyticsadmin.googleapis.com/$discovery/rest?version=v1alpha"`
- Consider including a "day in the life" narrative: a GA consultant using the CLI + an AI agent to audit 10 client properties in an afternoon
- Possible visual: terminal screenshots / asciinema recordings of key workflows
- Tone: practical, not overly salesy. Target audience = GA practitioners + technical marketers + analytics engineers
