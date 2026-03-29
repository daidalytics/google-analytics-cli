# GA4 Audit Workflow — Planning Document

## Goal

Build a comprehensive GA4 audit capability into the CLI that checks property configuration, data collection health, event/conversion setup, integrations, and data quality.

--> Use the Google Sheet template as a benchmark/guideline foir which features need to be checked:
https://docs.google.com/spreadsheets/d/1HXac-gvVXuNjf-pbUB3p1wnjRgQUEyixwwWkp_67AQs/edit?gid=0#gid=0

## Existing CLI Coverage

The CLI already wraps the key Admin API and Data API resources needed:

- **Property config**: `ga properties get`, `ga data-streams list`
- **Events & conversions**: `ga key-events list`, `ga custom-dimensions list`, `ga custom-metrics list`
- **Integrations**: `ga firebase-links list`, `ga google-ads-links list`, `ga mp-secrets list`
- **Data quality**: `ga reports run` (with flexible dimensions/metrics), `ga reports realtime`

## Proposed Audit Checks

### 1. Property Configuration

- Property settings review (timezone, currency, industry category)
- Data streams inventory (web/iOS/Android) — are all expected platforms present?
- Data retention and collection settings

### 2. Data Collection Health

- Are data streams actually receiving data? (run report with stream-level dimensions)
- Real-time data flowing?
- Measurement Protocol secrets in use?

### 3. Event & Conversion Setup

- Key events configured and counting methods reviewed (once per event vs once per session)
- Custom dimensions inventory — check for unused, duplicated, or poorly named definitions
- Custom metrics inventory — same checks
- Scope distribution (EVENT vs USER vs ITEM)

### 4. Integration Health

- Firebase links present and configured
- Google Ads links present, ads personalization settings reviewed
- Cross-product integration gaps

### 5. Data Quality (via Reports)

- `(not set)` values in key dimensions (source/medium, page title, country)
- Self-referral detection
- Channel grouping distribution — unexpected "Unassigned" traffic
- Low engagement rate or high bounce indicators
- Missing page titles

## Implementation Approach

### Option A: `ga audit` CLI Command (recommended starting point)

A built-in command that runs all checks programmatically, scores each one (pass/warn/fail), and outputs a structured report.

```
ga audit run [-p PROPERTY_ID] [-o table|json] [--checks all|config|collection|events|integrations|quality]
```

Advantages:
- Deterministic, repeatable results
- Ships with the tool — no external dependencies
- JSON output enables downstream automation

### Option B: Claude Code Skill/Workflow (layer on top)

A prompt-driven workflow where Claude orchestrates multiple `ga` CLI calls, interprets results, and produces a narrative audit report with recommendations.

Advantages:
- Richer interpretation and context-aware recommendations
- Can reason about combinations of findings
- More flexible — no code changes needed to add new checks

### Recommendation

Start with Option A for the core checks, then layer Option B on top for interpretation and recommendations.

## Admin API Gaps

Some audit checks require Admin API methods the CLI doesn't wrap yet:

- **Data retention settings** — `getDataRetentionSettings()`
- **Google Signals** — `getGoogleSignalsSettings()`
- **Enhanced measurement settings** — `getEnhancedMeasurementSettings()` (per data stream)
- **Attribution settings** — `getAttributionSettings()`
- **Audiences** — `listAudiences()`
- **Channel groups** — `listChannelGroups()`
- **Data redaction settings** — `getDataRedactionSettings()`

These would need to be added to the CLI before the audit can cover them.

## Open Questions

1. **Scope** — Should the audit target a single property, or sweep all properties under an account?
2. **Output format** — Scored checklist (pass/warn/fail), narrative report, or both?
3. **Priority** — Which checks to implement first?
4. **API gaps** — Add missing Admin API wrappers as part of this effort, or separate?
