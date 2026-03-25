"""Tests for config commands (setup, get, set, unset, path, reset)."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, get_config_value, load_config, save_config
from ga_cli.main import app

runner = CliRunner()


class TestSetupCommand:
    def test_setup_interactive(self):
        mock_text = MagicMock()
        mock_text.return_value.ask.side_effect = ["12345", "67890"]

        mock_select = MagicMock()
        mock_select.return_value.ask.return_value = "json"

        with (
            patch("questionary.text", mock_text),
            patch("questionary.select", mock_select),
        ):
            result = runner.invoke(app, ["config", "setup"])

        assert result.exit_code == 0
        assert "Configuration saved" in result.output

        config = load_config()
        assert config.default_account_id == "12345"
        assert config.default_property_id == "67890"
        assert config.output_format == "json"


class TestGetCommand:
    def test_get_all(self):
        save_config(UserConfig(
            default_account_id="111",
            default_property_id="222",
            output_format="compact",
        ))

        result = runner.invoke(app, ["config", "get"])

        assert result.exit_code == 0
        assert "111" in result.output
        assert "222" in result.output
        assert "compact" in result.output

    def test_get_specific_key(self):
        save_config(UserConfig(default_account_id="12345"))

        result = runner.invoke(app, ["config", "get", "default_account_id"])

        assert result.exit_code == 0
        assert "12345" in result.output

    def test_get_unknown_key(self):
        result = runner.invoke(app, ["config", "get", "nonexistent_key"])

        assert result.exit_code == 1
        assert "Unknown config key" in result.output

    def test_get_unset_key(self):
        result = runner.invoke(app, ["config", "get", "default_account_id"])

        assert result.exit_code == 1
        assert "not set" in result.output


class TestSetCommand:
    def test_set_valid_key(self):
        result = runner.invoke(app, ["config", "set", "default_account_id", "12345"])

        assert result.exit_code == 0
        assert "Set default_account_id = 12345" in result.output
        assert get_config_value("default_account_id") == "12345"

    def test_set_unknown_key(self):
        result = runner.invoke(app, ["config", "set", "bad_key", "value"])

        assert result.exit_code == 1
        assert "Unknown config key" in result.output


class TestUnsetCommand:
    def test_unset_key(self):
        save_config(UserConfig(default_account_id="12345"))

        result = runner.invoke(app, ["config", "unset", "default_account_id"])

        assert result.exit_code == 0
        assert "Unset default_account_id" in result.output
        assert get_config_value("default_account_id") is None

    def test_unset_unknown_key(self):
        result = runner.invoke(app, ["config", "unset", "bad_key"])

        assert result.exit_code == 1
        assert "Unknown config key" in result.output


class TestPathCommand:
    def test_path(self):
        result = runner.invoke(app, ["config", "path"])

        assert result.exit_code == 0
        assert "config.json" in result.output


class TestResetCommand:
    def test_reset_confirmed(self):
        save_config(UserConfig(default_account_id="12345", output_format="json"))

        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = True

        with patch("questionary.confirm", mock_confirm):
            result = runner.invoke(app, ["config", "reset"])

        assert result.exit_code == 0
        assert "Configuration reset" in result.output

        config = load_config()
        assert config.default_account_id is None
        assert config.output_format == "table"

    def test_reset_cancelled(self):
        save_config(UserConfig(default_account_id="12345"))

        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = False

        with patch("questionary.confirm", mock_confirm):
            result = runner.invoke(app, ["config", "reset"])

        assert result.exit_code == 0
        assert "cancelled" in result.output
        assert get_config_value("default_account_id") == "12345"
