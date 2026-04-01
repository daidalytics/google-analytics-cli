"""Tests for --quiet and --no-color global flags (WS-3)."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app
from ga_cli.utils.output import set_no_color, set_quiet

runner = CliRunner()

SAMPLE_ACCOUNTS = [
    {
        "name": "accounts/123456",
        "displayName": "My Account",
        "createTime": "2023-01-01T00:00:00Z",
    },
]


def _mock_admin_client(accounts=None):
    """Create a mock Admin API client."""
    mock_client = MagicMock()
    mock_client.accounts.return_value.list.return_value.execute.return_value = {
        "accounts": accounts or [],
    }
    return mock_client


class TestQuietFlag:
    def setup_method(self):
        """Reset quiet state between tests."""
        set_quiet(False)

    def test_quiet_suppresses_info(self):
        """Info messages should not appear in stderr when --quiet is passed."""
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["--quiet", "accounts", "list"])

        assert result.exit_code == 0
        assert "Info:" not in result.output

    def test_quiet_suppresses_success(self):
        """Success messages should not appear when --quiet is passed."""
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["--quiet", "accounts", "list"])

        assert result.exit_code == 0
        assert "OK" not in result.output

    def test_quiet_suppresses_warn(self):
        """Warning messages should not appear when --quiet is passed."""
        from ga_cli.utils.output import err_console, warn

        set_quiet(True)

        with patch.object(err_console, "print") as mock_print:
            warn("test warning")
            mock_print.assert_not_called()

    def test_quiet_does_not_suppress_errors(self):
        """Error messages should still appear even in quiet mode."""
        mock_client = MagicMock()
        mock_client.accounts.return_value.list.return_value.execute.side_effect = (
            Exception("API failure")
        )

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["--quiet", "accounts", "list"])

        assert result.exit_code == 3
        assert "API failure" in result.output

    def test_quiet_does_not_suppress_data_output(self):
        """Data output (JSON) should still be printed in quiet mode."""
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["--quiet", "accounts", "list", "-o", "json"])

        assert result.exit_code == 0
        assert "accounts/123456" in result.output
        assert "My Account" in result.output

    def test_quiet_short_flag(self):
        """The -q shorthand should work the same as --quiet."""
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["-q", "accounts", "list", "-o", "json"])

        assert result.exit_code == 0
        assert "My Account" in result.output


class TestNoColorFlag:
    def setup_method(self):
        """Reset no-color state between tests."""
        set_no_color(False)

    def test_no_color_removes_ansi_codes(self):
        """Output should not contain ANSI escape sequences with --no-color."""
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["--no-color", "accounts", "list"])

        assert result.exit_code == 0
        assert "\x1b[" not in result.output

    def test_no_color_env_var(self, monkeypatch):
        """The NO_COLOR env var should disable colors (Rich handles this natively)."""
        monkeypatch.setenv("NO_COLOR", "1")
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(app, ["accounts", "list"])

        assert result.exit_code == 0
        # Rich respects NO_COLOR natively
        assert "\x1b[" not in result.output


class TestQuietAndNoColorCombined:
    def setup_method(self):
        set_quiet(False)
        set_no_color(False)

    def test_both_flags_together(self):
        """Both flags should work simultaneously."""
        mock_client = _mock_admin_client(accounts=SAMPLE_ACCOUNTS)

        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            result = runner.invoke(
                app, ["--quiet", "--no-color", "accounts", "list", "-o", "json"]
            )

        assert result.exit_code == 0
        # Data still present
        assert "My Account" in result.output
        # No info messages
        assert "Info:" not in result.output
        # No ANSI codes
        assert "\x1b[" not in result.output
