"""Tests for config commands (setup, get, set, unset, path, reset)."""

from pathlib import Path
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

    def test_setup_auto_leaves_output_format_unset(self, tmp_path):
        """Writing "table" as a default is what made a configured table ambiguous."""
        mock_text = MagicMock()
        mock_text.return_value.ask.side_effect = ["", ""]
        mock_select = MagicMock()
        mock_select.return_value.ask.return_value = "auto"

        with (
            patch("questionary.text", mock_text),
            patch("questionary.select", mock_select),
        ):
            result = runner.invoke(app, ["config", "setup"])

        assert result.exit_code == 0
        assert mock_select.call_args.kwargs["default"] == "auto"
        assert load_config().output_format is None
        assert "output_format" not in (tmp_path / "config.json").read_text()


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

    def test_default_profile_path_is_unchanged(self, isolated_config_dir):
        """The default profile is the config root: same output as before profiles."""
        result = runner.invoke(app, ["config", "path"])

        assert result.exit_code == 0
        assert result.stdout == f"{isolated_config_dir / 'config.json'}\n"

    def test_named_profile_path(self, isolated_config_dir):
        result = runner.invoke(app, ["--profile", "client-a", "config", "path"])

        assert result.exit_code == 0
        expected = isolated_config_dir / "profiles" / "client-a" / "config.json"
        assert result.stdout == f"{expected}\n"

    def test_profile_from_env_var(self, isolated_config_dir, monkeypatch):
        monkeypatch.setenv("GA_CLI_PROFILE", "client-b")

        result = runner.invoke(app, ["config", "path"])

        assert result.exit_code == 0
        expected = isolated_config_dir / "profiles" / "client-b" / "config.json"
        assert result.stdout == f"{expected}\n"

    def test_path_does_not_create_the_profile(self, isolated_config_dir):
        """It shows where `config set` would write; only a write creates the profile."""
        result = runner.invoke(app, ["--profile", "client-a", "config", "path"])

        assert result.exit_code == 0
        assert not (isolated_config_dir / "profiles" / "client-a").exists()

    def test_path_matches_where_config_set_writes(self, isolated_config_dir):
        printed = runner.invoke(app, ["--profile", "client-a", "config", "path"]).stdout.strip()

        result = runner.invoke(
            app, ["--profile", "client-a", "config", "set", "default_property_id", "123"]
        )

        assert result.exit_code == 0
        assert Path(printed).is_file()
        assert '"default_property_id": "123"' in Path(printed).read_text()
        assert not (isolated_config_dir / "config.json").exists()


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
        assert config.output_format is None

    def test_reset_cancelled(self):
        save_config(UserConfig(default_account_id="12345"))

        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = False

        with patch("questionary.confirm", mock_confirm):
            result = runner.invoke(app, ["config", "reset"])

        assert result.exit_code == 0
        assert "cancelled" in result.output
        assert get_config_value("default_account_id") == "12345"


class TestUnknownNamedProfile:
    """get/unset/reset on a typo'd profile error instead of reading as empty
    or creating it; only `set` and `setup` create a profile."""

    def _assert_profile_not_found(self, result, isolated_config_dir):
        assert result.exit_code == 2
        assert "Profile 'clinet-a' does not exist" in result.output
        assert "Known profiles: default, client-a" in result.output
        assert not (isolated_config_dir / "profiles" / "clinet-a").exists()

    def _create_client_a(self):
        runner.invoke(app, ["--profile", "client-a", "config", "set", "default_property_id", "1"])

    def test_get_all(self, isolated_config_dir):
        self._create_client_a()

        result = runner.invoke(app, ["--profile", "clinet-a", "config", "get"])

        self._assert_profile_not_found(result, isolated_config_dir)

    def test_get_key(self, isolated_config_dir):
        self._create_client_a()

        result = runner.invoke(
            app, ["--profile", "clinet-a", "config", "get", "default_property_id"]
        )

        self._assert_profile_not_found(result, isolated_config_dir)

    def test_get_via_env_var(self, isolated_config_dir, monkeypatch):
        self._create_client_a()
        monkeypatch.setenv("GA_CLI_PROFILE", "clinet-a")

        result = runner.invoke(app, ["config", "get"])

        self._assert_profile_not_found(result, isolated_config_dir)

    def test_unset_does_not_create_the_profile(self, isolated_config_dir):
        self._create_client_a()

        result = runner.invoke(
            app, ["--profile", "clinet-a", "config", "unset", "default_property_id"]
        )

        self._assert_profile_not_found(result, isolated_config_dir)

    def test_reset_does_not_prompt_or_create_the_profile(self, isolated_config_dir):
        self._create_client_a()
        mock_confirm = MagicMock()

        with patch("questionary.confirm", mock_confirm):
            result = runner.invoke(app, ["--profile", "clinet-a", "config", "reset"])

        self._assert_profile_not_found(result, isolated_config_dir)
        mock_confirm.assert_not_called()

    def test_existing_named_profile_get_works(self):
        self._create_client_a()

        result = runner.invoke(
            app, ["--profile", "client-a", "config", "get", "default_property_id"]
        )

        assert result.exit_code == 0
        assert result.stdout.strip() == "1"

    def test_set_still_creates_the_profile(self, isolated_config_dir):
        result = runner.invoke(
            app, ["--profile", "client-b", "config", "set", "default_property_id", "2"]
        )

        assert result.exit_code == 0
        assert (isolated_config_dir / "profiles" / "client-b" / "config.json").is_file()
