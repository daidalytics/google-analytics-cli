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
from ga_cli.utils.errors import AllowlistError


def _write_config(tmp_path, data):
    (tmp_path / "config.json").write_text(json.dumps(data))
    store._cached_config = None


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
        ['{"allowed_property_ids": ["1"],}', "", "[]"],
        ids=["trailing comma", "empty file", "not an object"],
    )
    def test_unreadable_config_fails_closed(self, tmp_path, text):
        (tmp_path / "config.json").write_text(text)
        store._cached_config = None
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
