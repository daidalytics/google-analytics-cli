"""Tests for version handling and --version flag."""

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


class TestVersion:
    def test_version_from_metadata(self):
        """__version__ reads from importlib.metadata."""
        from ga_cli import __version__

        assert __version__
        assert isinstance(__version__, str)
        assert "." in __version__

    def test_version_flag(self):
        """--version flag prints version and exits."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "ga-cli" in result.output

    def test_version_flag_short(self):
        """-v flag works as alias for --version."""
        result = runner.invoke(app, ["-v"])

        assert result.exit_code == 0
        assert "ga-cli" in result.output
