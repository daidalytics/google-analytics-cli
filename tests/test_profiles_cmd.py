"""Tests for ``ga profiles list`` and ``ga profiles delete``.

Both commands are offline: they read and remove files under the config dir
and never build an API client or touch credentials.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()

SA_EMAIL = "reporter@client-a.iam.gserviceaccount.com"


def _profile_dir(root, name):
    return root if name == "default" else root / "profiles" / name


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content if isinstance(content, str) else json.dumps(content))


def _flat(text):
    """Collapse Rich's 80-column line wrapping so phrases can be matched."""
    return " ".join(text.split())


@pytest.fixture
def wide_console(monkeypatch):
    """Render tables at 200 columns so cells don't wrap under CliRunner."""
    import importlib

    from rich.console import Console

    # `ga_cli.utils.output` as a dotted string resolves to the re-exported
    # output() function, so patch the module object itself.
    output_module = importlib.import_module("ga_cli.utils.output")
    monkeypatch.setattr(output_module, "console", Console(width=200))


def _make_profile(
    root,
    name,
    *,
    sa_email=None,
    sa_path="/keys/sa.json",
    oauth=False,
    property_id=None,
):
    """Create a profile's files the way `auth login` / `config set` would."""
    directory = _profile_dir(root, name)
    directory.mkdir(parents=True, exist_ok=True)
    if sa_email:
        _write(
            directory / "auth-method.json",
            {
                "method": "service-account",
                "service_account_path": str(sa_path),
                "service_account_email": sa_email,
            },
        )
    if oauth:
        _write(
            directory / "credentials.json",
            {"token": "t", "refresh_token": "r", "client_id": "c", "client_secret": "s"},
        )
    if property_id:
        _write(directory / "config.json", {"default_property_id": property_id})
    return directory


def _list_json(*args, env=None):
    result = runner.invoke(app, [*args, "profiles", "list", "-o", "json"], env=env)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _by_name(rows):
    return {row["name"]: row for row in rows}


