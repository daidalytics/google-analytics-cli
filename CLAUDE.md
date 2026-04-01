# CLAUDE.md

## Project overview

GA CLI is a Python command-line tool for Google Analytics 4. It wraps the GA4 Admin API and Data API, providing commands for managing accounts, properties, data streams, and running reports.

Built with Typer (CLI framework), Rich (terminal output), and google-api-python-client (API access). Managed with uv and built with hatchling.

## Architecture

```
src/ga_cli/
├── __init__.py              # Package init, version via importlib.metadata
├── main.py                  # Typer app, registers 6 command groups
├── config/
│   ├── constants.py         # OAuth scopes, paths, pagination defaults
│   └── store.py             # JSON config persistence (~/.config/ga-cli/config.json)
├── auth/
│   ├── oauth.py             # OAuth 2.0 flow (InstalledAppFlow)
│   ├── credentials.py       # Token storage/load/refresh (0o600 permissions)
│   └── service_account.py   # Service account key validation + auth
├── api/
│   └── client.py            # Cached Admin & Data API client builders
├── commands/
│   ├── auth_cmd.py          # ga auth login/logout/status
│   ├── config_cmd.py        # ga config setup/get/set/unset/path/reset
│   ├── accounts.py          # ga accounts list/get
│   ├── properties.py        # ga properties list/get/create/delete
│   ├── data_streams.py      # ga data-streams list/get/create/delete
│   └── reports.py           # ga reports run/realtime/build
└── utils/
    ├── __init__.py          # Re-exports from errors, output, pagination
    ├── errors.py            # Google API error extraction + formatting
    ├── output.py            # Rich table, JSON output, success/error/info/warn helpers
    └── pagination.py        # API pagination (paginate_all) + client-side slicing
```

## Key conventions

- **Version**: Single source of truth in `pyproject.toml`, read at runtime via `importlib.metadata.version("ga-cli")`
- **Entry point**: `ga = "ga_cli.main:run"` (defined in pyproject.toml)
- **Config directory**: `~/.config/ga-cli/` via platformdirs, overridable with `GA_CLI_CONFIG_DIR` env var
- **Output**: All read commands support `--output table|json` (default: table)
- **OAuth credentials**: Users provide their own GCP OAuth credentials via `client_secret.json` file or `GA_CLI_CLIENT_ID`/`GA_CLI_CLIENT_SECRET` env vars
- **Auth priority**: `client_secret.json` > env vars > service account
- **API clients**: Cached instances via `get_admin_client()` and `get_data_client()` in `api/client.py`

## Common commands

```bash
uv sync                        # Install dependencies
uv run ga --help               # Run the CLI
uv run pytest                  # Run tests
uv run ruff check src/ tests/  # Lint
uv build                       # Build wheel + sdist
```

## Testing

Tests live in `tests/` and run via `uv run pytest`.

- **CLI tests**: Use `typer.testing.CliRunner` to invoke commands
- **Organization**: Class-based grouping (e.g., `class TestAccountsList:`)
- **Mocking**: `unittest.mock.patch` for API calls, credentials, and external services
- **Fixtures**: `conftest.py` provides `isolated_config_dir` (autouse) which redirects `GA_CLI_CONFIG_DIR` to a temp directory and clears config cache between tests
- **No real API calls**: Everything is mocked

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Runs on push/PR to master. Tests across Python 3.10, 3.12, 3.13. Lints with ruff.
- **Release** (`.github/workflows/release.yml`): Triggered by `v*` tags. Tests, builds, publishes to TestPyPI then PyPI via OIDC trusted publishing. No secrets required.
