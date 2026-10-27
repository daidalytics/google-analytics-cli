"""Tests for ga_cli.config.allowlist (configuration and resolution)."""

import json

import pytest

from ga_cli.config import store
from ga_cli.config.allowlist import (
    Allowlist,
    AllowlistSource,
    is_allowlist_configured,
    load_allowlist,
    parse_ids,
)
from ga_cli.config.constants import get_config_path, set_active_profile
from ga_cli.utils.errors import AllowlistConfigError, AllowlistError


def _write_config(tmp_path, data):
    (tmp_path / "config.json").write_text(json.dumps(data))
    store.reset_cache()


def _write_profile_config(tmp_path, profile, data):
    """A named profile's own config.json; ``data`` may be raw text."""
    path = tmp_path / "profiles" / profile / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    store.reset_cache()
    return path


def _no_lookup():
    raise AssertionError("account lookup should not be needed")


class TestParseIds:
    def test_comma_string(self):
        assert parse_ids("123, 456,", "accounts", "x") == {"123", "456"}

    def test_list(self):
        assert parse_ids(["123", "456"], "properties", "x") == {"123", "456"}

    def test_prefix_normalised(self):
        assert parse_ids("accounts/123,456", "accounts", "x") == {"123", "456"}
        assert parse_ids(["properties/9"], "properties", "x") == {"9"}

    def test_wrong_prefix_rejected(self):
        with pytest.raises(AllowlistError):
            parse_ids("properties/123", "accounts", "x")

    def test_empty_string_is_empty_set(self):
        assert parse_ids("", "accounts", "x") == frozenset()

    def test_non_numeric_rejected_with_origin(self):
        with pytest.raises(AllowlistError) as exc:
            parse_ids("123,abc", "accounts", "GA_CLI_ALLOWED_ACCOUNTS")
        assert exc.value.resource == "GA_CLI_ALLOWED_ACCOUNTS"
        assert "'abc'" in str(exc.value)

    def test_non_list_config_value_rejected(self):
        with pytest.raises(AllowlistError):
            parse_ids(123, "accounts", "x")  # type: ignore[arg-type]

    def test_non_string_item_rejected(self):
        with pytest.raises(AllowlistError):
            parse_ids([123], "accounts", "x")  # type: ignore[list-item]

    @pytest.mark.parametrize("value", ["properties/123", "abc", 123, [123]])
    def test_every_rejection_is_a_config_error(self, value):
        """A malformed entry means the allowlist itself can't be loaded."""
        with pytest.raises(AllowlistConfigError):
            parse_ids(value, "accounts", "x")


class TestLoadAllowlist:
    def test_nothing_configured_is_off(self):
        al = load_allowlist()
        assert not al.enabled
        assert al.allows_account("1")
        assert al.allows_property("1", _no_lookup)
        assert not is_allowlist_configured()

    def test_file_only(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["123"]})
        al = load_allowlist()
        assert [s.name for s in al.sources] == ["config"]
        assert al.allows_account("123")
        assert not al.allows_account("456")
        assert is_allowlist_configured()

    def test_env_only(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "properties/250400352")
        al = load_allowlist()
        assert [s.name for s in al.sources] == ["env"]
        assert al.sources[0].accounts is None
        assert al.allows_property("250400352", _no_lookup)
        assert not al.allows_property("999", lambda: "123")

    def test_env_narrows_file(self, tmp_path, monkeypatch):
        _write_config(tmp_path, {"allowed_account_ids": ["123", "456"]})
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "123")
        al = load_allowlist()
        assert al.allows_account("123")
        assert not al.allows_account("456")

    def test_env_cannot_widen_file(self, tmp_path, monkeypatch):
        _write_config(tmp_path, {"allowed_account_ids": ["123"]})
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "123,456")
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "999")
        al = load_allowlist()
        assert not al.allows_account("456")
        # 999 belongs to account 456: env lists it, file doesn't allow it
        assert not al.allows_property("999", lambda: "456")

    def test_empty_env_denies_everything(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "")
        al = load_allowlist()
        assert al.enabled
        assert not al.allows_account("123")
        assert not al.allows_property("1", lambda: "123")

    def test_empty_config_list_denies_everything(self, tmp_path):
        _write_config(tmp_path, {"allowed_property_ids": []})
        al = load_allowlist()
        assert al.enabled
        assert not al.allows_property("1", lambda: "1")

    def test_invalid_env_id_raises(self, monkeypatch):
        monkeypatch.setenv("GA_CLI_ALLOWED_PROPERTIES", "12x")
        with pytest.raises(AllowlistError):
            load_allowlist()

    def test_invalid_config_id_raises(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["oops"]})
        with pytest.raises(AllowlistError) as exc:
            load_allowlist()
        assert "allowed_account_ids" in exc.value.resource

    @pytest.mark.parametrize(
        "text",
        ['{"allowed_property_ids": ["1"],}', "[]"],
        ids=["trailing comma", "not an object"],
    )
    def test_unreadable_config_fails_closed(self, tmp_path, text):
        # An empty file is an empty config instead (test_config_cmd, #46)
        (tmp_path / "config.json").write_text(text)
        store.reset_cache()
        assert is_allowlist_configured()
        with pytest.raises(AllowlistError) as exc:
            load_allowlist()
        assert exc.value.resource == "config.json"
        assert "the allowlist can't be checked" in str(exc.value)

    def test_old_config_without_keys_loads(self, tmp_path):
        _write_config(tmp_path, {"default_property_id": "1"})
        cfg = store.load_config()
        assert cfg.allowed_account_ids is None
        assert cfg.allowed_property_ids is None