class TestProfilesList:
    def test_default_only(self, isolated_config_dir):
        rows = _list_json()

        assert rows == [
            {
                "name": "default",
                "active": True,
                "method": "none",
                "service_account_email": None,
                "default_property_id": None,
                "path": str(isolated_config_dir),
            }
        ]

    def test_multiple_profiles_sorted_default_first(self, isolated_config_dir):
        for name in ("zeta", "alpha", "client-b"):
            _make_profile(isolated_config_dir, name)

        rows = _list_json()

        assert [row["name"] for row in rows] == ["default", "alpha", "client-b", "zeta"]

    def test_named_profile_path(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")

        rows = _by_name(_list_json())

        assert rows["client-a"]["path"] == str(isolated_config_dir / "profiles" / "client-a")

    def test_method_service_account(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL)

        row = _by_name(_list_json())["client-a"]

        assert row["method"] == "service-account"
        assert row["service_account_email"] == SA_EMAIL

    def test_method_oauth(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a", oauth=True)

        row = _by_name(_list_json())["client-a"]

        assert row["method"] == "oauth"
        assert row["service_account_email"] is None

    def test_method_none(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a", property_id="123")

        row = _by_name(_list_json())["client-a"]

        assert row["method"] == "none"

    def test_service_account_beats_oauth(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL, oauth=True)

        row = _by_name(_list_json())["client-a"]

        assert row["method"] == "service-account"
        assert row["service_account_email"] == SA_EMAIL

    def test_default_profile_reads_root_files(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "default", oauth=True, property_id="250400352")

        row = _by_name(_list_json())["default"]

        assert row["method"] == "oauth"
        assert row["default_property_id"] == "250400352"

    def test_default_property_per_profile(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "default", property_id="111")
        _make_profile(isolated_config_dir, "client-a", property_id="222")
        _make_profile(isolated_config_dir, "client-b")

        rows = _by_name(_list_json())

        assert rows["default"]["default_property_id"] == "111"
        assert rows["client-a"]["default_property_id"] == "222"
        assert rows["client-b"]["default_property_id"] is None

    def test_active_defaults_to_default(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")

        rows = _by_name(_list_json())

        assert rows["default"]["active"] is True
        assert rows["client-a"]["active"] is False

    def test_active_follows_profile_flag(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")
        _make_profile(isolated_config_dir, "client-b")

        rows = _by_name(_list_json("--profile", "client-b"))

        assert [name for name, row in rows.items() if row["active"]] == ["client-b"]

    def test_active_follows_env_var(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")
        _make_profile(isolated_config_dir, "client-b")

        rows = _by_name(_list_json(env={"GA_CLI_PROFILE": "client-a"}))

        assert [name for name, row in rows.items() if row["active"]] == ["client-a"]

    def test_listing_another_profile_does_not_switch_active(self, isolated_config_dir):
        """Inspecting other profiles must read their files directly, not activate them."""
        from ga_cli.config.constants import get_active_profile, set_active_profile

        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL, property_id="1")
        _make_profile(isolated_config_dir, "client-b", oauth=True, property_id="2")

        with patch(
            "ga_cli.config.constants.set_active_profile", wraps=set_active_profile
        ) as spy:
            rows = _by_name(_list_json("--profile", "client-a"))

        spy.assert_called_once_with("client-a")  # the root callback only
        assert get_active_profile() == "client-a"
        assert rows["client-b"]["method"] == "oauth"
        assert rows["client-b"]["default_property_id"] == "2"

    def test_missing_active_profile_warns(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")

        result = runner.invoke(app, ["--profile", "typo", "profiles", "list", "-o", "json"])

        assert result.exit_code == 0
        rows = json.loads(result.stdout)
        assert not any(row["active"] for row in rows)
        assert "typo" in result.stderr
        assert not (isolated_config_dir / "profiles" / "typo").exists()

    def test_json_shape(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL, property_id="9")

        rows = _list_json()

        assert isinstance(rows, list)
        for row in rows:
            assert set(row) == {
                "name",
                "active",
                "method",
                "service_account_email",
                "default_property_id",
                "path",
            }
            assert isinstance(row["active"], bool)
            assert row["method"] in {"service-account", "oauth", "none"}

    @pytest.mark.parametrize("garbage", ["{not json", "[1, 2]", '"string"', "", b"\xff\xfe{"])
    def test_corrupt_json_tolerated(self, isolated_config_dir, garbage):
        directory = _make_profile(isolated_config_dir, "client-a")
        for filename in ("auth-method.json", "credentials.json", "config.json"):
            _write(directory / filename, garbage)

        row = _by_name(_list_json())["client-a"]

        assert row["method"] == "none"
        assert row["service_account_email"] is None
        assert row["default_property_id"] is None

    def test_corrupt_auth_method_falls_back_to_oauth(self, isolated_config_dir):
        directory = _make_profile(isolated_config_dir, "client-a", oauth=True)
        _write(directory / "auth-method.json", "{oops")

        row = _by_name(_list_json())["client-a"]

        assert row["method"] == "oauth"

    def test_corrupt_default_profile_config_tolerated(self, isolated_config_dir):
        _write(isolated_config_dir / "config.json", "{oops")

        result = runner.invoke(app, ["profiles", "list", "-o", "json"])

        assert result.exit_code == 0, result.output
        row = _by_name(json.loads(result.stdout))["default"]
        assert row["default_property_id"] is None

    def test_table_output(self, isolated_config_dir, wide_console):
        _make_profile(isolated_config_dir, "default", oauth=True, property_id="111")
        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL, property_id="222")
        _make_profile(isolated_config_dir, "client-b")

        result = runner.invoke(app, ["profiles", "list", "-o", "table"])

        assert result.exit_code == 0, result.output
        lines = result.stdout.splitlines()
        default_line = next(line for line in lines if " default " in line)
        assert "*" in default_line
        assert "oauth" in default_line
        assert "111" in default_line
        client_b_line = next(line for line in lines if "client-b" in line)
        assert "*" not in client_b_line
        assert "none" in client_b_line
        assert "—" in client_b_line
        assert "service-account" in result.stdout
        assert "reporter@client-a" in result.stdout
        assert "222" in result.stdout

    def test_table_marks_active_named_profile(self, isolated_config_dir, wide_console):
        _make_profile(isolated_config_dir, "client-a")

        result = runner.invoke(app, ["--profile", "client-a", "profiles", "list", "-o", "table"])

        assert result.exit_code == 0, result.output
        lines = result.stdout.splitlines()
        assert "*" in next(line for line in lines if "client-a" in line)
        assert "*" not in next(line for line in lines if " default " in line)

    def test_compact_output(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")

        result = runner.invoke(app, ["profiles", "list", "-o", "compact"])

        assert result.exit_code == 0, result.output
        names = [line.split("\t")[0] for line in result.stdout.splitlines()]
        assert names == ["default", "client-a"]

    def test_help_says_stored_credentials_only(self):
        result = runner.invoke(app, ["profiles", "list", "--help"])

        assert result.exit_code == 0
        assert "stored" in _flat(result.output)
        assert "ga auth status" in _flat(result.output)

    def test_no_api_client_or_credentials(self, isolated_config_dir):
        """Listing is file-only: no client build, no credential load or refresh."""
        _make_profile(isolated_config_dir, "default", oauth=True, property_id="1")
        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL, oauth=True)

        targets = [
            "googleapiclient.discovery.build",
            "ga_cli.api.client.build",
            "ga_cli.api.client._get_credentials",
            "ga_cli.api.client.get_admin_client",
            "ga_cli.api.client.get_admin_alpha_client",
            "ga_cli.api.client.get_data_client",
            "ga_cli.api.client.get_data_alpha_client",
            "ga_cli.auth.credentials.load_credentials",
            "ga_cli.auth.credentials.get_valid_credentials",
            "ga_cli.auth.service_account.get_service_account_credentials",
            "google.oauth2.credentials.Credentials.refresh",
            "google.oauth2.service_account.Credentials.refresh",
            "google.auth.default",
        ]
        with ExitStack() as stack:
            mocks = {target: stack.enter_context(patch(target)) for target in targets}
            for fmt in ("json", "table", "compact"):
                result = runner.invoke(app, ["profiles", "list", "-o", fmt])
                assert result.exit_code == 0, result.output

        for target, mock in mocks.items():
            assert not mock.called, f"{target} was called"


class TestProfilesDelete:
    def test_refuses_default(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "default", oauth=True, property_id="1")

        with patch("ga_cli.commands.profiles.questionary") as mock_q:
            result = runner.invoke(app, ["profiles", "delete", "default", "--yes"])

        assert result.exit_code == 1
        assert "default" in result.output
        assert "ga auth logout" in _flat(result.output)
        assert "ga config reset" in _flat(result.output)
        mock_q.confirm.assert_not_called()
        assert (isolated_config_dir / "credentials.json").exists()
        assert (isolated_config_dir / "config.json").exists()

    @pytest.mark.parametrize("name", ["..", ".", ".hidden", "a/b", "../profiles", "has space"])
    def test_invalid_name(self, isolated_config_dir, name):
        _make_profile(isolated_config_dir, "default", oauth=True)
        _make_profile(isolated_config_dir, "client-a")

        result = runner.invoke(app, ["profiles", "delete", name, "--yes"])

        assert result.exit_code == 1
        assert "Invalid profile name" in _flat(result.output)
        assert (isolated_config_dir / "credentials.json").exists()
        assert (isolated_config_dir / "profiles" / "client-a").is_dir()

    def test_unknown_profile_lists_known(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")
        _make_profile(isolated_config_dir, "client-b")

        result = runner.invoke(app, ["profiles", "delete", "clinet-a", "--yes"])

        assert result.exit_code == 1
        assert "clinet-a" in result.output
        assert "does not exist" in _flat(result.output)
        assert "default, client-a, client-b" in _flat(result.output)

    def test_prompts_without_yes_and_decline_keeps_dir(self, isolated_config_dir):
        directory = _make_profile(isolated_config_dir, "client-a", oauth=True)

        with patch("ga_cli.commands.profiles.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(app, ["profiles", "delete", "client-a"])

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()
        assert "client-a" in mock_q.confirm.call_args.args[0]
        assert "Cancelled" in result.output
        assert directory.is_dir()
        assert (directory / "credentials.json").exists()

    def test_prompt_aborted_keeps_dir(self, isolated_config_dir):
        """Ctrl-C at the prompt makes questionary return None: treat as a decline."""
        directory = _make_profile(isolated_config_dir, "client-a")

        with patch("ga_cli.commands.profiles.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = None
            result = runner.invoke(app, ["profiles", "delete", "client-a"])

        assert result.exit_code == 0
        assert directory.is_dir()

    def test_prompt_confirm_deletes(self, isolated_config_dir):
        directory = _make_profile(isolated_config_dir, "client-a", oauth=True)

        with patch("ga_cli.commands.profiles.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(app, ["profiles", "delete", "client-a"])

        assert result.exit_code == 0, result.output
        assert not directory.exists()

    def test_yes_deletes_without_prompt(self, isolated_config_dir):
        directory = _make_profile(
            isolated_config_dir, "client-a", sa_email=SA_EMAIL, oauth=True, property_id="1"
        )
        (directory / "chat-sessions.json").write_text("{}")

        with patch("ga_cli.commands.profiles.questionary") as mock_q:
            result = runner.invoke(app, ["profiles", "delete", "client-a", "--yes"])

        assert result.exit_code == 0, result.output
        mock_q.confirm.assert_not_called()
        assert not directory.exists()
        assert "client-a" in result.output
        assert "deleted" in result.output.lower()

    def test_short_yes_flag(self, isolated_config_dir):
        directory = _make_profile(isolated_config_dir, "client-a")

        result = runner.invoke(app, ["profiles", "delete", "client-a", "-y"])

        assert result.exit_code == 0, result.output
        assert not directory.exists()

    def test_leaves_other_profiles_and_root_alone(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "default", oauth=True, property_id="1")
        _write(isolated_config_dir / "client_secret.json", {"installed": {}})
        _make_profile(isolated_config_dir, "client-a", oauth=True)
        other = _make_profile(isolated_config_dir, "client-b", oauth=True)

        result = runner.invoke(app, ["profiles", "delete", "client-a", "--yes"])

        assert result.exit_code == 0, result.output
        assert (isolated_config_dir / "credentials.json").exists()
        assert (isolated_config_dir / "config.json").exists()
        assert (isolated_config_dir / "client_secret.json").exists()
        assert (other / "credentials.json").exists()
        assert (isolated_config_dir / "profiles").is_dir()

    def test_sa_key_outside_profile_survives(self, isolated_config_dir, tmp_path_factory):
        key = tmp_path_factory.mktemp("keys") / "client-a.json"
        key.write_text(json.dumps({"type": "service_account", "client_email": SA_EMAIL}))
        directory = _make_profile(
            isolated_config_dir, "client-a", sa_email=SA_EMAIL, sa_path=key
        )

        result = runner.invoke(app, ["profiles", "delete", "client-a", "--yes"])

        assert result.exit_code == 0, result.output
        assert not directory.exists()
        assert key.exists()

    def test_sa_key_in_config_root_survives(self, isolated_config_dir):
        """A key next to (not inside) the profile dir is not the profile's to delete."""
        key = isolated_config_dir / "keys" / "client-a.json"
        _write(key, {"type": "service_account"})
        directory = _make_profile(
            isolated_config_dir, "client-a", sa_email=SA_EMAIL, sa_path=key
        )

        result = runner.invoke(app, ["profiles", "delete", "client-a", "--yes"])

        assert result.exit_code == 0, result.output
        assert not directory.exists()
        assert key.exists()

    @pytest.mark.parametrize("relative", ["sa.json", "keys/nested/sa.json"])
    def test_sa_key_inside_profile_aborts(self, isolated_config_dir, relative):
        directory = isolated_config_dir / "profiles" / "client-a"
        key = directory / relative
        _write(key, {"type": "service_account"})
        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL, sa_path=key)

        with patch("ga_cli.commands.profiles.questionary") as mock_q:
            result = runner.invoke(app, ["profiles", "delete", "client-a", "--yes"])

        assert result.exit_code == 1
        assert str(key) in result.output.replace("\n", "")
        mock_q.confirm.assert_not_called()
        assert directory.is_dir()
        assert key.exists()
        assert (directory / "auth-method.json").exists()

    def test_sa_key_inside_profile_aborts_before_prompt(self, isolated_config_dir):
        directory = isolated_config_dir / "profiles" / "client-a"
        key = directory / "sa.json"
        _write(key, {"type": "service_account"})
        _make_profile(isolated_config_dir, "client-a", sa_email=SA_EMAIL, sa_path=key)

        with patch("ga_cli.commands.profiles.questionary") as mock_q:
            result = runner.invoke(app, ["profiles", "delete", "client-a"])

        assert result.exit_code == 1
        mock_q.confirm.assert_not_called()
        assert key.exists()

    def test_corrupt_auth_method_still_deletes(self, isolated_config_dir):
        directory = _make_profile(isolated_config_dir, "client-a")
        _write(directory / "auth-method.json", "{oops")

        result = runner.invoke(app, ["profiles", "delete", "client-a", "--yes"])

        assert result.exit_code == 0, result.output
        assert not directory.exists()

    def test_can_delete_active_profile(self, isolated_config_dir):
        directory = _make_profile(isolated_config_dir, "client-a", oauth=True)

        result = runner.invoke(
            app, ["--profile", "client-a", "profiles", "delete", "client-a", "--yes"]
        )

        assert result.exit_code == 0, result.output
        assert not directory.exists()

    def test_deleted_profile_no_longer_listed(self, isolated_config_dir):
        _make_profile(isolated_config_dir, "client-a")
        _make_profile(isolated_config_dir, "client-b")

        runner.invoke(app, ["profiles", "delete", "client-a", "--yes"])

        assert [row["name"] for row in _list_json()] == ["default", "client-b"]
