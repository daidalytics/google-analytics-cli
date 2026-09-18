"""Tests for the per-property chat session cache."""

import json

from ga_cli.config.chat_session import clear_session, load_session, save_session
from ga_cli.config.constants import get_chat_sessions_path


class TestSessionRoundTrip:
    def test_saves_and_loads_a_session_id(self, isolated_config_dir):
        save_session("111", "session-abc")

        assert load_session("111") == "session-abc"

    def test_overwrites_the_previous_session_for_the_same_property(self, isolated_config_dir):
        save_session("111", "session-old")
        save_session("111", "session-new")

        assert load_session("111") == "session-new"

    def test_records_an_updated_timestamp(self, isolated_config_dir):
        save_session("111", "session-abc")

        stored = json.loads(get_chat_sessions_path().read_text())
        assert stored["111"]["sessionId"] == "session-abc"
        assert stored["111"]["updatedAt"]

    def test_stores_nothing_but_the_session_id_and_timestamp(self, isolated_config_dir):
        """Conversation content must never reach disk."""
        save_session("111", "session-abc")

        stored = json.loads(get_chat_sessions_path().read_text())
        assert set(stored["111"].keys()) == {"sessionId", "updatedAt"}


class TestSessionIsolationBetweenProperties:
    def test_sessions_are_keyed_by_property(self, isolated_config_dir):
        save_session("111", "session-one")
        save_session("222", "session-two")

        assert load_session("111") == "session-one"
        assert load_session("222") == "session-two"

    def test_clear_removes_only_the_target_property(self, isolated_config_dir):
        save_session("111", "session-one")
        save_session("222", "session-two")

        clear_session("111")

        assert load_session("111") is None
        assert load_session("222") == "session-two"


class TestSessionMissingAndCorruptState:
    def test_returns_none_when_no_file_exists(self, isolated_config_dir):
        assert load_session("111") is None

    def test_returns_none_for_an_unknown_property(self, isolated_config_dir):
        save_session("111", "session-abc")

        assert load_session("999") is None

    def test_returns_none_when_the_file_is_malformed(self, isolated_config_dir):
        """A corrupt cache must not break an otherwise working command."""
        get_chat_sessions_path().write_text("{not valid json")

        assert load_session("111") is None

    def test_returns_none_when_the_file_is_empty(self, isolated_config_dir):
        get_chat_sessions_path().write_text("")

        assert load_session("111") is None

    def test_returns_none_when_an_entry_is_the_wrong_shape(self, isolated_config_dir):
        get_chat_sessions_path().write_text(json.dumps({"111": "bare-string"}))

        assert load_session("111") is None

    def test_clearing_a_missing_file_is_a_no_op(self, isolated_config_dir):
        clear_session("111")  # must not raise

    def test_saving_recovers_from_a_corrupt_file(self, isolated_config_dir):
        get_chat_sessions_path().write_text("{not valid json")

        save_session("111", "session-abc")

        assert load_session("111") == "session-abc"


class TestSessionFilePermissions:
    def test_file_is_created_with_owner_only_permissions(self, isolated_config_dir):
        import platform

        save_session("111", "session-abc")

        if platform.system() != "Windows":
            mode = get_chat_sessions_path().stat().st_mode & 0o777
            assert mode == 0o600