class TestProfileSources:
    """The root config.json is the fence for every profile; a named profile's own
    config.json only narrows it (SPEC D1)."""

    def test_root_profile_and_env_intersect(self, tmp_path, monkeypatch):
        _write_config(tmp_path, {"allowed_account_ids": ["1", "2", "3"]})
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["1", "2"]})
        monkeypatch.setenv("GA_CLI_ALLOWED_ACCOUNTS", "1,3")
        set_active_profile("client-a")
        al = load_allowlist()
        assert [s.name for s in al.sources] == ["config", "profile client-a", "env"]
        assert al.allows_account("1")
        assert not al.allows_account("2")  # not in env
        assert not al.allows_account("3")  # not in the profile
        assert al.allowed_accounts() == {"1"}
        assert al.describe() == (
            "config: accounts 1, 2, 3 | profile client-a: accounts 1, 2 | env: accounts 1, 3"
        )

    def test_default_profile_has_one_file_source(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["1"]})
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["2"]})
        al = load_allowlist()
        assert [s.name for s in al.sources] == ["config"]
        assert al.allows_account("1")

    def test_named_profile_inherits_root_fence(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["1"]})
        _write_profile_config(tmp_path, "client-a", {"default_property_id": "9"})
        set_active_profile("client-a")
        assert is_allowlist_configured()
        al = load_allowlist()
        assert al.enabled
        assert [s.name for s in al.sources] == ["config"]
        assert al.allows_account("1")
        assert not al.allows_account("2")
        assert not al.allows_property("9", lambda: "2")

    def test_profile_cannot_widen_root(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["1"]})
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["1", "2"]})
        set_active_profile("client-a")
        al = load_allowlist()
        assert not al.allows_account("2")
        assert not al.allows_property("9", lambda: "2")

    def test_profile_narrows_only_itself(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["1", "2"]})
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["1"]})
        _write_profile_config(tmp_path, "client-b", {})
        set_active_profile("client-a")
        assert not load_allowlist().allows_account("2")
        set_active_profile("client-b")
        assert load_allowlist().allows_account("2")
        set_active_profile(None)
        assert load_allowlist().allows_account("2")

    def test_profile_only_allowlist(self, tmp_path):
        _write_profile_config(tmp_path, "client-a", {"allowed_property_ids": ["7"]})
        set_active_profile("client-a")
        assert is_allowlist_configured()
        al = load_allowlist()
        assert [s.name for s in al.sources] == ["profile client-a"]
        assert al.allows_property("7", _no_lookup)
        assert not al.allows_property("8", lambda: "1")
        set_active_profile(None)
        assert not is_allowlist_configured()
        assert not load_allowlist().enabled

    def test_unknown_profile_has_no_profile_source(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["1"]})
        set_active_profile("nope")
        assert [s.name for s in load_allowlist().sources] == ["config"]
        assert not (tmp_path / "profiles" / "nope").exists()

    def test_invalid_profile_id_names_the_source(self, tmp_path):
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["oops"]})
        set_active_profile("client-a")
        with pytest.raises(AllowlistError) as exc:
            load_allowlist()
        assert exc.value.resource == "profile client-a config key allowed_account_ids"

    def test_invalid_root_id_fails_every_profile(self, tmp_path):
        _write_config(tmp_path, {"allowed_property_ids": ["x"]})
        _write_profile_config(tmp_path, "client-a", {})
        set_active_profile("client-a")
        with pytest.raises(AllowlistError) as exc:
            load_allowlist()
        assert exc.value.resource == "config key allowed_property_ids"

    def test_unreadable_root_fails_closed_in_named_profile(self, tmp_path):
        (tmp_path / "config.json").write_text('{"allowed_account_ids": ["1"],}')
        _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["1"]})
        set_active_profile("client-a")
        assert is_allowlist_configured()
        with pytest.raises(AllowlistError) as exc:
            load_allowlist()
        assert exc.value.resource == "config.json"
        assert "the allowlist can't be checked" in str(exc.value)

    def test_unreadable_root_counts_as_set_without_profile_dir(self, tmp_path):
        (tmp_path / "config.json").write_text("[]")
        set_active_profile("client-a")
        assert is_allowlist_configured()
        with pytest.raises(AllowlistError):
            load_allowlist()

    def test_unreadable_profile_fails_only_that_profile(self, tmp_path):
        path = _write_profile_config(tmp_path, "client-a", '{"allowed_account_ids": ["1"],}')
        _write_profile_config(tmp_path, "client-b", {})
        set_active_profile("client-a")
        assert is_allowlist_configured()
        with pytest.raises(AllowlistError) as exc:
            load_allowlist()
        assert exc.value.resource == "profiles/client-a/config.json"
        assert str(path) in str(exc.value)
        for other in (None, "client-b"):
            set_active_profile(other)
            assert not is_allowlist_configured()
            assert not load_allowlist().enabled


