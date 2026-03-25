"""Tests for the agent guide command."""

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


class TestAgentGuide:
    def test_guide_prints_markdown(self):
        """ga agent guide prints the full guide."""
        result = runner.invoke(app, ["agent", "guide"])

        assert result.exit_code == 0
        assert "# AI Agent Guide to GA CLI" in result.output

    def test_guide_contains_key_sections(self):
        """Guide contains all major sections."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "## Quick Start" in result.output
        assert "## Core Concepts" in result.output
        assert "## Configuration Management" in result.output
        assert "## Reports" in result.output
        assert "## Quick Reference Card" in result.output

    def test_guide_contains_command_examples(self):
        """Guide contains actual CLI command examples."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "ga auth login" in result.output
        assert "ga accounts list" in result.output
        assert "ga reports run" in result.output
        assert "ga config set" in result.output

    def test_guide_documents_upgrade(self):
        """Guide documents the upgrade command."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "ga upgrade" in result.output

    def test_guide_documents_quiet_flag(self):
        """Guide documents the --quiet flag."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "--quiet" in result.output

    def test_guide_documents_no_color_flag(self):
        """Guide documents the --no-color flag."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "--no-color" in result.output

    def test_guide_documents_accounts_update(self):
        """Guide documents accounts update command."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "accounts update" in result.output

    def test_guide_documents_completions(self):
        """Guide documents completions command."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "completions" in result.output

    def test_guide_documents_env_vars(self):
        """Guide documents environment variables."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "GOOGLE_APPLICATION_CREDENTIALS" in result.output
        assert "NO_COLOR" in result.output

    def test_agent_no_args_shows_help(self):
        """ga agent with no subcommand shows help."""
        result = runner.invoke(app, ["agent"])

        assert "guide" in result.output
