"""Tests for config commands (setup, get, set, unset, path, reset)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ga_cli.config.store import (
    ConfigFileError,
    UserConfig,
    config_error,
    get_config_value,
    load_config,
    save_config,
)
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


# ---------------------------------------------------------------------------
# Allowlist keys: interactive only
# ---------------------------------------------------------------------------
class TestAllowlistKeys:
    def _tty(self, monkeypatch, tty, confirm=True):
        import ga_cli.commands.config_cmd as config_cmd

        monkeypatch.setattr(config_cmd, "_stdin_is_tty", lambda: tty)
        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = confirm
        monkeypatch.setattr("questionary.confirm", mock_confirm)
        return mock_confirm

    def _file(self, tmp_path):
        path = tmp_path / "config.json"
        return path.read_text() if path.exists() else None

    def test_set_without_tty_refused_file_unchanged(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_account_ids=["1"]))
        before = self._file(tmp_path)
        confirm = self._tty(monkeypatch, tty=False)
        result = runner.invoke(app, ["config", "set", "allowed_account_ids", "1,2"], input="y\n")
        assert result.exit_code == 1
        assert "can only be changed interactively" in result.output
        assert self._file(tmp_path) == before
        confirm.assert_not_called()

    def test_set_with_tty_and_confirm_saves_normalised(self, monkeypatch, tmp_path):
        self._tty(monkeypatch, tty=True)
        result = runner.invoke(
            app, ["config", "set", "allowed_account_ids", "456, accounts/123,"]
        )
        assert result.exit_code == 0, result.output
        assert "(not set) → 123, 456" in result.output
        assert json.loads(self._file(tmp_path))["allowed_account_ids"] == ["123", "456"]

    def test_set_declined_leaves_file_unchanged(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_property_ids=["1"]))
        before = self._file(tmp_path)
        self._tty(monkeypatch, tty=True, confirm=False)
        result = runner.invoke(app, ["config", "set", "allowed_property_ids", "1,2"])
        assert result.exit_code == 0
        assert self._file(tmp_path) == before

    def test_set_invalid_id_exits_1(self, monkeypatch, tmp_path):
        confirm = self._tty(monkeypatch, tty=True)
        result = runner.invoke(app, ["config", "set", "allowed_property_ids", "12,abc"])
        assert result.exit_code == 1
        assert "'abc'" in result.output
        assert self._file(tmp_path) is None
        confirm.assert_not_called()

    def test_set_empty_value_stores_empty_list(self, monkeypatch, tmp_path):
        self._tty(monkeypatch, tty=True)
        result = runner.invoke(app, ["config", "set", "allowed_account_ids", ""])
        assert result.exit_code == 0
        assert "denies everything" in result.output
        assert json.loads(self._file(tmp_path))["allowed_account_ids"] == []

    def test_unset_without_tty_refused(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_account_ids=["1"]))
        before = self._file(tmp_path)
        self._tty(monkeypatch, tty=False)
        result = runner.invoke(app, ["config", "unset", "allowed_account_ids"])
        assert result.exit_code == 1
        assert self._file(tmp_path) == before

    def test_unset_with_tty_and_confirm(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_account_ids=["1"], default_property_id="9"))
        self._tty(monkeypatch, tty=True)
        result = runner.invoke(app, ["config", "unset", "allowed_account_ids"])
        assert result.exit_code == 0
        assert json.loads(self._file(tmp_path)) == {"default_property_id": "9"}

    def test_reset_without_tty_refused_when_allowlist_set(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_property_ids=["1"]))
        before = self._file(tmp_path)
        self._tty(monkeypatch, tty=False)
        result = runner.invoke(app, ["config", "reset"])
        assert result.exit_code == 1
        assert self._file(tmp_path) == before

    def test_reset_with_tty_clears_allowlist(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_property_ids=["1"]))
        confirm = self._tty(monkeypatch, tty=True)
        result = runner.invoke(app, ["config", "reset"])
        assert result.exit_code == 0
        assert confirm.call_count == 2
        assert json.loads(self._file(tmp_path)) == {}

    def test_reset_without_allowlist_needs_no_tty(self, monkeypatch):
        save_config(UserConfig(default_property_id="1"))
        confirm = self._tty(monkeypatch, tty=False)
        result = runner.invoke(app, ["config", "reset"])
        assert result.exit_code == 0
        assert confirm.call_count == 1

    def test_setup_keeps_allowlist(self):
        save_config(UserConfig(allowed_account_ids=["1"], allowed_property_ids=["2"]))
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
        config = load_config()
        assert config.allowed_account_ids == ["1"]
        assert config.allowed_property_ids == ["2"]

    def test_get_all_shows_null_when_unset(self):
        result = runner.invoke(app, ["config", "get"])
        data = json.loads(result.output)
        assert data["allowed_account_ids"] is None
        assert data["allowed_property_ids"] is None

    def test_get_key_prints_comma_separated(self):
        save_config(UserConfig(allowed_account_ids=["1", "2"]))
        result = runner.invoke(app, ["config", "get", "allowed_account_ids"])
        assert result.exit_code == 0
        assert result.output.strip() == "1,2"

    def test_get_key_with_hand_edited_numbers(self, tmp_path):
        (tmp_path / "config.json").write_text('{"allowed_account_ids": [123, 456]}')
        result = runner.invoke(app, ["config", "get", "allowed_account_ids"])
        assert result.exit_code == 0
        assert result.output.strip() == "123,456"

    def test_set_shows_hand_edited_old_value(self, monkeypatch, tmp_path):
        (tmp_path / "config.json").write_text('{"allowed_account_ids": [123]}')
        self._tty(monkeypatch, tty=True)
        result = runner.invoke(app, ["config", "set", "allowed_account_ids", "456"])
        assert result.exit_code == 0, result.output
        assert "123 → 456" in result.output

    def test_unset_when_not_set_needs_no_tty(self, monkeypatch):
        confirm = self._tty(monkeypatch, tty=False)
        result = runner.invoke(app, ["config", "unset", "allowed_property_ids"])
        assert result.exit_code == 0
        confirm.assert_not_called()

    def test_other_keys_need_no_tty(self, monkeypatch):
        self._tty(monkeypatch, tty=False)
        result = runner.invoke(app, ["config", "set", "default_property_id", "5"])
        assert result.exit_code == 0
        assert get_config_value("default_property_id") == "5"


# ---------------------------------------------------------------------------
# Allowlist keys per profile: the confirmation names the scope (SPEC D1)
# ---------------------------------------------------------------------------
class TestAllowlistScope:
    GLOBAL = "(all profiles)"
    NARROWS = "(profile client-a, narrows the global allowlist)"

    def _tty(self, monkeypatch, tty=True, confirm=True):
        import ga_cli.commands.config_cmd as config_cmd

        monkeypatch.setattr(config_cmd, "_stdin_is_tty", lambda: tty)
        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = confirm
        monkeypatch.setattr("questionary.confirm", mock_confirm)
        return mock_confirm

    @staticmethod
    def _text(result):
        # Rich wraps long lines at the terminal width
        return " ".join(result.output.split())

    @staticmethod
    def _profile_file(root):
        return root / "profiles" / "client-a" / "config.json"

    def test_default_profile_set_names_all_profiles(self, monkeypatch, tmp_path):
        self._tty(monkeypatch)
        result = runner.invoke(app, ["config", "set", "allowed_account_ids", "222,111"])
        assert result.exit_code == 0, result.output
        assert f"allowed_account_ids {self.GLOBAL}: (not set) → 111, 222" in self._text(result)
        assert json.loads((tmp_path / "config.json").read_text()) == {
            "allowed_account_ids": ["111", "222"]
        }

    def test_named_profile_set_writes_profile_file(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_account_ids=["5"]))
        root_before = (tmp_path / "config.json").read_text()
        self._tty(monkeypatch)
        result = runner.invoke(
            app, ["--profile", "client-a", "config", "set", "allowed_account_ids", "1"]
        )
        assert result.exit_code == 0, result.output
        # The old value is the profile's own, not the root's
        assert f"allowed_account_ids {self.NARROWS}: (not set) → 1" in self._text(result)
        assert self.GLOBAL not in self._text(result)
        assert json.loads(self._profile_file(tmp_path).read_text()) == {
            "allowed_account_ids": ["1"]
        }
        assert (tmp_path / "config.json").read_text() == root_before

    def test_named_profile_set_without_tty_refused(self, monkeypatch, tmp_path):
        confirm = self._tty(monkeypatch, tty=False)
        result = runner.invoke(
            app, ["--profile", "client-a", "config", "set", "allowed_property_ids", "1"]
        )
        assert result.exit_code == 1
        assert "can only be changed interactively" in result.output
        assert not (tmp_path / "profiles" / "client-a").exists()
        confirm.assert_not_called()

    def test_named_profile_set_declined(self, monkeypatch, tmp_path):
        self._tty(monkeypatch, confirm=False)
        result = runner.invoke(
            app, ["--profile", "client-a", "config", "set", "allowed_property_ids", "1"]
        )
        assert result.exit_code == 0
        assert "Allowlist unchanged" in result.output
        assert not self._profile_file(tmp_path).exists()

    def test_named_profile_unset_names_scope(self, monkeypatch, tmp_path):
        save_config(UserConfig(allowed_account_ids=["5"]))
        path = self._profile_file(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"allowed_account_ids": ["1"]}))
        self._tty(monkeypatch)
        result = runner.invoke(
            app, ["--profile", "client-a", "config", "unset", "allowed_account_ids"]
        )
        assert result.exit_code == 0, result.output
        assert f"allowed_account_ids {self.NARROWS}: 1 → (not set)" in self._text(result)
        assert json.loads(path.read_text()) == {}
        assert json.loads((tmp_path / "config.json").read_text()) == {
            "allowed_account_ids": ["5"]
        }

    def test_default_profile_reset_names_scope(self, monkeypatch):
        save_config(UserConfig(allowed_account_ids=["1"], allowed_property_ids=["2"]))
        self._tty(monkeypatch)
        result = runner.invoke(app, ["config", "reset"])
        assert result.exit_code == 0, result.output
        text = self._text(result)
        assert f"allowed_account_ids {self.GLOBAL}: 1 → (not set)" in text
        assert f"allowed_property_ids {self.GLOBAL}: 2 → (not set)" in text

    def test_named_profile_reset_names_scope(self, monkeypatch, tmp_path):
        path = self._profile_file(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"allowed_property_ids": ["2"]}))
        self._tty(monkeypatch)
        result = runner.invoke(app, ["--profile", "client-a", "config", "reset"])
        assert result.exit_code == 0, result.output
        assert f"allowed_property_ids {self.NARROWS}: 2 → (not set)" in self._text(result)
        assert json.loads(path.read_text()) == {}

    def test_named_profile_unreadable_file_refused(self, monkeypatch, tmp_path):
        path = self._profile_file(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("{oops")
        confirm = self._tty(monkeypatch)
        result = runner.invoke(
            app, ["--profile", "client-a", "config", "set", "allowed_account_ids", "1"]
        )
        assert result.exit_code == 1
        assert "Fix the file first" in self._text(result)
        assert path.read_text() == "{oops"
        confirm.assert_not_called()

    def test_named_profile_writes_past_unreadable_root(self, monkeypatch, tmp_path):
        """Only the unreadable file is protected; the profile's own file isn't it."""
        (tmp_path / "config.json").write_text("{oops")
        self._tty(monkeypatch)
        result = runner.invoke(
            app, ["--profile", "client-a", "config", "set", "allowed_account_ids", "1"]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(self._profile_file(tmp_path).read_text()) == {
            "allowed_account_ids": ["1"]
        }
        assert (tmp_path / "config.json").read_text() == "{oops"


# ---------------------------------------------------------------------------
# Unreadable config.json: never overwritten
# ---------------------------------------------------------------------------
class TestUnreadableConfig:
    BROKEN = '{"allowed_property_ids": ["1"],}'

    def _broken(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(self.BROKEN)
        return path

    def test_loads_as_defaults(self, tmp_path):
        self._broken(tmp_path)
        assert load_config() == UserConfig()
        assert "Can't read" in config_error()

    def test_missing_file_is_not_an_error(self):
        assert load_config() == UserConfig()
        assert config_error() is None

    @pytest.mark.parametrize("text", ["", " \n"])
    def test_empty_file_is_an_empty_config(self, tmp_path, text):
        """It can't hold an allowlist, so it mustn't block every API command (#46)."""
        from ga_cli.config.allowlist import is_allowlist_configured

        (tmp_path / "config.json").write_text(text)
        assert load_config() == UserConfig()
        assert config_error() is None
        assert not is_allowlist_configured()
        result = runner.invoke(app, ["config", "set", "output_format", "json"])
        assert result.exit_code == 0, result.output

    @pytest.mark.parametrize("args", [[], ["default_property_id"]])
    def test_get_reports_the_unreadable_file(self, tmp_path, args):
        """Not nulls, which would tell an agent no allowlist is set."""
        path = self._broken(tmp_path)
        result = runner.invoke(app, ["config", "get", *args])
        assert result.exit_code == 1
        assert "Can't read" in " ".join(result.output.split())
        assert "null" not in result.output
        assert path.read_text() == self.BROKEN

    def test_save_config_refuses(self, tmp_path):
        path = self._broken(tmp_path)
        with pytest.raises(ConfigFileError) as exc:
            save_config(UserConfig(output_format="json"))
        # The same refusal `ga config` prints before its prompts
        assert "Fix the file first" in str(exc.value)
        assert path.read_text() == self.BROKEN

    def test_set_refused_file_unchanged(self, tmp_path):
        path = self._broken(tmp_path)
        result = runner.invoke(app, ["config", "set", "output_format", "json"])
        assert result.exit_code == 1
        # Rich wraps the message at the terminal width; the JSON error text varies by Python
        assert "Fix the file first" in " ".join(result.output.split())
        assert path.read_text() == self.BROKEN

    def test_unset_refused_file_unchanged(self, tmp_path):
        path = self._broken(tmp_path)
        result = runner.invoke(app, ["config", "unset", "default_property_id"])
        assert result.exit_code == 1
        assert path.read_text() == self.BROKEN

    def test_reset_refused_before_any_prompt(self, tmp_path, monkeypatch):
        path = self._broken(tmp_path)
        confirm = MagicMock()
        monkeypatch.setattr("questionary.confirm", confirm)
        result = runner.invoke(app, ["config", "reset"])
        assert result.exit_code == 1
        confirm.assert_not_called()
        assert path.read_text() == self.BROKEN

    def test_setup_refused_before_any_prompt(self, tmp_path, monkeypatch):
        path = self._broken(tmp_path)
        text = MagicMock()
        monkeypatch.setattr("questionary.text", text)
        result = runner.invoke(app, ["config", "setup"])
        assert result.exit_code == 1
        text.assert_not_called()
        assert path.read_text() == self.BROKEN


class TestSaveConfigAtomic:
    def test_no_temp_files_left(self, tmp_path):
        save_config(UserConfig(default_property_id="1"))
        assert [p.name for p in tmp_path.iterdir()] == ["config.json"]

    def test_writes_through_symlink(self, tmp_path):
        real = tmp_path / "dotfiles" / "config.json"
        real.parent.mkdir()
        real.write_text("{}")
        (tmp_path / "config.json").symlink_to(real)
        save_config(UserConfig(default_property_id="1"))
        assert (tmp_path / "config.json").is_symlink()
        assert json.loads(real.read_text()) == {"default_property_id": "1"}


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