class TestStorePerPath:
    """store.py reads the root config.json next to the active profile's (SPEC D1)."""

    def test_root_config_path(self, tmp_path):
        assert store.get_root_config_path() == tmp_path / "config.json"
        assert store.get_root_config_path() == get_config_path()
        set_active_profile("client-a")
        assert store.get_root_config_path() == tmp_path / "config.json"
        assert get_config_path() == tmp_path / "profiles" / "client-a" / "config.json"

    def test_load_config_at_reads_that_file(self, tmp_path):
        _write_config(tmp_path, {"allowed_account_ids": ["1"], "default_property_id": "5"})
        path = _write_profile_config(tmp_path, "client-a", {"allowed_account_ids": ["2"]})
        assert store.load_config_at(tmp_path / "config.json").allowed_account_ids == ["1"]
        assert store.load_config_at(path).allowed_account_ids == ["2"]
        assert store.load_config_at(path).default_property_id is None

    def test_load_config_is_the_active_file(self, tmp_path):
        path = _write_profile_config(tmp_path, "client-a", {"default_property_id": "5"})
        set_active_profile("client-a")
        assert store.load_config() is store.load_config_at(path)

    def test_missing_file_loads_defaults(self, tmp_path):
        missing = tmp_path / "profiles" / "nope" / "config.json"
        assert store.load_config_at(missing) == store.UserConfig()
        assert store.config_error(missing) is None
        assert not missing.parent.exists()

    def test_reading_root_keeps_active_profile_cache(self, tmp_path):
        _write_config(tmp_path, {"default_property_id": "1"})
        _write_profile_config(tmp_path, "client-a", {"default_property_id": "2"})
        set_active_profile("client-a")
        active = store.load_config()
        root = store.load_config_at(store.get_root_config_path())
        assert root.default_property_id == "1"
        assert store.load_config() is active
        assert store.get_config_value("default_property_id") == "2"

    def test_config_error_is_per_path(self, tmp_path):
        (tmp_path / "config.json").write_text("{oops")
        path = _write_profile_config(tmp_path, "client-a", {})
        set_active_profile("client-a")
        assert store.config_error() is None
        assert store.config_error(path) is None
        reason = store.config_error(tmp_path / "config.json")
        assert reason.startswith(f"Can't read {tmp_path / 'config.json'}")
        # Reading the broken root left the active profile's state alone
        assert store.config_error() is None

    def test_config_error_defaults_to_active_profile(self, tmp_path):
        _write_profile_config(tmp_path, "client-a", "[]")
        assert store.config_error() is None
        set_active_profile("client-a")
        assert "Can't read" in store.config_error()

    def test_named_profile_saves_past_unreadable_root(self, tmp_path):
        """Only the unreadable file itself is protected from being overwritten."""
        (tmp_path / "config.json").write_text("{oops")
        set_active_profile("client-a")
        store.save_config(store.UserConfig(default_property_id="5"))
        saved = json.loads((tmp_path / "profiles" / "client-a" / "config.json").read_text())
        assert saved == {"default_property_id": "5"}
        assert (tmp_path / "config.json").read_text() == "{oops"
        set_active_profile(None)
        with pytest.raises(store.ConfigFileError):
            store.save_config(store.UserConfig())

    def test_save_updates_only_its_own_cache_entry(self, tmp_path):
        _write_config(tmp_path, {"default_property_id": "1"})
        root = store.load_config_at(tmp_path / "config.json")
        set_active_profile("client-a")
        store.save_config(store.UserConfig(default_property_id="2"))
        assert store.load_config_at(tmp_path / "config.json") is root
        assert store.load_config().default_property_id == "2"

    def test_reset_cache_forgets_every_path(self, tmp_path):
        _write_config(tmp_path, {"default_property_id": "1"})
        path = _write_profile_config(tmp_path, "client-a", "{oops")
        root_path = tmp_path / "config.json"
        assert store.load_config_at(root_path).default_property_id == "1"
        assert store.config_error(path) is not None

        root_path.write_text(json.dumps({"default_property_id": "3"}))
        path.write_text(json.dumps({"default_property_id": "4"}))
        # Still cached until reset
        assert store.load_config_at(root_path).default_property_id == "1"
        assert store.config_error(path) is not None

        store.reset_cache()
        assert store.load_config_at(root_path).default_property_id == "3"
        assert store.load_config_at(path).default_property_id == "4"
        assert store.config_error(path) is None


