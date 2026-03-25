"""Shared fixtures for auth tests."""


import pytest


@pytest.fixture(autouse=True)
def isolated_config_dir(tmp_path, monkeypatch):
    """Point GA_CLI_CONFIG_DIR to a temp dir so tests never touch real config."""
    monkeypatch.setenv("GA_CLI_CONFIG_DIR", str(tmp_path))

    # Also clear the in-memory config cache between tests
    from ga_cli.config import store

    store._cached_config = None

    # Reset global output flags between tests
    from ga_cli.utils.output import set_no_color, set_quiet

    set_quiet(False)
    set_no_color(False)

    yield tmp_path
