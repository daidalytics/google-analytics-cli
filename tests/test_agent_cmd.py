"""Tests for the agent guide command."""

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


class TestAgentGuide:
    def test_guide_prints_markdown(self):
        """ga agent guide prints the overview guide."""
        result = runner.invoke(app, ["agent", "guide"])

        assert result.exit_code == 0
        assert "# GA CLI" in result.output

    def test_guide_contains_key_sections(self):
        """Guide contains all major sections."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "## Setup" in result.output
        assert "## Command Reference" in result.output
        assert "## Global Flags" in result.output
        assert "## Troubleshooting" in result.output
        assert "## Environment Variables" in result.output

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

    def test_guide_lists_available_sections(self):
        """Guide tells agents about available deep-dive sections."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "reports" in result.output
        assert "admin" in result.output
        assert "examples" in result.output

    def test_agent_no_args_shows_help(self):
        """ga agent with no subcommand shows help."""
        result = runner.invoke(app, ["agent"])

        assert "guide" in result.output


class TestAgentGuideSection:
    def test_section_reports(self):
        """--section reports shows metrics and dimensions."""
        result = runner.invoke(app, ["agent", "guide", "--section", "reports"])

        assert result.exit_code == 0
        assert "Common Metrics" in result.output
        assert "Common Dimensions" in result.output
        assert "Pivot Reports" in result.output

    def test_section_admin(self):
        """--section admin shows custom dimensions, metrics, key events, streams."""
        result = runner.invoke(app, ["agent", "guide", "--section", "admin"])

        assert result.exit_code == 0
        assert "Custom Dimensions" in result.output
        assert "Custom Metrics" in result.output
        assert "Key Events" in result.output
        assert "Data Streams" in result.output

    def test_section_examples(self):
        """--section examples shows complete workflow examples."""
        result = runner.invoke(app, ["agent", "guide", "--section", "examples"])

        assert result.exit_code == 0
        assert "Audit a GA4 Account" in result.output
        assert "Traffic Report" in result.output

    def test_section_case_insensitive(self):
        """Section names are case-insensitive."""
        result = runner.invoke(app, ["agent", "guide", "--section", "REPORTS"])

        assert result.exit_code == 0
        assert "Common Metrics" in result.output

    def test_invalid_section_exits_cleanly(self):
        """Invalid section prints valid options and exits with code 0."""
        result = runner.invoke(app, ["agent", "guide", "--section", "bogus"])

        assert result.exit_code == 0
        assert "Unknown section" in result.output
        assert "reports" in result.output
        assert "admin" in result.output
        assert "examples" in result.output

    def test_section_short_flag(self):
        """-s works as shorthand for --section."""
        result = runner.invoke(app, ["agent", "guide", "-s", "admin"])

        assert result.exit_code == 0
        assert "Custom Dimensions" in result.output