class TestResolution:
    def _al(self, *sources):
        return Allowlist(tuple(sources))

    def test_property_via_account(self):
        al = self._al(AllowlistSource("config", frozenset({"123"}), None))
        assert al.allows_property("1", lambda: "123")
        assert not al.allows_property("2", lambda: "456")

    def test_unknown_account_denied(self):
        al = self._al(AllowlistSource("config", frozenset({"123"}), None))
        assert not al.allows_property("1", lambda: None)

    def test_property_only_source_denies_account_level(self):
        al = self._al(AllowlistSource("env", None, frozenset({"1"})))
        assert al.allows_property("1", _no_lookup)
        assert not al.allows_account("123")

    def test_direct_hit_in_every_source_never_looks_up(self):
        al = self._al(
            AllowlistSource("config", frozenset({"123"}), frozenset({"1"})),
            AllowlistSource("env", None, frozenset({"1"})),
        )
        assert al.lists_property("1")
        assert al.allows_property("1", _no_lookup)

    def test_lookup_called_at_most_once(self):
        calls = []

        def lookup():
            calls.append(1)
            return "123"

        al = self._al(
            AllowlistSource("config", frozenset({"123"}), None),
            AllowlistSource("env", frozenset({"123"}), None),
        )
        assert al.allows_property("1", lookup)
        assert len(calls) == 1

    def test_visible_accounts(self):
        al = self._al(AllowlistSource("config", frozenset({"10"}), frozenset({"2"})))
        prop_map = {"1": "10", "2": "20", "3": "30"}
        assert al.visible_accounts(prop_map) == {"10", "20"}

    def test_visible_accounts_includes_allowed_account_without_properties(self):
        al = self._al(AllowlistSource("config", frozenset({"10"}), None))
        assert al.visible_accounts({}) == {"10"}

    def test_visible_accounts_intersection(self):
        al = self._al(
            AllowlistSource("config", frozenset({"10", "20"}), None),
            AllowlistSource("env", None, frozenset({"2"})),
        )
        assert al.visible_accounts({"1": "10", "2": "20"}) == {"20"}

    def test_describe(self):
        al = self._al(
            AllowlistSource("config", frozenset({"123"}), None),
            AllowlistSource("env", None, frozenset()),
        )
        assert al.describe() == "config: accounts 123 | env: properties (none)"

    def test_describe_sorts_numerically(self):
        src = AllowlistSource("config", frozenset({"9", "10"}), frozenset())
        assert src.summary() == "accounts 9, 10; properties (none)"
        assert src.describe() == "config: accounts 9, 10; properties (none)"

    def test_listed_properties_is_union(self):
        al = Allowlist((
            AllowlistSource("config", frozenset({"1"}), frozenset({"2"})),
            AllowlistSource("env", None, frozenset({"3"})),
        ))
        assert al.listed_properties() == {"2", "3"}
