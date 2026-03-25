# Gap Analysis: GA Data API v1 & Admin API v1

Comprehensive gap analysis of the GA CLI against the full Google Analytics Data API v1 and Admin API v1 surfaces. Each workstream (WS) is self-contained and can be picked up independently.

**Testing convention:** All tests use `typer.testing.CliRunner`, `unittest.mock.patch`, class-based grouping (`class TestXxx:`), and the `isolated_config_dir` autouse fixture from `conftest.py`. Every workstream that adds or modifies Python code **must** include a corresponding test file (or additions to an existing test file) with full coverage before it is considered complete.

**Definition of Done (per workstream):**
1. All listed source files are created/modified
2. All tests in the test matrix pass (`uv run pytest tests/test_<name>.py`)
3. `uv run ruff check src/ tests/` passes with no new warnings
4. `uv run pytest` passes (full suite, no regressions)

---

## Table of Contents

- [Current Coverage Summary](#current-coverage-summary)
- **Data API v1beta**
  - [WS-D1: Pivot Reports](#ws-d1-pivot-reports)
  - [WS-D2: Batch Reports](#ws-d2-batch-reports)
  - [WS-D3: Check Compatibility](#ws-d3-check-compatibility)
  - [WS-D4: Audience Exports](#ws-d4-audience-exports)
  - [WS-D5: Expose getMetadata as a CLI Command](#ws-d5-expose-getmetadata-as-a-cli-command)
- **Data API v1alpha**
  - [WS-DA1: Funnel Reports](#ws-da1-funnel-reports)
  - [WS-DA2: Property Quotas Snapshot](#ws-da2-property-quotas-snapshot)
  - [WS-DA3: Report Tasks](#ws-da3-report-tasks)
- **Admin API v1beta**
  - [WS-A1: Custom Dimensions](#ws-a1-custom-dimensions)
  - [WS-A2: Custom Metrics](#ws-a2-custom-metrics)
  - [WS-A3: Key Events](#ws-a3-key-events)
  - [WS-A4: Measurement Protocol Secrets](#ws-a4-measurement-protocol-secrets)
  - [WS-A5: Google Ads Links](#ws-a5-google-ads-links)
  - [WS-A6: Firebase Links](#ws-a6-firebase-links)
  - [WS-A7: Account Summaries](#ws-a7-account-summaries)
  - [WS-A8: Properties — Patch](#ws-a8-properties--patch)
  - [WS-A9: Data Streams — Patch](#ws-a9-data-streams--patch)
  - [WS-A10: Data Retention Settings](#ws-a10-data-retention-settings)
  - [WS-A11: Change History](#ws-a11-change-history)
  - [WS-A12: Access Reports](#ws-a12-access-reports)
  - [WS-A13: Accounts — Delete](#ws-a13-accounts--delete)
  - [WS-A14: Acknowledge User Data Collection](#ws-a14-acknowledge-user-data-collection)
  - [WS-A15: Data Sharing Settings](#ws-a15-data-sharing-settings)
- **Admin API v1alpha**
  - [WS-AA1: Audiences](#ws-aa1-audiences)
  - [WS-AA2: BigQuery Links](#ws-aa2-bigquery-links)
  - [WS-AA3: Channel Groups](#ws-aa3-channel-groups)
  - [WS-AA4: Calculated Metrics](#ws-aa4-calculated-metrics)
  - [WS-AA5: Event Create Rules](#ws-aa5-event-create-rules)
  - [WS-AA6: Event Edit Rules](#ws-aa6-event-edit-rules)
  - [WS-AA7: Access Bindings](#ws-aa7-access-bindings)
  - [WS-AA8: Reporting Data Annotations](#ws-aa8-reporting-data-annotations)
  - [WS-AA9: Property Settings (Attribution, Google Signals, Enhanced Measurement)](#ws-aa9-property-settings)
  - [WS-AA10: Display & Video 360 Links](#ws-aa10-display--video-360-links)
  - [WS-AA11: Search Ads 360 Links](#ws-aa11-search-ads-360-links)
  - [WS-AA12: AdSense Links](#ws-aa12-adsense-links)
  - [WS-AA13: Expanded Data Sets](#ws-aa13-expanded-data-sets)
  - [WS-AA14: Rollup Property Source Links](#ws-aa14-rollup-property-source-links)
  - [WS-AA15: Subproperty Event Filters](#ws-aa15-subproperty-event-filters)
  - [WS-AA16: SKAdNetwork Conversion Value Schema](#ws-aa16-skadnetwork-conversion-value-schema)
- [Priority Matrix](#priority-matrix)

---

## Current Coverage Summary

### Data API v1beta

| Method | Status | CLI Command |
|--------|--------|-------------|
| `properties.runReport` | **Implemented** | `ga reports run` |
| `properties.runRealtimeReport` | **Implemented** | `ga reports realtime` |
| `properties.getMetadata` | **Implemented** | `ga reports metadata` |
| `properties.batchRunReports` | Missing | — |
| `properties.runPivotReport` | **Implemented** | `ga reports pivot` |
| `properties.batchRunPivotReports` | Missing | — |
| `properties.checkCompatibility` | **Implemented** | `ga reports check-compatibility` |
| `properties.audienceExports.create` | Missing | — |
| `properties.audienceExports.query` | Missing | — |
| `properties.audienceExports.get` | Missing | — |
| `properties.audienceExports.list` | Missing | — |

**Coverage: 5/11 methods (45%)**

### Admin API v1beta

| Method | Status | CLI Command |
|--------|--------|-------------|
| `accounts.list` | **Implemented** | `ga accounts list` |
| `accounts.get` | **Implemented** | `ga accounts get` |
| `accounts.patch` | **Implemented** | `ga accounts update` |
| `accounts.delete` | Missing | — |
| `accounts.provisionAccountTicket` | Missing (out of scope — requires UI) | — |
| `accounts.runAccessReport` | Missing | — |
| `accounts.searchChangeHistoryEvents` | Missing | — |
| `accounts.getDataSharingSettings` | Missing | — |
| `accountSummaries.list` | **Implemented** | `ga account-summaries list` |
| `properties.list` | **Implemented** | `ga properties list` |
| `properties.get` | **Implemented** | `ga properties get` |
| `properties.create` | **Implemented** | `ga properties create` |
| `properties.delete` | **Implemented** | `ga properties delete` |
| `properties.patch` | **Implemented** | `ga properties update` |
| `properties.acknowledgeUserDataCollection` | Missing | — |
| `properties.runAccessReport` | Missing | — |
| `properties.getDataRetentionSettings` | Missing | — |
| `properties.updateDataRetentionSettings` | Missing | — |
| `dataStreams.list` | **Implemented** | `ga data-streams list` |
| `dataStreams.get` | **Implemented** | `ga data-streams get` |
| `dataStreams.create` | **Implemented** | `ga data-streams create` |
| `dataStreams.delete` | **Implemented** | `ga data-streams delete` |
| `dataStreams.patch` | **Implemented** | `ga data-streams update` |
| `measurementProtocolSecrets.*` (5 methods) | Missing | — |
| `customDimensions.*` (5 methods) | **Implemented** | `ga custom-dimensions list\|get\|create\|update\|archive` |
| `customMetrics.*` (5 methods) | **Implemented** | `ga custom-metrics list\|get\|create\|update\|archive` |
| `keyEvents.*` (5 methods) | **Implemented** | `ga key-events list\|get\|create\|update\|delete` |
| `firebaseLinks.*` (3 methods) | Missing | — |
| `googleAdsLinks.*` (4 methods) | Missing | — |
| `conversionEvents.*` (5 methods) | Skipped (deprecated, replaced by keyEvents) | — |

**Coverage: 28/~55 methods (51%)**

---

## Data API v1beta Workstreams

---

### WS-D1: Pivot Reports

**Goal:** Add `ga reports pivot` to run cross-tabulated pivot reports via `properties.runPivotReport`.

**API reference:** `POST v1beta/{property=properties/*}:runPivotReport`

A pivot report restructures data into a cross-tabulation format (like a spreadsheet pivot table). Unlike `runReport` which returns flat rows, pivot reports group data by pivot field values across columns.

#### Files to create
- `tests/test_reports_pivot.py`

#### Files to modify
- `src/ga_cli/commands/reports.py` — add `pivot_cmd`

#### Implementation details

##### `pivot_cmd` in `reports.py`
```python
@reports_app.command("pivot")
def pivot_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p", help="GA4 property ID"),
    metrics: str = typer.Option(..., "--metrics", "-m", help="Comma-separated metrics"),
    dimensions: str = typer.Option(..., "--dimensions", "-d", help="Comma-separated dimensions (all used in pivots)"),
    pivot_field: str = typer.Option(..., "--pivot-field", help="Dimension to pivot on (must be in --dimensions)"),
    start_date: str = typer.Option("28daysAgo", "--start-date", help="Start date"),
    end_date: str = typer.Option("yesterday", "--end-date", help="End date"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max rows per pivot group"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Output format"),
):
```

- Build `pivots` array from `--pivot-field` and `--dimensions`:
  - The `--pivot-field` dimension becomes the pivot's `fieldNames`
  - Remaining dimensions are used as row dimensions
- Request body structure:
  ```json
  {
    "dateRanges": [{"startDate": "...", "endDate": "..."}],
    "metrics": [{"name": "m1"}, ...],
    "dimensions": [{"name": "d1"}, ...],
    "pivots": [
      {
        "fieldNames": ["<pivot-field>"],
        "limit": 5
      },
      {
        "fieldNames": ["<remaining-dimensions>"],
        "limit": <limit>
      }
    ]
  }
  ```
- Call `data_client.properties().runPivotReport(property=f"properties/{property_id}", body=body).execute()`
- Parse pivot response: `pivotHeaders` defines column groups, `rows` contain `dimensionValues` and `metricValues`
- Table output: render as cross-tab with pivot field values as column headers
- JSON output: return raw API response

##### Example usage
```bash
# Pivot sessions by device category across countries
ga reports pivot -p 123456 \
  --metrics sessions,users \
  --dimensions country,deviceCategory \
  --pivot-field deviceCategory \
  --start-date 7daysAgo
```

#### Tests (`tests/test_reports_pivot.py`)

##### Class: `TestPivotReport`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_pivot_basic_table` | `data.properties().runPivotReport().execute()` → sample pivot response | Exit 0, table output contains pivot column headers |
| `test_pivot_json_output` | Same mock, add `-o json` | Exit 0, valid JSON with `pivotHeaders` key |
| `test_pivot_requires_metrics` | No mocks | Exit != 0, error mentions `--metrics` |
| `test_pivot_requires_pivot_field` | No mocks | Exit != 0, error mentions `--pivot-field` |
| `test_pivot_field_must_be_in_dimensions` | No mocks, `--pivot-field foo --dimensions bar,baz` | Exit != 0 or warning |
| `test_pivot_api_error` | `runPivotReport().execute()` raises HttpError | Exit 1, formatted error message |
| `test_pivot_empty_response` | Mock returns empty rows | Exit 0, "No data" message |
| `test_pivot_uses_config_property_id` | Mock `get_effective_value("default_property_id")` → "123" | API called with `properties/123` |

---

### WS-D2: Batch Reports

**Goal:** Add `ga reports batch` to run multiple reports in a single API call via `properties.batchRunReports`.

**API reference:** `POST v1beta/{property=properties/*}:batchRunReports`

Batch reports allow up to 5 report requests in a single API call. All reports must be for the same property. This reduces round-trips and counts as a single quota hit.

#### Files to create
- `tests/test_reports_batch.py`

#### Files to modify
- `src/ga_cli/commands/reports.py` — add `batch_cmd`

#### Implementation details

##### `batch_cmd` in `reports.py`
```python
@reports_app.command("batch")
def batch_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p", help="GA4 property ID"),
    config_file: str = typer.Option(..., "--config", "-c", help="Path to JSON batch config file"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Output format"),
):
```

- Read a JSON config file that defines up to 5 report specs:
  ```json
  {
    "reports": [
      {
        "metrics": ["sessions", "users"],
        "dimensions": ["date"],
        "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
        "limit": 100
      },
      {
        "metrics": ["eventCount"],
        "dimensions": ["eventName"],
        "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
        "limit": 50
      }
    ]
  }
  ```
- Validate: max 5 reports, each has at least one metric
- Transform each report spec into the `RunReportRequest` format
- Call `data_client.properties().batchRunReports(property=f"properties/{property_id}", body={"requests": requests}).execute()`
- Response contains `reports` array — each entry is a standard `RunReportResponse`
- Table output: render each report sequentially with a header separator (e.g., "--- Report 1 ---")
- JSON output: return the full batch response

#### Tests (`tests/test_reports_batch.py`)

##### Class: `TestBatchReport`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_batch_two_reports_table` | `batchRunReports().execute()` → response with 2 report results | Exit 0, output contains both report tables |
| `test_batch_json_output` | Same mock, add `-o json` | Exit 0, JSON with `reports` array of length 2 |
| `test_batch_requires_config_file` | No mocks | Exit != 0, error mentions `--config` |
| `test_batch_config_file_not_found` | Pass nonexistent path | Exit 1, "file not found" error |
| `test_batch_config_exceeds_5_reports` | Write config with 6 report specs | Exit 1, error about max 5 reports |
| `test_batch_config_invalid_json` | Write file with invalid JSON | Exit 1, JSON parse error |
| `test_batch_api_error` | `batchRunReports().execute()` raises HttpError | Exit 1, formatted error |
| `test_batch_empty_reports_array` | Write config with empty `reports: []` | Exit 1, error about at least one report |
| `test_batch_uses_config_property_id` | Mock `get_effective_value` | API called with correct property |

---

### WS-D3: Check Compatibility

**Goal:** Add `ga reports check-compatibility` to verify that a combination of dimensions and metrics can be used together in a report.

**API reference:** `POST v1beta/{property=properties/*}:checkCompatibility`

This is useful before running a report to verify that the requested dimensions and metrics are compatible with each other. The response indicates which combinations are valid.

#### Files to modify
- `src/ga_cli/commands/reports.py` — add `check_compatibility_cmd`
- `tests/test_reports.py` — add `TestCheckCompatibility` class

#### Implementation details

##### `check_compatibility_cmd` in `reports.py`
```python
@reports_app.command("check-compatibility")
def check_compatibility_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p", help="GA4 property ID"),
    metrics: str = typer.Option(None, "--metrics", "-m", help="Comma-separated metrics to check"),
    dimensions: str = typer.Option(None, "--dimensions", "-d", help="Comma-separated dimensions to check"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Output format"),
):
```

- Build request body:
  ```json
  {
    "metrics": [{"name": "sessions"}, ...],
    "dimensions": [{"name": "date"}, ...],
    "compatibilityFilter": "COMPATIBLE"
  }
  ```
- Call `data_client.properties().checkCompatibility(property=f"properties/{property_id}", body=body).execute()`
- Response contains:
  - `dimensionCompatibilities`: list with each dimension's compatibility status
  - `metricCompatibilities`: list with each metric's compatibility status
- Table output: show each dimension/metric with its compatibility status (COMPATIBLE / INCOMPATIBLE)
- JSON output: return raw response

#### Tests (in `tests/test_reports.py`)

##### Class: `TestCheckCompatibility`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_all_compatible_table` | `checkCompatibility().execute()` → all COMPATIBLE | Exit 0, all items show COMPATIBLE |
| `test_some_incompatible_table` | Response with mixed compatibility | Exit 0, INCOMPATIBLE items flagged |
| `test_json_output` | Standard response, `-o json` | Exit 0, valid JSON |
| `test_no_metrics_or_dimensions` | Neither `--metrics` nor `--dimensions` given | Exit != 0, error about needing at least one |
| `test_api_error` | `checkCompatibility().execute()` raises HttpError | Exit 1, formatted error |

---

### WS-D4: Audience Exports

**Goal:** Add `ga audience-exports` command group with `create`, `get`, `list`, and `query` subcommands.

**API reference:**
- `POST v1beta/{parent=properties/*}/audienceExports` (create)
- `GET v1beta/{name=properties/*/audienceExports/*}` (get)
- `GET v1beta/{parent=properties/*}/audienceExports` (list)
- `POST v1beta/{name=properties/*/audienceExports/*}:query` (query)

Audience exports allow exporting the users that match a GA4 audience definition. The workflow is: create an export (async), poll until complete, then query for the user list.

#### Files to create
- `src/ga_cli/commands/audience_exports.py`
- `tests/test_audience_exports.py`

#### Files to modify
- `src/ga_cli/main.py` — register `audience_exports_app`

#### Implementation details

##### `audience_exports.py`
```python
audience_exports_app = typer.Typer(name="audience-exports", help="Manage audience exports")

@audience_exports_app.command("create")
def create_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    audience: str = typer.Option(..., "--audience", "-a", help="Audience resource name (e.g., properties/123/audiences/456)"),
    dimensions: str = typer.Option(None, "--dimensions", "-d", help="Comma-separated dimension names to include in export"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Body: `{"audience": "<audience>", "dimensions": [{"dimensionName": "..."}]}`
- Call `data_client.properties().audienceExports().create(parent=f"properties/{property_id}", body=body).execute()`
- Returns a long-running operation; extract the audience export name from the response
- Print the export name/state so user can poll with `get`

```python
@audience_exports_app.command("get")
def get_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    export_id: str = typer.Option(..., "--export-id", "-e", help="Audience export ID"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `data_client.properties().audienceExports().get(name=f"properties/{property_id}/audienceExports/{export_id}").execute()`
- Display export metadata including state (CREATING, ACTIVE, FAILED)

```python
@audience_exports_app.command("list")
def list_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `data_client.properties().audienceExports().list(parent=f"properties/{property_id}").execute()`
- Use `paginate_all` for pagination
- Display table with name, audience, state, creation time

```python
@audience_exports_app.command("query")
def query_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    export_id: str = typer.Option(..., "--export-id", "-e", help="Audience export ID"),
    limit: int = typer.Option(100, "--limit", "-l"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `data_client.properties().audienceExports().query(name=f"properties/{property_id}/audienceExports/{export_id}", body={"limit": limit}).execute()`
- Response contains `audienceRows` with user dimension values
- Render as table or JSON

#### Tests (`tests/test_audience_exports.py`)

##### Class: `TestAudienceExportsCreate`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_create_returns_operation` | `audienceExports().create().execute()` → operation response | Exit 0, export name printed |
| `test_create_requires_audience` | No mocks | Exit != 0, error mentions `--audience` |
| `test_create_api_error` | `create().execute()` raises HttpError | Exit 1, formatted error |
| `test_create_with_dimensions` | Pass `--dimensions deviceId,userId` | Body includes dimensions array |
| `test_create_json_output` | Standard mock, `-o json` | Valid JSON output |

##### Class: `TestAudienceExportsGet`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_get_active_export` | `audienceExports().get().execute()` → state=ACTIVE | Exit 0, shows ACTIVE state |
| `test_get_creating_export` | Same, state=CREATING | Exit 0, shows CREATING state |
| `test_get_api_error` | Raises HttpError | Exit 1 |

##### Class: `TestAudienceExportsList`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_list_multiple_exports` | `list().execute()` → 3 exports | Exit 0, 3 rows in table |
| `test_list_empty` | Empty response | Exit 0, "No audience exports" message |
| `test_list_json` | Standard mock, `-o json` | Valid JSON array |

##### Class: `TestAudienceExportsQuery`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_query_returns_users` | `query().execute()` → audienceRows with data | Exit 0, user data in output |
| `test_query_empty_results` | Empty audienceRows | Exit 0, "No data" message |
| `test_query_json_output` | Standard mock, `-o json` | Valid JSON |
| `test_query_respects_limit` | Pass `--limit 10` | Body contains `"limit": 10` |

---

### WS-D5: Expose getMetadata as a CLI Command

**Goal:** Add `ga reports metadata` to expose the existing `getMetadata` call as a user-facing command.

**API reference:** `GET v1beta/{name=properties/*/metadata}`

Currently `getMetadata` is only used internally by `reports build`. Exposing it as a standalone command lets users browse available dimensions and metrics.

#### Files to modify
- `src/ga_cli/commands/reports.py` — add `metadata_cmd`
- `tests/test_reports.py` — add `TestMetadata` class

#### Implementation details

##### `metadata_cmd` in `reports.py`
```python
@reports_app.command("metadata")
def metadata_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p", help="GA4 property ID"),
    filter_type: str = typer.Option(None, "--type", "-t", help="Filter by 'metrics' or 'dimensions'"),
    search: str = typer.Option(None, "--search", "-s", help="Filter names containing this string"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `data_client.properties().getMetadata(name=f"properties/{property_id}/metadata").execute()`
- Response has `dimensions` and `metrics` arrays, each with `apiName`, `uiName`, `description`, `category`, `customDefinition`
- If `--type metrics`, only show metrics; if `--type dimensions`, only show dimensions; else show both
- If `--search`, filter to entries where `apiName` or `uiName` contains the search string (case-insensitive)
- Table output: columns = Type, API Name, UI Name, Category, Custom
- JSON output: filtered list

#### Tests (in `tests/test_reports.py`)

##### Class: `TestMetadata`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_metadata_all` | `getMetadata().execute()` → sample response with dims + metrics | Exit 0, both dimensions and metrics in output |
| `test_metadata_filter_metrics` | Same mock, `--type metrics` | Output contains only metrics |
| `test_metadata_filter_dimensions` | Same mock, `--type dimensions` | Output contains only dimensions |
| `test_metadata_search` | Same mock, `--search page` | Output filtered to matching names |
| `test_metadata_json` | Same mock, `-o json` | Valid JSON |
| `test_metadata_api_error` | Raises HttpError | Exit 1 |
| `test_metadata_empty_response` | No dimensions or metrics | Exit 0, "No metadata" message |

---

## Data API v1alpha Workstreams

> **Note:** Alpha API methods may have breaking changes. These workstreams require using the `v1alpha` API version. The CLI should build a separate alpha Data API client in `api/client.py`: `build("analyticsdata", "v1alpha", credentials=creds)`.

---

### WS-DA1: Funnel Reports

**Goal:** Add `ga reports funnel` to run funnel analysis reports via `properties.runFunnelReport` (v1alpha).

**API reference:** `POST v1alpha/{property=properties/*}:runFunnelReport`

Funnel reports show how users progress through a defined sequence of steps (e.g., page view → add to cart → purchase). Each step defines filter conditions and the report shows drop-off between steps.

#### Files to create
- `tests/test_reports_funnel.py`

#### Files to modify
- `src/ga_cli/api/client.py` — add `get_data_alpha_client()` builder
- `src/ga_cli/commands/reports.py` — add `funnel_cmd`

#### Implementation details

##### Alpha client in `api/client.py`
```python
_data_alpha_client = None

def get_data_alpha_client():
    global _data_alpha_client
    if _data_alpha_client is None:
        creds = resolve_credentials()
        _data_alpha_client = build("analyticsdata", "v1alpha", credentials=creds)
    return _data_alpha_client
```

##### `funnel_cmd` in `reports.py`
```python
@reports_app.command("funnel")
def funnel_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    config_file: str = typer.Option(..., "--config", "-c", help="Path to JSON funnel config"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```

- Read funnel configuration from a JSON file:
  ```json
  {
    "dateRanges": [{"startDate": "28daysAgo", "endDate": "yesterday"}],
    "funnel": {
      "steps": [
        {
          "name": "First visit",
          "filterExpression": {
            "eventFilter": {"eventName": "first_visit"}
          }
        },
        {
          "name": "Purchase",
          "filterExpression": {
            "eventFilter": {"eventName": "purchase"}
          }
        }
      ]
    }
  }
  ```
- Call `alpha_data_client.properties().runFunnelReport(property=f"properties/{property_id}", body=body).execute()`
- Response contains `funnelTable` with `funnelStepRows` (active users at each step) and `funnelVisualization`
- Table output: step name, active users, completion rate, drop-off rate
- JSON output: raw response

#### Tests (`tests/test_reports_funnel.py`)

##### Class: `TestFunnelReport`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_funnel_basic_table` | `runFunnelReport().execute()` → sample funnel response | Exit 0, step names and completion rates shown |
| `test_funnel_json_output` | Same mock, `-o json` | Valid JSON with `funnelTable` |
| `test_funnel_requires_config` | No `--config` | Exit != 0 |
| `test_funnel_config_not_found` | Nonexistent path | Exit 1 |
| `test_funnel_invalid_config` | Invalid JSON file | Exit 1 |
| `test_funnel_api_error` | HttpError | Exit 1 |
| `test_funnel_uses_alpha_client` | Mock `get_data_alpha_client` | Alpha client used, not beta |

---

### WS-DA2: Property Quotas Snapshot

**Goal:** Add `ga properties quotas` to view API quota usage via `properties.getPropertyQuotasSnapshot` (v1alpha).

**API reference:** `GET v1alpha/{name=properties/*/propertyQuotasSnapshot}`

Shows current quota consumption across categories: tokens per day, tokens per hour, tokens per project per hour, concurrent requests, and server errors per project per hour.

#### Files to modify
- `src/ga_cli/api/client.py` — ensure `get_data_alpha_client()` exists (from WS-DA1, or add here)
- `src/ga_cli/commands/properties.py` — add `quotas_cmd`
- `tests/test_properties.py` — add `TestPropertyQuotas` class

#### Implementation details

##### `quotas_cmd` in `properties.py`
```python
@properties_app.command("quotas")
def quotas_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `alpha_data_client.properties().getPropertyQuotasSnapshot(name=f"properties/{property_id}/propertyQuotasSnapshot").execute()`
- Response contains quota categories each with `consumed` and `remaining` values
- Table output: Quota Category, Consumed, Remaining, Limit (consumed + remaining)
- JSON output: raw response

#### Tests (in `tests/test_properties.py`)

##### Class: `TestPropertyQuotas`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_quotas_table` | `getPropertyQuotasSnapshot().execute()` → sample response | Exit 0, quota categories shown |
| `test_quotas_json` | Same, `-o json` | Valid JSON |
| `test_quotas_api_error` | HttpError | Exit 1 |

---

### WS-DA3: Report Tasks

**Goal:** Add `ga report-tasks` command group for async report generation via `properties.reportTasks.*` (v1alpha).

**API reference:**
- `POST v1alpha/{parent=properties/*}/reportTasks` (create)
- `GET v1alpha/{name=properties/*/reportTasks/*}` (get)
- `GET v1alpha/{parent=properties/*}/reportTasks` (list)
- `POST v1alpha/{name=properties/*/reportTasks/*}:query` (query)

Report tasks allow initiating a report asynchronously and retrieving results later. Useful for large reports that may time out with synchronous `runReport`.

#### Files to create
- `src/ga_cli/commands/report_tasks.py`
- `tests/test_report_tasks.py`

#### Files to modify
- `src/ga_cli/main.py` — register `report_tasks_app`
- `src/ga_cli/api/client.py` — ensure alpha client exists

#### Implementation details

##### `report_tasks.py`
```python
report_tasks_app = typer.Typer(name="report-tasks", help="Manage async report tasks (alpha)")

@report_tasks_app.command("create")
def create_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    config_file: str = typer.Option(..., "--config", "-c", help="Path to JSON report config"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Read JSON config matching `RunReportRequest` format
- Call `alpha_data_client.properties().reportTasks().create(parent=f"properties/{property_id}", body={"reportDefinition": config}).execute()`
- Returns long-running operation; print task name/ID

```python
@report_tasks_app.command("get")
def get_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    task_id: str = typer.Option(..., "--task-id", "-t"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `.reportTasks().get(name=f"properties/{property_id}/reportTasks/{task_id}").execute()`
- Display task state and metadata

```python
@report_tasks_app.command("list")
def list_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- List all report tasks for a property with pagination

```python
@report_tasks_app.command("query")
def query_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    task_id: str = typer.Option(..., "--task-id", "-t"),
    limit: int = typer.Option(100, "--limit", "-l"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `.reportTasks().query(name=f"properties/{property_id}/reportTasks/{task_id}", body={"limit": limit}).execute()`
- Response is a standard report format — render like `reports run`

#### Tests (`tests/test_report_tasks.py`)

##### Class: `TestReportTasksCreate`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_create_returns_task_name` | `reportTasks().create().execute()` → operation | Exit 0, task name printed |
| `test_create_requires_config` | No `--config` | Exit != 0 |
| `test_create_api_error` | HttpError | Exit 1 |

##### Class: `TestReportTasksGet`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_get_completed_task` | State = COMPLETED | Exit 0, state shown |
| `test_get_pending_task` | State = CREATING | Exit 0, state shown |

##### Class: `TestReportTasksList`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_list_tasks` | Multiple tasks | Exit 0, all tasks shown |
| `test_list_empty` | Empty response | Exit 0, "No report tasks" message |

##### Class: `TestReportTasksQuery`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_query_results` | Report rows in response | Exit 0, data shown |
| `test_query_json` | Same, `-o json` | Valid JSON |
| `test_query_respects_limit` | `--limit 10` | Body contains limit |

---

## Admin API v1beta Workstreams

---

### WS-A1: Custom Dimensions

**Goal:** Add `ga custom-dimensions` command group with `list`, `get`, `create`, `update`, and `archive` subcommands.

**API reference:**
- `GET v1beta/{parent=properties/*}/customDimensions` (list)
- `GET v1beta/{name=properties/*/customDimensions/*}` (get)
- `POST v1beta/{parent=properties/*}/customDimensions` (create)
- `PATCH v1beta/{customDimension.name=properties/*/customDimensions/*}` (patch)
- `POST v1beta/{name=properties/*/customDimensions/*}:archive` (archive)

Custom dimensions extend GA4's built-in dimensions with property-specific user/event/item-scoped parameters.

#### Files to create
- `src/ga_cli/commands/custom_dimensions.py`
- `tests/test_custom_dimensions.py`

#### Files to modify
- `src/ga_cli/main.py` — register `custom_dimensions_app`

#### Implementation details

##### `custom_dimensions.py`
```python
custom_dimensions_app = typer.Typer(name="custom-dimensions", help="Manage custom dimensions")

@custom_dimensions_app.command("list")
def list_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `admin.properties().customDimensions().list(parent=f"properties/{property_id}").execute()`
- Use `paginate_all` helper
- Table columns: Name, Parameter Name, Display Name, Scope, Description, Disallow Ads Personalization

```python
@custom_dimensions_app.command("get")
def get_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    dimension_id: str = typer.Option(..., "--dimension-id", "-d", help="Custom dimension ID"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `admin.properties().customDimensions().get(name=f"properties/{property_id}/customDimensions/{dimension_id}").execute()`

```python
@custom_dimensions_app.command("create")
def create_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    parameter_name: str = typer.Option(..., "--parameter-name", help="Event parameter name"),
    display_name: str = typer.Option(..., "--display-name", help="Display name in GA4 UI"),
    scope: str = typer.Option(..., "--scope", help="Scope: EVENT, USER, or ITEM"),
    description: str = typer.Option("", "--description", help="Description"),
    disallow_ads: bool = typer.Option(False, "--disallow-ads", help="Disallow ads personalization"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Validate scope is one of EVENT, USER, ITEM
- Body: `{"parameterName": ..., "displayName": ..., "scope": ..., "description": ..., "disallowAdsPersonalization": ...}`
- Call `admin.properties().customDimensions().create(parent=f"properties/{property_id}", body=body).execute()`

```python
@custom_dimensions_app.command("update")
def update_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    dimension_id: str = typer.Option(..., "--dimension-id", "-d"),
    display_name: str = typer.Option(None, "--display-name"),
    description: str = typer.Option(None, "--description"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Build `updateMask` from provided fields
- Call `admin.properties().customDimensions().patch(name=..., body=body, updateMask=mask).execute()`
- Note: `parameterName` and `scope` cannot be changed after creation

```python
@custom_dimensions_app.command("archive")
def archive_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    dimension_id: str = typer.Option(..., "--dimension-id", "-d"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
```
- Confirm unless `--yes`
- Call `admin.properties().customDimensions().archive(name=f"properties/{property_id}/customDimensions/{dimension_id}", body={}).execute()`

#### Tests (`tests/test_custom_dimensions.py`)

##### Class: `TestCustomDimensionsList`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_list_table` | `customDimensions().list().execute()` → 3 dimensions | Exit 0, 3 rows in table |
| `test_list_empty` | Empty response | Exit 0, "No custom dimensions" message |
| `test_list_json` | Standard mock, `-o json` | Valid JSON array |
| `test_list_api_error` | HttpError | Exit 1 |

##### Class: `TestCustomDimensionsGet`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_get_table` | `get().execute()` → dimension object | Exit 0, dimension details shown |
| `test_get_json` | Same, `-o json` | Valid JSON |
| `test_get_api_error` | HttpError | Exit 1 |

##### Class: `TestCustomDimensionsCreate`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_create_event_scope` | `create().execute()` → new dimension | Exit 0, dimension printed, scope=EVENT in body |
| `test_create_user_scope` | Same with `--scope USER` | scope=USER in body |
| `test_create_item_scope` | Same with `--scope ITEM` | scope=ITEM in body |
| `test_create_invalid_scope` | `--scope INVALID` | Exit != 0, error |
| `test_create_requires_parameter_name` | Missing `--parameter-name` | Exit != 0 |
| `test_create_requires_display_name` | Missing `--display-name` | Exit != 0 |
| `test_create_api_error` | HttpError | Exit 1 |

##### Class: `TestCustomDimensionsUpdate`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_update_display_name` | `patch().execute()` | Exit 0, `updateMask` = `"displayName"` |
| `test_update_description` | Same | `updateMask` = `"description"` |
| `test_update_both_fields` | Same | `updateMask` contains both fields |
| `test_update_no_fields` | No optional fields given | Exit != 0 |
| `test_update_api_error` | HttpError | Exit 1 |

##### Class: `TestCustomDimensionsArchive`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_archive_with_yes` | `archive().execute()`, `--yes` | Exit 0, success message |
| `test_archive_prompts_without_yes` | Mock `typer.confirm` | `confirm` was called |
| `test_archive_api_error` | HttpError | Exit 1 |

---

### WS-A2: Custom Metrics

**Goal:** Add `ga custom-metrics` command group with `list`, `get`, `create`, `update`, and `archive` subcommands.

**API reference:**
- `GET v1beta/{parent=properties/*}/customMetrics` (list)
- `GET v1beta/{name=properties/*/customMetrics/*}` (get)
- `POST v1beta/{parent=properties/*}/customMetrics` (create)
- `PATCH v1beta/{customMetric.name=properties/*/customMetrics/*}` (patch)
- `POST v1beta/{name=properties/*/customMetrics/*}:archive` (archive)

Custom metrics extend GA4 with property-specific numeric measurements from event parameters.

#### Files to create
- `src/ga_cli/commands/custom_metrics.py`
- `tests/test_custom_metrics.py`

#### Files to modify
- `src/ga_cli/main.py` — register `custom_metrics_app`

#### Implementation details

##### `custom_metrics.py`
Structure mirrors WS-A1 (custom dimensions) with these differences:

- **create** parameters:
  ```python
  @custom_metrics_app.command("create")
  def create_cmd(
      property_id: str = typer.Option(..., "--property-id", "-p"),
      parameter_name: str = typer.Option(..., "--parameter-name"),
      display_name: str = typer.Option(..., "--display-name"),
      scope: str = typer.Option(..., "--scope", help="EVENT only"),
      measurement_unit: str = typer.Option(..., "--measurement-unit", help="STANDARD, CURRENCY, FEET, METERS, KILOMETERS, MILES, MILLISECONDS, SECONDS, MINUTES, HOURS"),
      description: str = typer.Option("", "--description"),
      output_format: Optional[str] = typer.Option(None, "--output", "-o"),
  ):
  ```
- Body includes `measurementUnit` field
- **update** can modify `displayName`, `description`, `measurementUnit`
- Table columns: Name, Parameter Name, Display Name, Scope, Measurement Unit, Description

#### Tests (`tests/test_custom_metrics.py`)

Mirror the test structure from WS-A1, adjusted for metric-specific fields:

##### Classes: `TestCustomMetricsList`, `TestCustomMetricsGet`, `TestCustomMetricsCreate`, `TestCustomMetricsUpdate`, `TestCustomMetricsArchive`

Key additional tests:
| Test | Assert |
|------|--------|
| `test_create_with_currency_unit` | `measurementUnit = "CURRENCY"` in body |
| `test_create_invalid_measurement_unit` | Exit != 0 |
| `test_update_measurement_unit` | `updateMask` includes `measurementUnit` |

---

### WS-A3: Key Events

**Goal:** Add `ga key-events` command group with `list`, `get`, `create`, `update`, and `delete` subcommands.

**API reference:**
- `GET v1beta/{parent=properties/*}/keyEvents` (list)
- `GET v1beta/{name=properties/*/keyEvents/*}` (get)
- `POST v1beta/{parent=properties/*}/keyEvents` (create)
- `PATCH v1beta/{keyEvent.name=properties/*/keyEvents/*}` (patch)
- `DELETE v1beta/{name=properties/*/keyEvents/*}` (delete)

Key events (formerly "conversions") mark significant user actions that you want to track in GA4. They replace the deprecated `conversionEvents` resource.

#### Files to create
- `src/ga_cli/commands/key_events.py`
- `tests/test_key_events.py`

#### Files to modify
- `src/ga_cli/main.py` — register `key_events_app`

#### Implementation details

##### `key_events.py`
```python
key_events_app = typer.Typer(name="key-events", help="Manage key events (conversions)")

@key_events_app.command("list")
def list_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `admin.properties().keyEvents().list(parent=f"properties/{property_id}").execute()`
- Table columns: Name, Event Name, Create Time, Deletable, Custom, Counting Method

```python
@key_events_app.command("get")
def get_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    key_event_id: str = typer.Option(..., "--key-event-id", "-k"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```

```python
@key_events_app.command("create")
def create_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    event_name: str = typer.Option(..., "--event-name", "-e", help="Event name to mark as key event"),
    counting_method: str = typer.Option("ONCE_PER_EVENT", "--counting-method", help="ONCE_PER_EVENT or ONCE_PER_SESSION"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Body: `{"eventName": ..., "countingMethod": ...}`
- Validate counting method

```python
@key_events_app.command("update")
def update_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    key_event_id: str = typer.Option(..., "--key-event-id", "-k"),
    counting_method: str = typer.Option(None, "--counting-method"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Only `countingMethod` and `defaultValue` are updatable

```python
@key_events_app.command("delete")
def delete_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    key_event_id: str = typer.Option(..., "--key-event-id", "-k"),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
```
- Confirm unless `--yes`

#### Tests (`tests/test_key_events.py`)

##### Classes: `TestKeyEventsList`, `TestKeyEventsGet`, `TestKeyEventsCreate`, `TestKeyEventsUpdate`, `TestKeyEventsDelete`

| Test | What to mock | Assert |
|------|-------------|--------|
| `test_list_table` | `keyEvents().list().execute()` → 3 events | Exit 0, 3 rows |
| `test_list_empty` | Empty | Exit 0, "No key events" |
| `test_get_details` | `get().execute()` → event | Exit 0, details shown |
| `test_create_once_per_event` | `create().execute()` | countingMethod = ONCE_PER_EVENT in body |
| `test_create_once_per_session` | Same, `--counting-method ONCE_PER_SESSION` | countingMethod = ONCE_PER_SESSION |
| `test_create_invalid_counting` | `--counting-method INVALID` | Exit != 0 |
| `test_update_counting_method` | `patch().execute()` | updateMask correct |
| `test_delete_with_yes` | `delete().execute()`, `--yes` | Exit 0 |
| `test_delete_confirms` | Mock `typer.confirm` | confirm was called |
| `test_delete_api_error` | HttpError | Exit 1 |

---

### WS-A4: Measurement Protocol Secrets

**Goal:** Add `ga measurement-protocol-secrets` command group (nested under data streams) with `list`, `get`, `create`, `update`, and `delete`.

**API reference:**
- `GET v1beta/{parent=properties/*/dataStreams/*}/measurementProtocolSecrets` (list)
- `GET v1beta/{name=properties/*/dataStreams/*/measurementProtocolSecrets/*}` (get)
- `POST v1beta/{parent=properties/*/dataStreams/*}/measurementProtocolSecrets` (create)
- `PATCH v1beta/{measurementProtocolSecret.name=...}` (patch)
- `DELETE v1beta/{name=properties/*/dataStreams/*/measurementProtocolSecrets/*}` (delete)

Measurement Protocol secrets are API secrets used to validate hits sent via the GA4 Measurement Protocol (server-side event collection).

#### Files to create
- `src/ga_cli/commands/mp_secrets.py`
- `tests/test_mp_secrets.py`

#### Files to modify
- `src/ga_cli/main.py` — register `mp_secrets_app`

#### Implementation details

##### `mp_secrets.py`
```python
mp_secrets_app = typer.Typer(name="mp-secrets", help="Manage Measurement Protocol secrets")

@mp_secrets_app.command("list")
def list_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `admin.properties().dataStreams().measurementProtocolSecrets().list(parent=f"properties/{property_id}/dataStreams/{stream_id}").execute()`
- Table columns: Name, Display Name, Secret Value (masked by default)

```python
@mp_secrets_app.command("get")
def get_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    secret_id: str = typer.Option(..., "--secret-id"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```

```python
@mp_secrets_app.command("create")
def create_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    display_name: str = typer.Option(..., "--display-name"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Body: `{"displayName": ...}`
- The API auto-generates the `secretValue`

```python
@mp_secrets_app.command("update")
def update_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    secret_id: str = typer.Option(..., "--secret-id"),
    display_name: str = typer.Option(..., "--display-name"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```

```python
@mp_secrets_app.command("delete")
def delete_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    secret_id: str = typer.Option(..., "--secret-id"),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
```

#### Tests (`tests/test_mp_secrets.py`)

##### Classes: `TestMPSecretsList`, `TestMPSecretsGet`, `TestMPSecretsCreate`, `TestMPSecretsUpdate`, `TestMPSecretsDelete`

| Test | What to mock | Assert |
|------|-------------|--------|
| `test_list_secrets` | `measurementProtocolSecrets().list().execute()` → 2 secrets | Exit 0, 2 rows |
| `test_list_empty` | Empty response | Exit 0, "No secrets" |
| `test_get_secret` | `get().execute()` → secret with value | Exit 0, details shown |
| `test_create_secret` | `create().execute()` → new secret | Exit 0, secretValue shown |
| `test_update_display_name` | `patch().execute()` | updateMask = "displayName" |
| `test_delete_with_yes` | `delete().execute()`, `--yes` | Exit 0 |
| `test_requires_property_and_stream` | Missing either | Exit != 0 |
| `test_api_error` | HttpError on each operation | Exit 1 |

---

### WS-A5: Google Ads Links

**Goal:** Add `ga google-ads-links` command group with `list`, `create`, `update`, and `delete`.

**API reference:**
- `GET v1beta/{parent=properties/*}/googleAdsLinks` (list)
- `POST v1beta/{parent=properties/*}/googleAdsLinks` (create)
- `PATCH v1beta/{googleAdsLink.name=properties/*/googleAdsLinks/*}` (patch)
- `DELETE v1beta/{name=properties/*/googleAdsLinks/*}` (delete)

Note: There is no `get` method — use `list` and filter client-side if needed.

#### Files to create
- `src/ga_cli/commands/google_ads_links.py`
- `tests/test_google_ads_links.py`

#### Files to modify
- `src/ga_cli/main.py` — register `google_ads_links_app`

#### Implementation details

##### `google_ads_links.py`
```python
google_ads_links_app = typer.Typer(name="google-ads-links", help="Manage Google Ads links")

@google_ads_links_app.command("list")
def list_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Table columns: Name, Customer ID, Can Manage Clients, Ads Personalization Enabled, Create Time

```python
@google_ads_links_app.command("create")
def create_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    customer_id: str = typer.Option(..., "--customer-id", help="Google Ads customer ID"),
    ads_personalization: bool = typer.Option(True, "--ads-personalization/--no-ads-personalization"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Body: `{"customerId": ..., "adsPersonalizationEnabled": ...}`

```python
@google_ads_links_app.command("update")
def update_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    link_id: str = typer.Option(..., "--link-id"),
    ads_personalization: bool = typer.Option(None, "--ads-personalization/--no-ads-personalization"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```

```python
@google_ads_links_app.command("delete")
def delete_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    link_id: str = typer.Option(..., "--link-id"),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
```

#### Tests (`tests/test_google_ads_links.py`)

##### Classes: `TestGoogleAdsLinksList`, `TestGoogleAdsLinksCreate`, `TestGoogleAdsLinksUpdate`, `TestGoogleAdsLinksDelete`

| Test | Assert |
|------|--------|
| `test_list_links` | Exit 0, links displayed |
| `test_list_empty` | Exit 0, "No Google Ads links" |
| `test_create_link` | Body has customerId |
| `test_create_no_ads_personalization` | adsPersonalizationEnabled = False |
| `test_update_ads_personalization` | updateMask correct |
| `test_delete_with_yes` | Exit 0, deleted |
| `test_delete_confirms` | confirm was called |

---

### WS-A6: Firebase Links

**Goal:** Add `ga firebase-links` command group with `list`, `create`, and `delete`.

**API reference:**
- `GET v1beta/{parent=properties/*}/firebaseLinks` (list)
- `POST v1beta/{parent=properties/*}/firebaseLinks` (create)
- `DELETE v1beta/{name=properties/*/firebaseLinks/*}` (delete)

Note: No `get` or `patch` methods exist for Firebase links. A property can have at most one Firebase link.

#### Files to create
- `src/ga_cli/commands/firebase_links.py`
- `tests/test_firebase_links.py`

#### Files to modify
- `src/ga_cli/main.py` — register `firebase_links_app`

#### Implementation details

##### `firebase_links.py`
```python
firebase_links_app = typer.Typer(name="firebase-links", help="Manage Firebase links")

@firebase_links_app.command("list")
def list_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Table columns: Name, Project, Create Time

```python
@firebase_links_app.command("create")
def create_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    project: str = typer.Option(..., "--project", help="Firebase project resource name"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Body: `{"project": ...}`

```python
@firebase_links_app.command("delete")
def delete_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    link_id: str = typer.Option(..., "--link-id"),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
```

#### Tests (`tests/test_firebase_links.py`)

##### Classes: `TestFirebaseLinksList`, `TestFirebaseLinksCreate`, `TestFirebaseLinksDelete`

| Test | Assert |
|------|--------|
| `test_list_links` | Exit 0, link shown |
| `test_list_empty` | "No Firebase links" |
| `test_create_link` | Body has project |
| `test_delete_with_yes` | Exit 0 |
| `test_delete_confirms` | confirm called |

---

### WS-A7: Account Summaries

**Goal:** Add `ga account-summaries list` for a quick overview of all accessible accounts and their properties.

**API reference:** `GET v1beta/accountSummaries`

Account summaries provide a lightweight view of all accounts and their property summaries without needing to call `accounts.list` + `properties.list` separately.

#### Files to create
- `src/ga_cli/commands/account_summaries.py`
- `tests/test_account_summaries.py`

#### Files to modify
- `src/ga_cli/main.py` — register `account_summaries_app`

#### Implementation details

##### `account_summaries.py`
```python
account_summaries_app = typer.Typer(name="account-summaries", help="View account summaries")

@account_summaries_app.command("list")
def list_cmd(
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `admin.accountSummaries().list().execute()` with pagination
- Response contains `accountSummaries` array, each with:
  - `name`, `account`, `displayName`
  - `propertySummaries` array with `property`, `displayName`, `propertyType`, `parent`
- Table output: flatten into Account Name | Account ID | Property Name | Property ID | Property Type
- JSON output: raw response

#### Tests (`tests/test_account_summaries.py`)

##### Class: `TestAccountSummariesList`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_list_table` | `accountSummaries().list().execute()` → 2 accounts with properties | Exit 0, all accounts and properties shown |
| `test_list_empty` | Empty response | Exit 0, "No accounts" message |
| `test_list_json` | Standard mock, `-o json` | Valid JSON |
| `test_list_pagination` | Mock paginated response | All pages fetched |
| `test_list_api_error` | HttpError | Exit 1 |

---

### WS-A8: Properties — Patch

**Goal:** Add `ga properties update` command to update property fields.

**API reference:** `PATCH v1beta/{property.name=properties/*}`

Currently properties can be created and deleted, but not updated. This adds the ability to change display name, time zone, currency code, and industry category.

#### Files to modify
- `src/ga_cli/commands/properties.py` — add `update_cmd`
- `tests/test_properties.py` — add `TestPropertiesUpdate` class

#### Implementation details

##### `update_cmd` in `properties.py`
```python
@properties_app.command("update")
def update_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    name: str = typer.Option(None, "--name", help="New display name"),
    timezone: str = typer.Option(None, "--timezone", help="Reporting time zone (e.g., America/New_York)"),
    currency: str = typer.Option(None, "--currency", help="Currency code (e.g., USD, EUR)"),
    industry: str = typer.Option(None, "--industry", help="Industry category"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Build body and `updateMask` dynamically from provided options:
  - `--name` → `displayName`
  - `--timezone` → `timeZone`
  - `--currency` → `currencyCode`
  - `--industry` → `industryCategory`
- Require at least one field
- Call `admin.properties().patch(name=f"properties/{property_id}", body=body, updateMask=mask).execute()`

#### Tests (in `tests/test_properties.py`)

##### Class: `TestPropertiesUpdate`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_update_name` | `patch().execute()` | updateMask = "displayName" |
| `test_update_timezone` | Same | updateMask = "timeZone" |
| `test_update_currency` | Same | updateMask = "currencyCode" |
| `test_update_multiple_fields` | `--name X --timezone Y` | updateMask contains both |
| `test_update_no_fields` | No optional flags | Exit != 0, error |
| `test_update_json_output` | Standard mock, `-o json` | Valid JSON |
| `test_update_api_error` | HttpError | Exit 1 |

---

### WS-A9: Data Streams — Patch

**Goal:** Add `ga data-streams update` command to update data stream fields.

**API reference:** `PATCH v1beta/{dataStream.name=properties/*/dataStreams/*}`

#### Files to modify
- `src/ga_cli/commands/data_streams.py` — add `update_cmd`
- `tests/test_data_streams.py` — add `TestDataStreamsUpdate` class

#### Implementation details

##### `update_cmd` in `data_streams.py`
```python
@data_streams_app.command("update")
def update_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    display_name: str = typer.Option(None, "--display-name"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Build `updateMask` from provided fields
- Call `admin.properties().dataStreams().patch(name=..., body=body, updateMask=mask).execute()`

#### Tests (in `tests/test_data_streams.py`)

##### Class: `TestDataStreamsUpdate`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_update_display_name` | `patch().execute()` | updateMask = "displayName" |
| `test_update_no_fields` | No optional flags | Exit != 0 |
| `test_update_json_output` | Standard mock, `-o json` | Valid JSON |
| `test_update_api_error` | HttpError | Exit 1 |

---

### WS-A10: Data Retention Settings

**Goal:** Add `ga properties data-retention get` and `ga properties data-retention update`.

**API reference:**
- `GET v1beta/{name=properties/*/dataRetentionSettings}`
- `PATCH v1beta/{dataRetentionSettings.name=properties/*/dataRetentionSettings}`

Controls how long event-level and user-level data is retained before automatic deletion.

#### Files to create
- `src/ga_cli/commands/data_retention.py`
- `tests/test_data_retention.py`

#### Files to modify
- `src/ga_cli/main.py` — register `data_retention_app`

#### Implementation details

##### `data_retention.py`
```python
data_retention_app = typer.Typer(name="data-retention", help="Manage data retention settings")

@data_retention_app.command("get")
def get_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `admin.properties().getDataRetentionSettings(name=f"properties/{property_id}/dataRetentionSettings").execute()`
- Response: `eventDataRetention` (TWO_MONTHS, FOURTEEN_MONTHS, TWENTY_SIX_MONTHS, THIRTY_EIGHT_MONTHS, FIFTY_MONTHS), `resetUserDataOnNewActivity`

```python
@data_retention_app.command("update")
def update_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    event_retention: str = typer.Option(None, "--event-retention", help="TWO_MONTHS, FOURTEEN_MONTHS, TWENTY_SIX_MONTHS, THIRTY_EIGHT_MONTHS, or FIFTY_MONTHS"),
    reset_on_activity: bool = typer.Option(None, "--reset-on-activity/--no-reset-on-activity"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Build updateMask and body from provided options
- Call `admin.properties().updateDataRetentionSettings(name=..., body=body, updateMask=mask).execute()`

#### Tests (`tests/test_data_retention.py`)

##### Class: `TestDataRetentionGet`
| Test | Assert |
|------|--------|
| `test_get_table` | Settings shown |
| `test_get_json` | Valid JSON |
| `test_get_api_error` | Exit 1 |

##### Class: `TestDataRetentionUpdate`
| Test | Assert |
|------|--------|
| `test_update_event_retention` | updateMask = "eventDataRetention" |
| `test_update_reset_on_activity` | updateMask = "resetUserDataOnNewActivity" |
| `test_update_both` | Both in updateMask |
| `test_update_invalid_retention` | Exit != 0 |
| `test_update_no_fields` | Exit != 0 |

---

### WS-A11: Change History

**Goal:** Add `ga accounts change-history` to search change history events.

**API reference:** `POST v1beta/{account=accounts/*}:searchChangeHistoryEvents`

Provides an audit log of configuration changes (property creation, user additions, setting changes, etc.) within an account.

#### Files to modify
- `src/ga_cli/commands/accounts.py` — add `change_history_cmd`
- `tests/test_accounts.py` — add `TestChangeHistory` class

#### Implementation details

##### `change_history_cmd` in `accounts.py`
```python
@accounts_app.command("change-history")
def change_history_cmd(
    account_id: str = typer.Option(..., "--account-id", "-a"),
    property_id: str = typer.Option(None, "--property-id", "-p", help="Filter to specific property"),
    resource_type: str = typer.Option(None, "--resource-type", help="Filter by resource type (ACCOUNT, PROPERTY, etc.)"),
    action: str = typer.Option(None, "--action", help="Filter by action (CREATED, UPDATED, DELETED)"),
    earliest_change_time: str = typer.Option(None, "--since", help="ISO 8601 timestamp"),
    latest_change_time: str = typer.Option(None, "--until", help="ISO 8601 timestamp"),
    limit: int = typer.Option(100, "--limit", "-l"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Build request body with optional filters
- Call `admin.accounts().searchChangeHistoryEvents(account=f"accounts/{account_id}", body=body).execute()`
- Response: `changeHistoryEvents` array with `changeTime`, `actorType`, `userActorEmail`, `changesFiltered`, `changes` (with resource type, action, old/new values)
- Table output: Time, Actor, Resource, Action, Resource Name
- Paginate with `pageToken`

#### Tests (in `tests/test_accounts.py`)

##### Class: `TestChangeHistory`
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_list_changes_table` | `searchChangeHistoryEvents().execute()` → 3 events | Exit 0, 3 rows |
| `test_filter_by_property` | Pass `--property-id 123` | Body contains property filter |
| `test_filter_by_action` | Pass `--action CREATED` | Body contains action filter |
| `test_filter_by_resource_type` | Pass `--resource-type PROPERTY` | Body contains resourceType filter |
| `test_json_output` | Standard mock, `-o json` | Valid JSON |
| `test_empty_history` | Empty response | Exit 0, "No changes found" |
| `test_api_error` | HttpError | Exit 1 |

---

### WS-A12: Access Reports

**Goal:** Add `ga accounts access-report` and `ga properties access-report` to run data access reports.

**API reference:**
- `POST v1beta/{entity=accounts/*}:runAccessReport`
- `POST v1beta/{entity=properties/*}:runAccessReport`

Data access reports show who accessed GA data, when, and what they accessed. Useful for compliance and auditing.

#### Files to modify
- `src/ga_cli/commands/accounts.py` — add `access_report_cmd`
- `src/ga_cli/commands/properties.py` — add `access_report_cmd`
- `tests/test_accounts.py` — add `TestAccessReport` class
- `tests/test_properties.py` — add `TestAccessReport` class

#### Implementation details

Both commands share nearly identical logic; consider a shared helper in `utils/`.

```python
@accounts_app.command("access-report")
def access_report_cmd(
    account_id: str = typer.Option(..., "--account-id", "-a"),
    start_date: str = typer.Option("28daysAgo", "--start-date"),
    end_date: str = typer.Option("yesterday", "--end-date"),
    dimensions: str = typer.Option(None, "--dimensions", "-d", help="e.g., accessorEmail,accessMechanism"),
    metrics: str = typer.Option("accessCount", "--metrics", "-m"),
    limit: int = typer.Option(100, "--limit", "-l"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Build body matching `RunAccessReportRequest` format
- Supported dimensions: `accessorEmail`, `accessMechanism`, `epochTimeMicros`, `mostRecentAccessEpochTimeMicros`, `subpropertyId`
- Supported metrics: `accessCount`
- Call `admin.accounts().runAccessReport(entity=f"accounts/{account_id}", body=body).execute()`

The property version is identical but uses `entity=f"properties/{property_id}"`.

#### Tests

##### Class: `TestAccessReport` (in both test files)
| Test | What to mock | Assert |
|------|-------------|--------|
| `test_access_report_table` | `runAccessReport().execute()` → sample data | Exit 0, data shown |
| `test_access_report_json` | Same, `-o json` | Valid JSON |
| `test_access_report_with_dimensions` | Pass `--dimensions accessorEmail` | Body has dimensions |
| `test_access_report_empty` | Empty response | Exit 0, "No data" |
| `test_access_report_api_error` | HttpError | Exit 1 |

---

### WS-A13: Accounts — Delete

**Goal:** Add `ga accounts delete` for soft-deleting an account.

**API reference:** `DELETE v1beta/{name=accounts/*}`

Marks an account as soft-deleted. The account can be restored within 35 days.

#### Files to modify
- `src/ga_cli/commands/accounts.py` — add `delete_cmd`
- `tests/test_accounts.py` — add `TestAccountsDelete` class

#### Implementation details

```python
@accounts_app.command("delete")
def delete_cmd(
    account_id: str = typer.Option(..., "--account-id", "-a"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
```
- Confirm with warning: "This will soft-delete account {account_id}. It can be restored within 35 days."
- Call `admin.accounts().delete(name=f"accounts/{account_id}").execute()`

#### Tests (in `tests/test_accounts.py`)

##### Class: `TestAccountsDelete`
| Test | Assert |
|------|--------|
| `test_delete_with_yes` | Exit 0, success message |
| `test_delete_confirms` | `typer.confirm` called |
| `test_delete_api_error` | Exit 1 |

---

### WS-A14: Acknowledge User Data Collection

**Goal:** Add `ga properties acknowledge-data-collection`.

**API reference:** `POST v1beta/{property=properties/*}:acknowledgeUserDataCollection`

Acknowledges the terms of user data collection for a property. Required before data collection can begin.

#### Files to modify
- `src/ga_cli/commands/properties.py` — add `acknowledge_cmd`
- `tests/test_properties.py` — add `TestAcknowledgeDataCollection` class

#### Implementation details

```python
@properties_app.command("acknowledge-data-collection")
def acknowledge_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    acknowledgement: str = typer.Option(..., "--acknowledgement", help="Acknowledgement text as required by API"),
):
```
- Body: `{"acknowledgement": ...}`
- Call `admin.properties().acknowledgeUserDataCollection(property=f"properties/{property_id}", body=body).execute()`

#### Tests (in `tests/test_properties.py`)

##### Class: `TestAcknowledgeDataCollection`
| Test | Assert |
|------|--------|
| `test_acknowledge_success` | Exit 0 |
| `test_acknowledge_api_error` | Exit 1 |

---

### WS-A15: Data Sharing Settings

**Goal:** Add `ga accounts data-sharing-settings` to view data sharing settings.

**API reference:** `GET v1beta/{name=accounts/*/dataSharingSettings}`

Read-only endpoint that shows the account's data sharing settings with Google products and services.

#### Files to modify
- `src/ga_cli/commands/accounts.py` — add `data_sharing_cmd`
- `tests/test_accounts.py` — add `TestDataSharingSettings` class

#### Implementation details

```python
@accounts_app.command("data-sharing-settings")
def data_sharing_cmd(
    account_id: str = typer.Option(..., "--account-id", "-a"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- Call `admin.accounts().getDataSharingSettings(name=f"accounts/{account_id}/dataSharingSettings").execute()`
- Response fields: `sharingWithGoogleSupportEnabled`, `sharingWithGoogleAssignedSalesEnabled`, `sharingWithGoogleAnySalesEnabled`, `sharingWithGoogleProductsEnabled`, `sharingWithOthersEnabled`
- Table output: setting name + enabled/disabled

#### Tests (in `tests/test_accounts.py`)

##### Class: `TestDataSharingSettings`
| Test | Assert |
|------|--------|
| `test_get_table` | Exit 0, settings shown |
| `test_get_json` | Valid JSON |
| `test_api_error` | Exit 1 |

---

## Admin API v1alpha Workstreams

> **Note:** Alpha API methods may have breaking changes. These workstreams require using the `v1alpha` API version. The CLI should build a separate alpha Admin API client in `api/client.py`: `build("analyticsadmin", "v1alpha", credentials=creds)`.

---

### WS-AA1: Audiences

**Goal:** Add `ga audiences` command group with `list`, `get`, `create`, `update`, and `archive`.

**API reference:**
- `GET v1alpha/{parent=properties/*}/audiences` (list)
- `GET v1alpha/{name=properties/*/audiences/*}` (get)
- `POST v1alpha/{parent=properties/*}/audiences` (create)
- `PATCH v1alpha/{audience.name=properties/*/audiences/*}` (patch)
- `POST v1alpha/{name=properties/*/audiences/*}:archive` (archive)

Audiences define segments of users based on attributes and behaviors for use in reporting and ad targeting.

#### Files to create
- `src/ga_cli/commands/audiences.py`
- `tests/test_audiences.py`

#### Files to modify
- `src/ga_cli/main.py` — register `audiences_app`
- `src/ga_cli/api/client.py` — add `get_admin_alpha_client()`

#### Implementation details

##### Alpha admin client in `api/client.py`
```python
_admin_alpha_client = None

def get_admin_alpha_client():
    global _admin_alpha_client
    if _admin_alpha_client is None:
        creds = resolve_credentials()
        _admin_alpha_client = build("analyticsadmin", "v1alpha", credentials=creds)
    return _admin_alpha_client
```

##### `audiences.py`
- **list**: Table columns: Name, Display Name, Description, Membership Duration Days, Ads Personalization Enabled
- **get**: Full audience details including filter clauses
- **create**: Accept `--config` JSON file for audience definition (complex filter clauses are too large for CLI flags):
  ```json
  {
    "displayName": "Purchasers",
    "description": "Users who completed a purchase",
    "membershipDurationDays": 30,
    "filterClauses": [
      {
        "clauseType": "INCLUDE",
        "simpleFilter": {
          "scope": "AUDIENCE_FILTER_SCOPE_ACROSS_ALL_SESSIONS",
          "filterExpression": {
            "eventFilter": {"eventName": "purchase"}
          }
        }
      }
    ]
  }
  ```
- **update**: Accept `--config` JSON or `--display-name` / `--description` flags
- **archive**: Confirm before archiving

#### Tests (`tests/test_audiences.py`)

##### Classes: `TestAudiencesList`, `TestAudiencesGet`, `TestAudiencesCreate`, `TestAudiencesUpdate`, `TestAudiencesArchive`

Standard CRUD test patterns (list empty/populated, get details, create with config, update with mask, archive with confirmation).

---

### WS-AA2: BigQuery Links

**Goal:** Add `ga bigquery-links` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:**
- `GET v1alpha/{parent=properties/*}/bigQueryLinks` (list)
- `GET v1alpha/{name=properties/*/bigQueryLinks/*}` (get)
- `POST v1alpha/{parent=properties/*}/bigQueryLinks` (create)
- `PATCH v1alpha/{bigqueryLink.name=properties/*/bigQueryLinks/*}` (patch)
- `DELETE v1alpha/{name=properties/*/bigQueryLinks/*}` (delete)

Manages the link between a GA4 property and a BigQuery project for data export.

#### Files to create
- `src/ga_cli/commands/bigquery_links.py`
- `tests/test_bigquery_links.py`

#### Files to modify
- `src/ga_cli/main.py` — register `bigquery_links_app`

#### Implementation details

- **create** flags: `--project` (BQ project ID), `--daily-export/--no-daily-export`, `--streaming-export/--no-streaming-export`, `--include-advertising-id/--no-include-advertising-id`, `--fresh-daily-export/--no-fresh-daily-export`
- **update**: Modify export settings
- Table columns: Name, Project, Daily Export, Streaming Export, Create Time

#### Tests (`tests/test_bigquery_links.py`)

Standard CRUD test patterns.

---

### WS-AA3: Channel Groups

**Goal:** Add `ga channel-groups` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:**
- `GET v1alpha/{parent=properties/*}/channelGroups` (list)
- `GET v1alpha/{name=properties/*/channelGroups/*}` (get)
- `POST v1alpha/{parent=properties/*}/channelGroups` (create)
- `PATCH v1alpha/{channelGroup.name=properties/*/channelGroups/*}` (patch)
- `DELETE v1alpha/{name=properties/*/channelGroups/*}` (delete)

Custom channel groups define how traffic sources are categorized beyond the default channel grouping.

#### Files to create
- `src/ga_cli/commands/channel_groups.py`
- `tests/test_channel_groups.py`

#### Files to modify
- `src/ga_cli/main.py` — register `channel_groups_app`

#### Implementation details

- **create/update**: Accept `--config` JSON file (channel group rules are complex nested structures)
- Table columns: Name, Display Name, Description, System Defined (bool)

#### Tests (`tests/test_channel_groups.py`)

Standard CRUD test patterns.

---

### WS-AA4: Calculated Metrics

**Goal:** Add `ga calculated-metrics` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:**
- `GET v1alpha/{parent=properties/*}/calculatedMetrics` (list)
- `GET v1alpha/{name=properties/*/calculatedMetrics/*}` (get)
- `POST v1alpha/{parent=properties/*}/calculatedMetrics` (create)
- `PATCH v1alpha/{calculatedMetric.name=properties/*/calculatedMetrics/*}` (patch)
- `DELETE v1alpha/{name=properties/*/calculatedMetrics/*}` (delete)

Calculated metrics are derived metrics defined by a formula over existing metrics (e.g., revenue per user = totalRevenue / totalUsers).

#### Files to create
- `src/ga_cli/commands/calculated_metrics.py`
- `tests/test_calculated_metrics.py`

#### Files to modify
- `src/ga_cli/main.py` — register `calculated_metrics_app`

#### Implementation details

- **create** flags: `--calculated-metric-id`, `--display-name`, `--description`, `--formula` (e.g., `"{{totalRevenue}} / {{totalUsers}}"`), `--metric-unit` (STANDARD, CURRENCY, etc.)
- **update**: Modify display name, description, formula, metric unit
- Table columns: Name, Calculated Metric ID, Display Name, Formula, Metric Unit

#### Tests (`tests/test_calculated_metrics.py`)

Standard CRUD test patterns + formula validation tests.

---

### WS-AA5: Event Create Rules

**Goal:** Add `ga event-create-rules` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:**
- `GET v1alpha/{parent=properties/*/dataStreams/*}/eventCreateRules` (list)
- `GET v1alpha/{name=properties/*/dataStreams/*/eventCreateRules/*}` (get)
- `POST v1alpha/{parent=properties/*/dataStreams/*}/eventCreateRules` (create)
- `PATCH v1alpha/{eventCreateRule.name=...}` (patch)
- `DELETE v1alpha/{name=properties/*/dataStreams/*/eventCreateRules/*}` (delete)

Event create rules generate new events based on conditions applied to existing events within a data stream.

#### Files to create
- `src/ga_cli/commands/event_create_rules.py`
- `tests/test_event_create_rules.py`

#### Files to modify
- `src/ga_cli/main.py` — register `event_create_rules_app`

#### Implementation details

- All commands require both `--property-id` and `--stream-id`
- **create/update**: Accept `--config` JSON file (rules have complex condition/action structures)
- Table columns: Name, Destination Event, Conditions Count

#### Tests (`tests/test_event_create_rules.py`)

Standard CRUD test patterns. All tests must mock with full parent path `properties/{id}/dataStreams/{id}`.

---

### WS-AA6: Event Edit Rules

**Goal:** Add `ga event-edit-rules` command group with `list`, `get`, `create`, `update`, `delete`, and `reorder`.

**API reference:**
- `GET v1alpha/{parent=properties/*/dataStreams/*}/eventEditRules` (list)
- `GET v1alpha/{name=properties/*/dataStreams/*/eventEditRules/*}` (get)
- `POST v1alpha/{parent=properties/*/dataStreams/*}/eventEditRules` (create)
- `PATCH v1alpha/{eventEditRule.name=...}` (patch)
- `DELETE v1alpha/{name=properties/*/dataStreams/*/eventEditRules/*}` (delete)
- `POST v1alpha/{parent=properties/*/dataStreams/*}/eventEditRules:reorder` (reorder)

Event edit rules modify event data (e.g., rename events, add/remove parameters) as it flows through a data stream. Order matters — rules are applied sequentially.

#### Files to create
- `src/ga_cli/commands/event_edit_rules.py`
- `tests/test_event_edit_rules.py`

#### Files to modify
- `src/ga_cli/main.py` — register `event_edit_rules_app`

#### Implementation details

Same structure as WS-AA5 plus:

```python
@event_edit_rules_app.command("reorder")
def reorder_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    rule_ids: str = typer.Option(..., "--rule-ids", help="Comma-separated rule IDs in desired order"),
):
```
- Body: `{"eventEditRules": ["properties/.../eventEditRules/1", "properties/.../eventEditRules/2"]}`

#### Tests (`tests/test_event_edit_rules.py`)

Standard CRUD patterns + `TestReorder` class.

---

### WS-AA7: Access Bindings

**Goal:** Add `ga access-bindings` command group for managing user access at account and property levels.

**API reference:** (v1alpha only)
- Account-level: `accounts.accessBindings.*` (batchCreate, batchDelete, batchGet, batchUpdate, create, delete, get, list, patch)
- Property-level: `properties.accessBindings.*` (same methods)

Access bindings grant users roles on accounts or properties.

#### Files to create
- `src/ga_cli/commands/access_bindings.py`
- `tests/test_access_bindings.py`

#### Files to modify
- `src/ga_cli/main.py` — register `access_bindings_app`

#### Implementation details

```python
access_bindings_app = typer.Typer(name="access-bindings", help="Manage user access bindings")
```

- Commands: `list`, `get`, `create`, `update`, `delete`
- Each command accepts either `--account-id` or `--property-id` to determine the parent level
- **create** flags: `--user` (email), `--roles` (comma-separated role names like `predefinedRoles/viewer`, `predefinedRoles/editor`, `predefinedRoles/admin`)
- **update**: Modify roles
- Batch operations (`batch-create`, `batch-delete`, `batch-update`) accept `--config` JSON file
- Table columns: Name, User, Roles

#### Tests (`tests/test_access_bindings.py`)

Test both account-level and property-level access bindings. Standard CRUD patterns.

---

### WS-AA8: Reporting Data Annotations

**Goal:** Add `ga annotations` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:**
- `GET v1alpha/{parent=properties/*}/reportingDataAnnotations` (list)
- `GET v1alpha/{name=properties/*/reportingDataAnnotations/*}` (get)
- `POST v1alpha/{parent=properties/*}/reportingDataAnnotations` (create)
- `PATCH v1alpha/{reportingDataAnnotation.name=...}` (patch)
- `DELETE v1alpha/{name=properties/*/reportingDataAnnotations/*}` (delete)

Annotations mark specific dates/events on GA4 reports with contextual notes (e.g., "Launched new feature", "Marketing campaign started").

#### Files to create
- `src/ga_cli/commands/annotations.py`
- `tests/test_annotations.py`

#### Files to modify
- `src/ga_cli/main.py` — register `annotations_app`

#### Implementation details

- **create** flags: `--title`, `--description`, `--annotation-date` (YYYY-MM-DD), `--color` (optional)
- **update**: Modify title, description, color
- Table columns: Name, Title, Date, Description, Color

#### Tests (`tests/test_annotations.py`)

Standard CRUD test patterns.

---

### WS-AA9: Property Settings

**Goal:** Add commands for managing property-level settings: attribution, Google Signals, and enhanced measurement.

**API reference:**
- `GET/PATCH v1alpha/{name=properties/*/attributionSettings}` (attribution)
- `GET/PATCH v1alpha/{name=properties/*/googleSignalsSettings}` (Google Signals)
- `GET/PATCH v1alpha/{name=properties/*/dataStreams/*/enhancedMeasurementSettings}` (enhanced measurement)

#### Files to create
- `src/ga_cli/commands/property_settings.py`
- `tests/test_property_settings.py`

#### Files to modify
- `src/ga_cli/main.py` — register `property_settings_app`

#### Implementation details

##### `property_settings.py`
```python
property_settings_app = typer.Typer(name="property-settings", help="Manage property-level settings")

@property_settings_app.command("attribution")
def attribution_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    model: str = typer.Option(None, "--model", help="Set attribution model (CROSS_CHANNEL_DATA_DRIVEN, etc.)"),
    lookback_window: str = typer.Option(None, "--lookback-window", help="THIRTY_DAYS, SIXTY_DAYS, NINETY_DAYS"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```
- If no update flags: GET and display current settings
- If update flags provided: PATCH with updateMask

```python
@property_settings_app.command("google-signals")
def google_signals_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    state: str = typer.Option(None, "--state", help="Set state: GOOGLE_SIGNALS_ENABLED or GOOGLE_SIGNALS_DISABLED"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
):
```

```python
@property_settings_app.command("enhanced-measurement")
def enhanced_measurement_cmd(
    property_id: str = typer.Option(..., "--property-id", "-p"),
    stream_id: str = typer.Option(..., "--stream-id", "-s"),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
    # Boolean flags for each setting:
    page_views: bool = typer.Option(None, "--page-views/--no-page-views"),
    scrolls: bool = typer.Option(None, "--scrolls/--no-scrolls"),
    outbound_clicks: bool = typer.Option(None, "--outbound-clicks/--no-outbound-clicks"),
    site_search: bool = typer.Option(None, "--site-search/--no-site-search"),
    video_engagement: bool = typer.Option(None, "--video-engagement/--no-video-engagement"),
    file_downloads: bool = typer.Option(None, "--file-downloads/--no-file-downloads"),
    form_interactions: bool = typer.Option(None, "--form-interactions/--no-form-interactions"),
):
```
- If no update flags: GET and display current settings
- If flags provided: PATCH

#### Tests (`tests/test_property_settings.py`)

##### Classes: `TestAttributionSettings`, `TestGoogleSignalsSettings`, `TestEnhancedMeasurementSettings`

Get/update tests for each setting type.

---

### WS-AA10: Display & Video 360 Links

**Goal:** Add `ga dv360-links` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:** `properties.displayVideo360AdvertiserLinks.*` and `properties.displayVideo360AdvertiserLinkProposals.*`

#### Files to create
- `src/ga_cli/commands/dv360_links.py`
- `tests/test_dv360_links.py`

#### Files to modify
- `src/ga_cli/main.py`

#### Implementation details

Standard CRUD + proposal workflow (approve/cancel). Table columns: Name, Advertiser ID, Ads Personalization Enabled, Campaign Data Sharing Enabled.

#### Tests (`tests/test_dv360_links.py`)

Standard CRUD patterns + proposal approval/cancel tests.

---

### WS-AA11: Search Ads 360 Links

**Goal:** Add `ga sa360-links` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:** `properties.searchAds360Links.*`

#### Files to create
- `src/ga_cli/commands/sa360_links.py`
- `tests/test_sa360_links.py`

#### Files to modify
- `src/ga_cli/main.py`

#### Implementation details

Standard CRUD. Table columns: Name, Advertiser ID, Ads Personalization Enabled, Campaign Data Sharing Enabled, Cost Data Sharing Enabled.

#### Tests (`tests/test_sa360_links.py`)

Standard CRUD test patterns.

---

### WS-AA12: AdSense Links

**Goal:** Add `ga adsense-links` command group with `list`, `get`, `create`, and `delete`.

**API reference:** `properties.adSenseLinks.*`

#### Files to create
- `src/ga_cli/commands/adsense_links.py`
- `tests/test_adsense_links.py`

#### Files to modify
- `src/ga_cli/main.py`

#### Implementation details

Standard CRUD (no patch). Table columns: Name, Ad Client Code.

#### Tests (`tests/test_adsense_links.py`)

Standard CRUD test patterns (no update).

---

### WS-AA13: Expanded Data Sets

**Goal:** Add `ga expanded-data-sets` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:** `properties.expandedDataSets.*`

Expanded data sets allow larger cardinality reporting by pre-defining dimension/metric combinations.

#### Files to create
- `src/ga_cli/commands/expanded_data_sets.py`
- `tests/test_expanded_data_sets.py`

#### Files to modify
- `src/ga_cli/main.py`

#### Implementation details

- **create**: Accept `--config` JSON file for complex dimension/metric filter definitions
- Table columns: Name, Display Name, Dimensions, Metrics

#### Tests (`tests/test_expanded_data_sets.py`)

Standard CRUD test patterns.

---

### WS-AA14: Rollup Property Source Links

**Goal:** Add `ga rollup-source-links` command group with `list`, `get`, `create`, and `delete`.

**API reference:** `properties.rollupPropertySourceLinks.*`

Manages the source properties that feed into a rollup property.

#### Files to create
- `src/ga_cli/commands/rollup_source_links.py`
- `tests/test_rollup_source_links.py`

#### Files to modify
- `src/ga_cli/main.py`

#### Implementation details

Standard CRUD (no patch). Table columns: Name, Source Property.

#### Tests (`tests/test_rollup_source_links.py`)

Standard CRUD test patterns.

---

### WS-AA15: Subproperty Event Filters

**Goal:** Add `ga subproperty-event-filters` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:** `properties.subpropertyEventFilters.*`

Manages event filters that control which events flow from a source property into a subproperty.

#### Files to create
- `src/ga_cli/commands/subproperty_event_filters.py`
- `tests/test_subproperty_event_filters.py`

#### Files to modify
- `src/ga_cli/main.py`

#### Implementation details

- **create/update**: Accept `--config` JSON file for complex filter clause definitions
- Table columns: Name, Applied to Property

#### Tests (`tests/test_subproperty_event_filters.py`)

Standard CRUD test patterns.

---

### WS-AA16: SKAdNetwork Conversion Value Schema

**Goal:** Add `ga skadnetwork-schema` command group with `list`, `get`, `create`, `update`, and `delete`.

**API reference:** `properties.dataStreams.sKAdNetworkConversionValueSchema.*`

Manages Apple's SKAdNetwork conversion value schema for iOS app data streams.

#### Files to create
- `src/ga_cli/commands/skadnetwork_schema.py`
- `tests/test_skadnetwork_schema.py`

#### Files to modify
- `src/ga_cli/main.py`

#### Implementation details

- Scoped under `--property-id` and `--stream-id` (iOS data streams only)
- **create/update**: Accept `--config` JSON file (postback window schemas are complex)
- Table columns: Name, Apply Conversion Values (bool)

#### Tests (`tests/test_skadnetwork_schema.py`)

Standard CRUD test patterns. Tests must verify stream type validation (iOS only).

---

## Priority Matrix

### Tier 1 — High Value, Stable (v1beta)

| Priority | Workstream | New Commands | Impact |
|----------|-----------|-------------|--------|
| ~~1~~ | ~~WS-A1: Custom Dimensions~~ | ~~5~~ | ~~Core GA4 configuration management~~ **DONE** |
| ~~2~~ | ~~WS-A2: Custom Metrics~~ | ~~5~~ | ~~Core GA4 configuration management~~ **DONE** |
| ~~3~~ | ~~WS-A3: Key Events~~ | ~~5~~ | ~~Core conversion tracking~~ **DONE** |
| ~~4~~ | ~~WS-D1: Pivot Reports~~ | ~~1~~ | ~~Advanced reporting~~ **DONE** |
| ~~5~~ | ~~WS-D3: Check Compatibility~~ | ~~1~~ | ~~Report validation~~ **DONE** |
| ~~6~~ | ~~WS-A4: MP Secrets~~ | ~~5~~ | ~~Server-side tracking~~ **DONE** |
| ~~7~~ | ~~WS-A5: Google Ads Links~~ | ~~4~~ | ~~Common integration~~ **DONE** |
| ~~8~~ | ~~WS-A7: Account Summaries~~ | ~~1~~ | ~~Quick overview~~ **DONE** |
| ~~9~~ | ~~WS-A8: Properties Patch~~ | ~~1~~ | ~~Completes property CRUD~~ **DONE** |
| ~~10~~ | ~~WS-A9: Data Streams Patch~~ | ~~1~~ | ~~Completes data streams CRUD~~ **DONE** |
| ~~11~~ | ~~WS-D5: Expose getMetadata~~ | ~~1~~ | ~~Developer utility~~ **DONE** |
| ~~12~~ | ~~WS-A6: Firebase Links~~ | ~~3~~ | ~~Firebase integration~~ **DONE** |
| 13 | WS-A11: Change History | 1 | Audit / debugging |
| 14 | WS-D2: Batch Reports | 1 | Efficiency for multi-report |
| 15 | WS-A10: Data Retention | 2 | Compliance / governance |
| 16 | WS-A12: Access Reports | 2 | Compliance / auditing |
| 17 | WS-A13: Accounts Delete | 1 | Completes accounts CRUD |
| 18 | WS-A14: Acknowledge Data Collection | 1 | Property setup |
| 19 | WS-A15: Data Sharing Settings | 1 | Account settings |
| 20 | WS-D4: Audience Exports | 4 | Audience data workflows *(deprioritized)* |

### Tier 2 — Medium Value, Alpha

| Priority | Workstream | New Commands | Impact |
|----------|-----------|-------------|--------|
| 21 | WS-AA1: Audiences | 5 | Audience management |
| 22 | WS-AA2: BigQuery Links | 5 | BigQuery export management |
| 23 | WS-AA3: Channel Groups | 5 | Traffic categorization |
| 24 | WS-AA4: Calculated Metrics | 5 | Advanced metrics |
| 25 | WS-DA1: Funnel Reports | 1 | Funnel analysis |
| 26 | WS-AA5: Event Create Rules | 5 | Event modification |
| 27 | WS-AA6: Event Edit Rules | 6 | Event modification |
| 28 | WS-AA7: Access Bindings | 5+ | User management |
| 29 | WS-AA8: Annotations | 5 | Report annotations |
| 30 | WS-AA9: Property Settings | 3 | Advanced property config |
| 31 | WS-DA2: Property Quotas | 1 | Quota monitoring |

### Tier 3 — Niche / Low Demand

| Priority | Workstream | New Commands | Impact |
|----------|-----------|-------------|--------|
| 32 | WS-AA10: DV360 Links | 5+ | DV360 integration |
| 33 | WS-AA11: SA360 Links | 5 | SA360 integration |
| 34 | WS-AA12: AdSense Links | 4 | AdSense integration |
| 35 | WS-AA13: Expanded Data Sets | 5 | Advanced reporting |
| 36 | WS-DA3: Report Tasks | 4 | Async reporting |
| 37 | WS-AA14: Rollup Source Links | 4 | Rollup properties |
| 38 | WS-AA15: Subproperty Event Filters | 5 | Subproperty management |
| 39 | WS-AA16: SKAdNetwork Schema | 5 | iOS attribution |
