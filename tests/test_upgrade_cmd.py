"""Tests for the upgrade command (WS-1)."""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest
from typer.testing import CliRunner

from ga_cli.commands.upgrade_cmd import (
    _check_pypi_version,
    _is_ephemeral_uvx_env,
    _is_newer,
    maybe_check_for_updates,
)
from ga_cli.main import app

runner = CliRunner()


def _pypi_response(version: str) -> MagicMock:
    """Create a mock urllib response returning a given version."""
    body = json.dumps({"info": {"version": version}}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestCheckPypiVersion:
    def test_returns_latest_version(self):
        with patch("ga_cli.commands.upgrade_cmd.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _pypi_response("1.2.3")
            result = _check_pypi_version()
        assert result == "1.2.3"

    def test_returns_none_on_network_error(self):
        with patch("ga_cli.commands.upgrade_cmd.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")
            result = _check_pypi_version()
        assert result is None

    def test_returns_none_on_timeout(self):
        import socket

        with patch("ga_cli.commands.upgrade_cmd.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = socket.timeout("timed out")
            result = _check_pypi_version()
        assert result is None

    def test_returns_none_on_invalid_json(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("ga_cli.commands.upgrade_cmd.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock_resp
            result = _check_pypi_version()
        assert result is None


class TestIsNewer:
    def test_newer_version(self):
        assert _is_newer("2.0.0", "1.0.0") is True

    def test_same_version(self):
        assert _is_newer("1.0.0", "1.0.0") is False

    def test_older_version(self):
        assert _is_newer("0.9.0", "1.0.0") is False

    def test_prerelease(self):
        assert _is_newer("1.0.0", "1.0.0a1") is True


class TestUpgradeCheck:
    def test_check_up_to_date(self):
        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="0.1.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"):
            result = runner.invoke(app, ["upgrade", "--check"])
        assert result.exit_code == 0
        assert "latest version" in result.output

    def test_check_update_available(self):
        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="2.0.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"):
            result = runner.invoke(app, ["upgrade", "--check"])
        assert result.exit_code == 0
        assert "Update available" in result.output
        assert "0.1.0" in result.output
        assert "2.0.0" in result.output

    def test_check_network_failure(self):
        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value=None
        ):
            result = runner.invoke(app, ["upgrade", "--check"])
        assert result.exit_code == 1
        assert "Could not check" in result.output


class TestUpgradeRun:
    def test_upgrade_runs_pip(self):
        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="2.0.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"), patch(
            "ga_cli.commands.upgrade_cmd.subprocess.run"
        ) as mock_run, patch(
            "ga_cli.commands.upgrade_cmd._detect_installer",
            return_value=["pip", "install", "--upgrade", "google-analytics-cli"],
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 0
        assert "Successfully upgraded" in result.output
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert "pip" in cmd_args
        assert "--upgrade" in cmd_args

    def test_upgrade_skips_when_latest(self):
        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="0.1.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"), patch(
            "ga_cli.commands.upgrade_cmd.subprocess.run"
        ) as mock_run:
            result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 0
        assert "up to date" in result.output
        mock_run.assert_not_called()

    def test_upgrade_force_flag(self):
        with patch(
            "ga_cli.commands.upgrade_cmd.subprocess.run"
        ) as mock_run, patch(
            "ga_cli.commands.upgrade_cmd._detect_installer",
            return_value=["pip", "install", "--upgrade", "google-analytics-cli"],
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["upgrade", "--force"])
        assert result.exit_code == 0
        cmd_args = mock_run.call_args[0][0]
        assert "--force-reinstall" in cmd_args

    def test_upgrade_pip_failure(self):
        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="2.0.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"), patch(
            "ga_cli.commands.upgrade_cmd.subprocess.run"
        ) as mock_run, patch(
            "ga_cli.commands.upgrade_cmd._detect_installer",
            return_value=["pip", "install", "--upgrade", "google-analytics-cli"],
        ):
            mock_run.return_value = MagicMock(returncode=1, stderr="install error")
            result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 1
        assert "Upgrade failed" in result.output

    def test_upgrade_detects_pipx(self):
        def _which(name):
            return "/usr/local/bin/pipx" if name == "pipx" else None

        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="2.0.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"), patch(
            "ga_cli.commands.upgrade_cmd.subprocess.run"
        ) as mock_run, patch(
            "ga_cli.commands.upgrade_cmd.shutil.which", side_effect=_which
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 0
        cmd_args = mock_run.call_args[0][0]
        assert "pipx" in cmd_args

    def test_upgrade_detects_uv(self):
        def _which(name):
            return "/usr/local/bin/uv" if name == "uv" else None

        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="2.0.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"), patch(
            "ga_cli.commands.upgrade_cmd.subprocess.run"
        ) as mock_run, patch(
            "ga_cli.commands.upgrade_cmd.shutil.which", side_effect=_which
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 0
        cmd_args = mock_run.call_args[0][0]
        assert "uv" in cmd_args

    def test_upgrade_uv_preferred_over_pipx(self):
        """When both uv and pipx are available, uv should be preferred."""
        def _which(name):
            if name == "uv":
                return "/usr/local/bin/uv"
            if name == "pipx":
                return "/usr/local/bin/pipx"
            return None

        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="2.0.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"), patch(
            "ga_cli.commands.upgrade_cmd.subprocess.run"
        ) as mock_run, patch(
            "ga_cli.commands.upgrade_cmd.shutil.which", side_effect=_which
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 0
        cmd_args = mock_run.call_args[0][0]
        assert "uv" in cmd_args
        assert "pipx" not in cmd_args


class TestDailyUpdateCheck:
    @pytest.fixture(autouse=True)
    def _regular_install(self, tmp_path, monkeypatch):
        """Pin sys.prefix outside uv's cache so the host environment never matters."""
        monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))

    def test_skips_when_checked_recently(self, isolated_config_dir):
        check_path = isolated_config_dir / "update-check.json"
        check_path.write_text(json.dumps({"last_check": time.time()}))

        with patch("ga_cli.commands.upgrade_cmd.urllib.request.urlopen") as mock_urlopen:
            maybe_check_for_updates()
        mock_urlopen.assert_not_called()

    def test_runs_when_stale(self, isolated_config_dir):
        check_path = isolated_config_dir / "update-check.json"
        check_path.write_text(json.dumps({"last_check": time.time() - 90000}))

        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="9.9.9"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"), patch(
            "ga_cli.commands.upgrade_cmd.warn"
        ) as mock_warn:
            maybe_check_for_updates()

        # Timestamp should be updated
        data = json.loads(check_path.read_text())
        assert data["last_check"] > time.time() - 10
        # Outside uv's cache the notice still points at 'ga upgrade'
        mock_warn.assert_called_once()
        assert "v9.9.9" in mock_warn.call_args[0][0]
        assert "Run 'ga upgrade' to update." in mock_warn.call_args[0][0]

    def test_runs_when_no_timestamp_file(self, isolated_config_dir):
        check_path = isolated_config_dir / "update-check.json"
        assert not check_path.exists()

        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="0.1.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"):
            maybe_check_for_updates()

        assert check_path.exists()
        data = json.loads(check_path.read_text())
        assert "last_check" in data

    def test_does_not_block_on_error(self, isolated_config_dir):
        """Network errors in the daily check must not raise."""
        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", side_effect=Exception("boom")
        ):
            # Should not raise
            maybe_check_for_updates()

    def test_writes_timestamp_after_check(self, isolated_config_dir):
        check_path = isolated_config_dir / "update-check.json"

        with patch(
            "ga_cli.commands.upgrade_cmd._check_pypi_version", return_value="0.1.0"
        ), patch("ga_cli.commands.upgrade_cmd.__version__", "0.1.0"):
            maybe_check_for_updates()

        assert check_path.exists()
        data = json.loads(check_path.read_text())
        assert abs(data["last_check"] - time.time()) < 5


