"""Shared fixtures for auth tests."""

import importlib
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import DefaultCredentialsError


@pytest.fixture(autouse=True)
def no_gcloud_adc(monkeypatch):
    """Never let a test reach the dev machine's real gcloud ADC.

    ``google.auth.default`` raises ``DefaultCredentialsError`` in every test,
    so credential resolution ends in "not authenticated" instead of picking up
    real credentials (or probing the GCE metadata server). A test that wants
    ADC patches ``google.auth.default`` itself, or sets this mock's
    ``side_effect``/``return_value``.

    Exported credential env vars are dropped for the same reason: tests that
    need them set their own.
    """
    monkeypatch.delenv("GA_CLI_SERVICE_ACCOUNT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    mock = MagicMock(
        side_effect=DefaultCredentialsError("gcloud ADC is disabled in tests (conftest)")
    )
    monkeypatch.setattr("google.auth.default", mock)
    return mock


@pytest.fixture(autouse=True)
def isolated_config_dir(tmp_path, monkeypatch):
    """Point GA_CLI_CONFIG_DIR to a temp dir so tests never touch real config."""
    monkeypatch.setenv("GA_CLI_CONFIG_DIR", str(tmp_path))
    # Keep a developer's own allowlist from leaking into the suite
    monkeypatch.delenv("GA_CLI_ALLOWED_ACCOUNTS", raising=False)
    monkeypatch.delenv("GA_CLI_ALLOWED_PROPERTIES", raising=False)

    # A developer may have a profile exported; every test starts on default.
    monkeypatch.delenv("GA_CLI_PROFILE", raising=False)
    from ga_cli.config.constants import set_active_profile

    set_active_profile(None)

    # Also clear the in-memory config cache between tests
    from ga_cli.config import store

    store.reset_cache()

    # Drop API clients and allowlist maps cached by a previous test (possibly
    # under another profile)
    from ga_cli.api.allowlist_guard import reset_caches
    from ga_cli.api.client import clear_client_cache

    clear_client_cache()
    reset_caches()

    # Reset global output flags between tests
    from ga_cli.utils.output import set_no_color, set_output_format, set_quiet

    set_quiet(False)
    set_no_color(False)
    set_output_format("table")

    # CliRunner's stdout is never a TTY, and piped output defaults to JSON.
    # Simulate an interactive terminal so commands render tables unless a test
    # passes -o or patches is_tty itself.
    # (Patched via the module object: ga_cli.utils re-exports an `output`
    # function that shadows the submodule in dotted-path lookups.)
    monkeypatch.setattr(importlib.import_module("ga_cli.utils.output"), "is_tty", lambda: True)

    yield tmp_path
