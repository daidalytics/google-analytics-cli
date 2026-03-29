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
- AI agents need *tools* — interfaces they can call programmatically
- Why CLIs are natural agent tools:
  - Structured output (JSON mode) that agents can parse
  - Self-documenting (`--help`, and GA CLI's built-in `ga agent guide`)
  - Composable — agents can chain commands just like shell scripts
  - No browser/UI automation needed
- GA CLI was designed with this in mind: the `ga agent guide` command ships a reference specifically for AI agents

## 4. CLI vs MCP Servers — Where Does Each Fit?
- **MCP Servers**: Tight integration with MCP-compatible hosts (e.g., Claude Desktop). Rich bidirectional protocol. But: locked to MCP ecosystem, more complex to build and deploy.
- **CLIs**: Universal — works with any agent framework, shell script, CI pipeline, or human. Portable, installable via pip/pipx, zero infrastructure. Trade-off: stateless per invocation, no streaming protocol.
- **The sweet spot**: CLIs are more opinionated than raw APIs (less boilerplate) but more portable than MCP (works everywhere). They complement each other — a CLI can power an MCP server under the hood.
- Table/diagram comparing: CLI vs MCP vs raw API on dimensions like portability, agent compatibility, setup complexity, human usability

## 5. GA CLI Feature Tour
- **Auth**: OAuth 2.0 + service account support
- **Account & property management**: list, get, create, update, delete accounts and properties
- **Configuration resources**: custom dimensions, custom metrics, key events, data streams, data retention, MP secrets, Google Ads links, Firebase links
- **Reporting**: custom reports, pivot reports, real-time, batch reports, compatibility checks, metadata browsing, interactive report builder
- **Access reports**: audit who accessed what data and when
- **Developer experience**: shell completions (bash/zsh/fish), self-update (`ga upgrade`), `--output json|table|compact`
- **Agent-ready**: `ga agent guide` with sections for reports, admin, and worked examples

## 6. Application Scenarios

### 6a. GA4 Audit
- Problem: Auditing a GA4 property's configuration is tedious in the UI — clicking through dozens of screens
- Solution: Script a full config dump in seconds
- Example commands: list custom dimensions, custom metrics, key events, data streams, data retention settings, Google Ads links, access reports
- Output as JSON for diffing, archiving, or feeding into a report

### 6b. Configuration Syncing Across Properties
- Problem: Organizations with multiple properties need consistent setup (same custom dimensions, key events, etc.)
- Solution: Export config from a "golden" property, apply to others
- Example: read custom dimensions from property A → create matching ones on property B
- Enables infrastructure-as-code patterns for analytics

### 6c. Automated Property Provisioning
- Problem: Spinning up new GA4 properties for new brands/sites/apps involves many manual steps
- Solution: A single script that creates property → data stream → custom dimensions → custom metrics → key events → MP secrets
- Show a shell script or agent workflow that does this end-to-end

### 6d. Compliance & Access Auditing
- Problem: "Who accessed our analytics data last quarter?" is a hard question to answer in the UI
- Solution: `ga access-reports run-account` / `run-property` with date ranges
- Use case: GDPR/privacy reviews, internal access audits, detecting unusual access patterns

### 6e. Reporting Pipelines & Dashboards
- Problem: Pulling recurring reports from GA4 requires either Looker Studio or custom API scripts
- Solution: `ga reports run` / `ga reports batch` with JSON output piped to downstream tools
- Examples: daily traffic summary to Slack, weekly performance CSV export, feeding data into a BI tool or spreadsheet

### 6f. Real-Time Monitoring
- Problem: Need a quick pulse check on live site activity without opening the GA4 UI
- Solution: `ga reports realtime --interval 30` for a live-updating terminal dashboard
- Use case: monitoring during launches, campaigns, or incidents

### 6g. Configuration Drift Detection
- Problem: Properties that should be identical slowly diverge over time
- Solution: Dump configs from multiple properties as JSON, diff them
- Detect missing custom dimensions, inconsistent key events, different data retention settings

## 7. Getting Started
- Installation (`pipx install ga-cli`)
- Quick auth setup (`ga auth login`)
- First commands to try
- Link to docs / GitHub repo

## 8. What's Next
- Roadmap teasers (if any)
- Call to action: try it, star the repo, file issues
- Community / contribution invitation

---

## Notes / Ideas to Revisit
- GA API nuggets: Discovery endpoint? `curl -s "https://analyticsadmin.googleapis.com/$discovery/rest?version=v1alpha"`
- Consider including a "day in the life" narrative: a GA consultant using the CLI + an AI agent to audit 10 client properties in an afternoon
- Possible visual: terminal screenshots / asciinema recordings of key workflows
- Tone: practical, not overly salesy. Target audience = GA practitioners + technical marketers + analytics engineers