class TestUpdateCheckUnderUvx:
    """`uvx google-analytics-cli` runs from uv's cache; 'ga upgrade' can't update it."""

    @pytest.fixture(autouse=True)
    def _clean_uv_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("UV_CACHE_DIR", raising=False)
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        self.home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: self.home))

    @staticmethod
    def _run_stale_check():
        """Run the daily check with a newer version on PyPI; return (urlopen, warn) mocks."""
        with patch(
            "ga_cli.commands.upgrade_cmd.urllib.request.urlopen",
            return_value=_pypi_response("9.9.9"),
        ) as mock_urlopen, patch(
            "ga_cli.commands.upgrade_cmd.__version__", "0.1.0"
        ), patch("ga_cli.commands.upgrade_cmd.warn") as mock_warn:
            maybe_check_for_updates()
        return mock_urlopen, mock_warn

    def test_skipped_when_prefix_under_uv_cache_dir_env(
        self, tmp_path, monkeypatch, isolated_config_dir
    ):
        cache_dir = tmp_path / "custom-uv-cache"
        monkeypatch.setenv("UV_CACHE_DIR", str(cache_dir))
        monkeypatch.setattr(sys, "prefix", str(cache_dir / "archive-v0" / "pi-abc123"))

        mock_urlopen, mock_warn = self._run_stale_check()

        mock_urlopen.assert_not_called()
        mock_warn.assert_not_called()
        assert not (isolated_config_dir / "update-check.json").exists()

    def test_skipped_when_prefix_under_default_cache(self, monkeypatch, isolated_config_dir):
        prefix = self.home / ".cache" / "uv" / "archive-v0" / "pi-abc123"
        monkeypatch.setattr(sys, "prefix", str(prefix))

        mock_urlopen, mock_warn = self._run_stale_check()

        mock_urlopen.assert_not_called()
        mock_warn.assert_not_called()
        assert not (isolated_config_dir / "update-check.json").exists()

    def test_uv_cache_dir_env_takes_precedence_over_default(
        self, tmp_path, monkeypatch, isolated_config_dir
    ):
        """With UV_CACHE_DIR elsewhere, the default ~/.cache/uv is not uv's cache."""
        monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "custom-uv-cache"))
        prefix = self.home / ".cache" / "uv" / "archive-v0" / "pi-abc123"
        monkeypatch.setattr(sys, "prefix", str(prefix))

        assert _is_ephemeral_uvx_env() is False
        mock_urlopen, mock_warn = self._run_stale_check()

        mock_urlopen.assert_called_once()
        mock_warn.assert_called_once()
        assert "Run 'ga upgrade' to update." in mock_warn.call_args[0][0]
        assert (isolated_config_dir / "update-check.json").exists()


