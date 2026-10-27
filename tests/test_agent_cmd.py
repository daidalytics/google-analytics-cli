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
        assert "## Agent Workflow" in result.output
        assert "## Agent Best Practices" in result.output
        assert "## Troubleshooting" in result.output
        assert "## Environment Variables" in result.output

    def test_guide_contains_command_examples(self):
        """Guide contains actual CLI command examples."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "ga auth login" in result.output
        assert "ga accounts list" in result.output
        assert "ga reports run" in result.output
        assert "ga config set" in result.output
        assert "ga mp-secrets" in result.output
        assert "ga google-ads-links" in result.output
        assert "ga firebase-links" in result.output

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

    def test_guide_shows_jq_patterns(self):
        """Guide includes jq patterns for extracting IDs."""
        result = runner.invoke(app, ["agent", "guide"])

        assert "jq" in result.output
        assert "grep -o" in result.output

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
        assert "Measurement Protocol Secrets" in result.output
        assert "Google Ads Links" in result.output
        assert "Firebase Links" in result.output

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


def _guide_section(heading: str) -> str:
    """The overview guide's text from `## heading` up to the next `## ` heading."""
    output = runner.invoke(app, ["agent", "guide"]).output
    start = output.index(f"## {heading}\n")
    end = output.find("\n## ", start + 1)
    return output[start:] if end == -1 else output[start:end]


class TestAgentGuideAllowlist:
    def test_guide_documents_allowlist(self):
        result = runner.invoke(app, ["agent", "guide"])

        assert "## Allowlist" in result.output
        assert "ga allowlist show" in result.output
        assert "allowlist_error" in result.output
        assert "GA_CLI_ALLOWED_ACCOUNTS" in result.output
        assert "GA_CLI_ALLOWED_PROPERTIES" in result.output

    def test_guide_lists_all_exit_codes(self):
        result = runner.invoke(app, ["agent", "guide"])

        assert "## Errors and exit codes" in result.output
        for code, category in [
            (1, "client_error"), (2, "auth_error"), (3, "api_error"),
            (4, "network_error"), (5, "allowlist_error"),
        ]:
            assert f"| {code} | `{category}` |" in result.output

    def test_allowlist_names_all_three_sources(self):
        section = _guide_section("Allowlist")

        assert "| `config` |" in section
        assert "| `profile NAME` |" in section
        assert "| `env` |" in section

    def test_allowlist_states_the_profile_rule(self):
        """The default profile's allowlist binds every profile; a profile's own only narrows."""
        section = _guide_section("Allowlist")
        config_row = next(line for line in section.splitlines() if line.startswith("| `config` |"))
        profile_row = next(
            line for line in section.splitlines() if line.startswith("| `profile NAME` |")
        )

        assert "default profile" in config_row
        assert "every profile" in config_row
        assert "ga --profile NAME config set" in profile_row
        assert "narrows" in profile_row
        assert "can never widen" in section
        assert "`--profile`" in section
        assert "`GA_CLI_PROFILE`" in section

    def test_allowlist_says_not_to_switch_profile_on_exit_5(self):
        section = _guide_section("Allowlist")

        assert "another `--profile`" in section
        assert "ga auth login" in section

    def test_error_shape_mentions_resource_and_hint(self):
        section = _guide_section("Errors and exit codes")

        assert '"resource"' in section
        assert '"hint"' in section

    def test_exit_codes_cover_profile_errors(self):
        rows = {
            line.split("|")[1].strip(): line
            for line in _guide_section("Errors and exit codes").splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()
        }

        assert "invalid profile name" in rows["1"]
        assert "unknown profile" in rows["2"]

    def test_global_flags_list_profile(self):
        assert "| `--profile NAME` |" in _guide_section("Global Flags")

    def test_env_vars_list_profile_next_to_allowlist_vars(self):
        names = [
            line.split("`")[1]
            for line in _guide_section("Environment Variables").splitlines()
            if line.startswith("| `")
        ]

        i = names.index("GA_CLI_PROFILE")
        assert names[i + 1:i + 3] == ["GA_CLI_ALLOWED_ACCOUNTS", "GA_CLI_ALLOWED_PROPERTIES"]

    def test_exit_codes_match_classify_error_docstring(self):
        from ga_cli.utils.errors import classify_error

        for code, category in [
            (1, "client_error"), (2, "auth_error"), (3, "api_error"),
            (4, "network_error"), (5, "allowlist_error"),
        ]:
            assert f"{code} — {category}" in classify_error.__doc__
