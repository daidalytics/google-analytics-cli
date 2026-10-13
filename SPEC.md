# Spec: Output escaping and input validation fixes

Status: **Implemented: pending release** (branch `fix/escape-and-validation`)
Target version: 0.5.0 (ships alongside the #30 breaking changes)
Previous spec (ResponseMetaData, shipped in 0.4.0): `git show 72e3a4f:SPEC.md`

---

## Objective

Six bugs found while reviewing #28–#31. Two of them change or break output for real-world
data and must be fixed. The other four are consistency and validation gaps.

Users: people running `ga` in a terminal (table output is the default there) and agents
piping `ga` into `jq`. Report values such as page titles, page paths and event parameters
are **untrusted**: anyone can send hits with arbitrary text.

| # | Issue | Severity | Root cause |
|---|-------|----------|------------|
| 1 | Table cells are parsed as Rich markup: `/search?q=[foo]bar` shows as `/search?q=bar`; `Docs [/admin] x` raises `MarkupError` and aborts the report | **High** | API text reaches Rich unescaped |
| 2 | Filter values containing `>`, `<`, `==`, `!=` split at the wrong operator | **High** | Symbol operators are tried before word operators, on the whole expression |
| 3 | `ga auth status` defaults to table on a pipe | Medium | `-o` hard-coded to `"table"` |
| 4 | Compact-mode Data Notes aren't escaped; `[/…]` raises `MarkupError` | Medium | Same as 1 |
| 5 | `--order-by country:asc:alpha:bogus` is accepted | Low | Extra segments ignored |
| 6 | `reports run --limit 0` returns up to 10,000 rows; `--limit -5` gets an API 400 | Low | No bounds on the option |

### Reproduced on master (`f04b593`)

```
_output_table([{"pagePath": "/search?q=[foo]bar"}])      → shows "/search?q=bar"
_output_table([{"pageTitle": "Docs [/admin] x"}])        → MarkupError
pageTitle contains Home > Blog                           → "Invalid numeric value: 'Blog'"
pageTitle contains a != b                                → NOT EXACT on field "pageTitle contains a"
pagePath begins_with /a==b                               → EXACT on field "pagePath begins_with /a"
country in A<B,C                                         → "Invalid numeric value: 'B,C'"
warn("Truncated: see [/docs] here")                      → MarkupError
error("API said [/x]")                                   → MarkupError (handle_error's terminal path)
parse_order_bys(["country:asc:alpha:bogus"], ...)        → accepted, "bogus" dropped
```

The last two `warn`/`error` rows widen issue 4: `handle_error()` prints API error messages
through `error()` in terminal mode, so an API error containing `[/…]` crashes with a
traceback instead of a clean error.

---

## Design

### Issues 1 + 4: escape API text at the Rich boundary

Treat every value that reaches Rich as plain text unless the CLI itself wrote the markup.

- `utils/output.py::_format_value`: return `escape(str(value))` for strings, numbers and the
  JSON of dicts. The CLI's own markup (`[green]Yes[/green]` / `[red]No[/red]` for booleans)
  stays as is.
- `_output_table`: escape the headers too. Pivot headers contain data values
  (`"{pivot value} / {metric}"`).
- `_output_object`: escape keys via `_format_header` output.
- `success`/`error`/`warn`/`info`: escape `message`. This fixes issue 4 for every caller,
  including `handle_error()`. Verified: none of the 101 current call sites passes intentional
  markup in `message`.
- `reports.py::_display_response_metadata`: the table branch keeps its explicit `escape()`.
  The compact branch needs no change once `warn()` escapes.

Not in scope: JSON output (already safe), compact TSV (already escapes control characters).

### Issue 2: anchor the field name, then match the first operator after it

GA4 API field names follow `[A-Za-z][A-Za-z0-9_]*`, optionally followed by
`:` and a name with the same characters (`customEvent:plan_type`, `keyEvents:sign_up`). Parse the
field first, then the operator that immediately follows it, so operator-like text in the
**value** is never considered:

```python
_FIELD = r"(?P<field>[A-Za-z][A-Za-z0-9_]*(?::[A-Za-z0-9_]+)*)"
_SYMBOL_FILTER = re.compile(rf"^{_FIELD}\s*(?P<op>==|!=|=~|>=|<=|>|<)\s*(?P<value>.+)$")
_WORD_FILTER = re.compile(
    rf"^{_FIELD}\s+(?P<op>contains|begins_with|ends_with|in|between)\s+(?P<value>.+)$",
    re.IGNORECASE,
)
```

| Expression | Result |
|---|---|
| `pageTitle contains Home > Blog` | CONTAINS `Home > Blog` |
| `pageTitle contains a != b` | CONTAINS `a != b` |
| `pagePath begins_with /a==b` | BEGINS_WITH `/a==b` |
| `country in A<B,C` | IN_LIST `["A<B", "C"]` |
| `pageTitle==A > B` | EXACT `A > B` (unchanged) |
| `customEvent:plan==pro` | EXACT on `customEvent:plan` |
| `page title==x` | Error: can't parse the expression, list operators |

The function's output dicts and metric handling (#29) stay unchanged. Only the matching changes.

### Issue 3: `ga auth status` uses the shared resolution

`output_format: Optional[str] = typer.Option(None, "--output", "-o", …)` and
`fmt = resolve_output_format(output_format)`, like every other read command. Terminal output
is still a table, a pipe gets JSON, and an explicit `-o` wins.

### Issue 5: reject extra `--order-by` segments

After the field is resolved, `rest` may hold at most 2 segments (direction, sort type). With
more: `BadParameter("Too many ':' segments in --order-by 'country:asc:alpha:bogus'. Format:
field[:asc|desc[:alpha|ialpha|numeric]]")`.

### Issue 6: bound `reports run --limit`

`min=1, max=250_000` (the API's `RunReportRequest.limit` maximum), matching pivot's `min=1`.
Typer then reports the usage error with exit code 2 before any API call. `realtime` takes no
`--limit`.

### API snapshot refresh

`.api-snapshots/` was last refreshed on 2026-09-12 (revision `20260909`). A check on
2026-10-13 shows revision bumps only: admin `20261011`, data `20261012`, with no semantic
changes. Refresh with `python scripts/check_api_changes.py --update` as a separate
`chore:` commit, so the weekly API Watch starts from the revision 0.5.0 ships against. If
the diff shows semantic changes by then, stop and review them before updating.

---

## Commands

```bash
uv run pytest                          # full suite (currently 1071 passed)
uv run pytest tests/test_output.py tests/test_filters.py tests/test_reports.py tests/test_auth_cmd.py -q
uv run ruff check src/ tests/
uv run ga reports run -p 250400352 …   # live checks (read-only)
```

## Project structure (files touched)

```
src/ga_cli/utils/output.py      → issues 1, 4 (escaping in _format_value, headers, message helpers)
src/ga_cli/utils/filters.py     → issues 2, 5
src/ga_cli/commands/auth_cmd.py → issue 3
src/ga_cli/commands/reports.py  → issue 6 (and the comment on the compact Data Notes branch)
tests/test_output.py, tests/test_filters.py, tests/test_auth_cmd.py, tests/test_reports.py
.api-snapshots/*.json           → snapshot refresh (generated by the script)
```

## Code style

Match the surrounding code: short docstrings, comments only where the *why* isn't obvious,
`typer.BadParameter` for user input errors, class-grouped pytest tests. Example of the
expected test shape:

```python
class TestTableEscaping:
    def test_brackets_in_values_render_literally(self, capsys):
        _output_table([{"pagePath": "/search?q=[foo]bar"}])
        assert "/search?q=[foo]bar" in capsys.readouterr().out

    def test_closing_tag_in_value_does_not_raise(self, capsys):
        _output_table([{"pageTitle": "Docs [/admin] x"}])
        assert "Docs [/admin] x" in capsys.readouterr().out
```

## Testing strategy

- **TDD, one issue at a time:** write the failing regression test from the "Reproduced" table
  first, then fix it.
- Unit tests for parsers (`test_filters.py`) and renderers (`test_output.py`). CLI tests via
  `CliRunner` for issues 3 and 6 (piped `auth status` → valid JSON; `--limit 0` → exit 2,
  no API call).
- Existing tests must keep passing unchanged, except where they assert the old buggy behaviour.
- Live smoke test on property 250400352 after all six land: a table report with bracketed
  values (if the property has any) and a filter whose value contains `>`.

## Boundaries

- **Always:** a regression test per issue; run `pytest` and `ruff` before each commit; keep
  JSON and compact-TSV output byte-identical to today.
- **Ask first:** changing any user-visible output beyond the bugs above, adding dependencies,
  releasing or tagging 0.5.0.
- **Never:** interpret report data as markup; push to master directly (go through a PR, CI
  must pass).

## Success criteria

1. Every row in the "Reproduced" table gives the result in the Design tables, and each has a
   regression test.
2. `ga auth status | jq .authenticated` prints `true`/`false`.
3. `ga reports run --limit 0` and `--limit -5` exit 2 with a usage error and make no API call.
4. Full suite and ruff pass on Python 3.10, 3.12 and 3.13 in CI.
5. No change to JSON or compact output for data without brackets.
6. `python scripts/check_api_changes.py` reports no changes after the snapshot refresh.

## Decisions

1. **Delivery:** one PR, one commit per issue.
2. **Field-name grammar (issue 2):** `[A-Za-z][A-Za-z0-9_]*(:[A-Za-z0-9_]+)*` covers every
   field name in use.
3. **Release:** part of 0.5.0, together with #30's changes.
