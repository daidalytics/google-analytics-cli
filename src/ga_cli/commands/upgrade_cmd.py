"""Upgrade command: check for updates and self-update ga-cli."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from typing import Optional

import typer

from .. import __version__
from ..config.constants import get_update_check_path
from ..utils import error, info, success, warn

upgrade_app = typer.Typer(
    name="upgrade", help="Check for and install updates", invoke_without_command=True
)

PYPI_URL = "https://pypi.org/pypi/google-analytics-cli/json"
PYPI_TIMEOUT = 5
UPDATE_CHECK_INTERVAL = 86400  # 24 hours in seconds


def _check_pypi_version() -> Optional[str]:
    """Fetch the latest ga-cli version from PyPI.

    Returns the version string, or None on any error.
    """
    try:
        req = urllib.request.Request(PYPI_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=PYPI_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return data["info"]["version"]
    except Exception:
        return None


def _is_newer(latest: str, current: str) -> bool:
    """Return True if latest is strictly newer than current."""
    from packaging.version import parse

    return parse(latest) > parse(current)


def _detect_installer() -> list[str]:
    """Detect the best install command to upgrade ga-cli.

    Checks for uv first, then pipx, then falls back to pip.
    """
    if shutil.which("uv"):
        return ["uv", "pip", "install", "--upgrade", "google-analytics-cli"]
    if shutil.which("pipx"):
        return ["pipx", "upgrade", "google-analytics-cli"]
    return [sys.executable, "-m", "pip", "install", "--upgrade", "google-analytics-cli"]


@upgrade_app.callback(invoke_without_command=True)
def upgrade_cmd(
    check: bool = typer.Option(False, "--check", help="Check for updates without installing"),
    force: bool = typer.Option(False, "--force", help="Force reinstall current version"),
):
    """Check for and install updates."""
    current = __version__

    if check:
        latest = _check_pypi_version()
        if latest is None:
            error("Could not check for updates. Please check your network connection.")
            raise typer.Exit(1)
        if _is_newer(latest, current):
            info(f"Update available: {current} → {latest}. Run 'ga upgrade' to install.")
        else:
            success(f"ga-cli {current} is the latest version.")
        return

    if force:
        info(f"Force-reinstalling ga-cli {current}...")
        cmd = _detect_installer()
        if cmd[0] == "pipx":
            cmd = ["pipx", "install", "--force", "google-analytics-cli"]
        elif cmd[0] == "uv":
            cmd.append("--reinstall")
        else:
            cmd.append("--force-reinstall")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            success(f"Reinstalled ga-cli {current}.")
        else:
            error(f"Upgrade failed:\n{result.stderr.strip()}")
            raise typer.Exit(1)
        return

    # Default: check and upgrade
    latest = _check_pypi_version()
    if latest is None:
        error("Could not check for updates. Please check your network connection.")
        raise typer.Exit(1)

    if not _is_newer(latest, current):
        success(f"ga-cli {current} is already up to date.")
        return

    info(f"Upgrading ga-cli {current} → {latest}...")
    cmd = _detect_installer()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        success(f"Successfully upgraded to ga-cli {latest}.")
    else:
        error(f"Upgrade failed:\n{result.stderr.strip()}")
        raise typer.Exit(1)


def maybe_check_for_updates() -> None:
    """Run a non-blocking daily update check.

    Called from main.py after command dispatch. Prints a dim notice
    to stderr if a newer version is available. Never raises.
    """
    try:
        check_path = get_update_check_path()

        # Read last check timestamp
        last_check = 0.0
        if check_path.exists():
            try:
                data = json.loads(check_path.read_text())
                last_check = data.get("last_check", 0.0)
            except (json.JSONDecodeError, OSError):
                pass

        now = time.time()
        if now - last_check < UPDATE_CHECK_INTERVAL:
            return

        latest = _check_pypi_version()

        # Write new timestamp regardless of result
        check_path.parent.mkdir(parents=True, exist_ok=True)
        check_path.write_text(json.dumps({"last_check": now}))

        if latest and _is_newer(latest, __version__):
            warn(
                f"A new version of ga-cli is available (v{latest}). "
                "Run 'ga upgrade' to update."
            )
    except Exception:
        pass