class TestIsEphemeralUvxEnv:
    @pytest.fixture(autouse=True)
    def _clean_uv_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("UV_CACHE_DIR", raising=False)
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        self.home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: self.home))

    def test_prefix_under_uv_cache_dir_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "c"))
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "c" / "archive-v0" / "x"))
        assert _is_ephemeral_uvx_env() is True

    def test_prefix_under_xdg_cache_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "xdg" / "uv" / "archive-v0" / "x"))
        assert _is_ephemeral_uvx_env() is True

    def test_xdg_cache_home_replaces_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        prefix = self.home / ".cache" / "uv" / "archive-v0" / "x"
        monkeypatch.setattr(sys, "prefix", str(prefix))
        assert _is_ephemeral_uvx_env() is False

    def test_prefix_under_default_cache(self, monkeypatch):
        prefix = self.home / ".cache" / "uv" / "archive-v0" / "x"
        monkeypatch.setattr(sys, "prefix", str(prefix))
        assert _is_ephemeral_uvx_env() is True

    def test_windows_default_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
        prefix = tmp_path / "AppData" / "Local" / "uv" / "cache" / "archive-v0" / "x"
        monkeypatch.setattr(sys, "prefix", str(prefix))
        assert _is_ephemeral_uvx_env() is True

    def test_windows_without_localappdata(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(sys, "prefix", str(self.home / ".cache" / "uv" / "x"))
        assert _is_ephemeral_uvx_env() is False

    def test_regular_venv(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "project" / ".venv"))
        assert _is_ephemeral_uvx_env() is False

    def test_sibling_dir_with_shared_name_prefix(self, tmp_path, monkeypatch):
        """`~/.cache/uv-other` is not inside `~/.cache/uv`."""
        monkeypatch.setattr(sys, "prefix", str(self.home / ".cache" / "uv-other" / "x"))
        assert _is_ephemeral_uvx_env() is False

    def test_returns_false_when_home_unresolvable(self, monkeypatch):
        def _no_home(cls):
            raise RuntimeError("Could not determine home directory.")

        monkeypatch.setattr(Path, "home", classmethod(_no_home))
        assert _is_ephemeral_uvx_env() is False
