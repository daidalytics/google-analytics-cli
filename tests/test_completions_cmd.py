"""Tests for the completions command (WS-2)."""

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


class TestCompletionsBash:
    def test_bash_outputs_completion_script(self):
        result = runner.invoke(app, ["completions", "bash"])
        assert result.exit_code == 0
        assert "_ga_completion" in result.output

    def test_bash_output_contains_complete_var(self):
        result = runner.invoke(app, ["completions", "bash"])
        assert "_GA_COMPLETE" in result.output

    def test_bash_output_is_valid_shell(self):
        result = runner.invoke(app, ["completions", "bash"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output
        assert "Error" not in result.output


class TestCompletionsZsh:
    def test_zsh_outputs_completion_script(self):
        result = runner.invoke(app, ["completions", "zsh"])
        assert result.exit_code == 0
        assert "#compdef ga" in result.output

    def test_zsh_output_contains_completion_func(self):
        result = runner.invoke(app, ["completions", "zsh"])
        assert "_ga_completion" in result.output

    def test_zsh_output_is_valid_shell(self):
        result = runner.invoke(app, ["completions", "zsh"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output
        assert "Error" not in result.output


class TestCompletionsFish:
    def test_fish_outputs_completion_script(self):
        result = runner.invoke(app, ["completions", "fish"])
        assert result.exit_code == 0
        assert "_ga_completion" in result.output

    def test_fish_output_contains_complete_command(self):
        result = runner.invoke(app, ["completions", "fish"])
        assert "_GA_COMPLETE" in result.output

    def test_fish_output_is_valid_shell(self):
        result = runner.invoke(app, ["completions", "fish"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output
        assert "Error" not in result.output


class TestCompletionsNoArgs:
    def test_no_args_shows_help(self):
        result = runner.invoke(app, ["completions"])
        # no_args_is_help exits with code 2 (standard Click/Typer behavior)
        assert result.exit_code == 2
        assert "bash" in result.output
        assert "zsh" in result.output
        assert "fish" in result.output
