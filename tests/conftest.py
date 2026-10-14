"""Shared fixtures for auth tests."""

import importlib

import pytest


@pytest.fixture(autouse=True)
def isolated_config_dir(tmp_path, monkeypatch):
    """Point GA_CLI_CONFIG_DIR to a temp dir so tests never touch real config."""
    monkeypatch.setenv("GA_CLI_CONFIG_DIR", str(tmp_path))

    # A developer may have a profile exported; every test starts on default.
    monkeypatch.delenv("GA_CLI_PROFILE", raising=False)
    from ga_cli.config.constants import set_active_profile

    set_active_profile(None)

    # Also clear the in-memory config cache between tests
    from ga_cli.config import store

    store._cached_config = None

    # Drop API clients cached by a previous test (possibly under another profile)
    from ga_cli.api.client import clear_client_cache

    clear_client_cache()

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
