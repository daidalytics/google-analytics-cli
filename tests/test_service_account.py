"""Tests for ga_cli.auth.service_account."""

import json

import pytest

from ga_cli.auth.service_account import (
    clear_auth_method,
    load_auth_method,
    validate_service_account_key,
)


def _write_key_file(tmp_path, data: dict, filename: str = "sa-key.json") -> str:
    """Write a service account key file and return the path."""
    path = tmp_path / filename
    path.write_text(json.dumps(data))
    return str(path)


VALID_KEY_DATA = {
    "type": "service_account",
    "project_id": "test-project",
    "private_key_id": "key123",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
    "client_email": "test@test-project.iam.gserviceaccount.com",
    "client_id": "123456789",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}


class TestValidateServiceAccountKey:
    def test_valid_key(self, tmp_path):
        path = _write_key_file(tmp_path, VALID_KEY_DATA)
        result = validate_service_account_key(path)
        assert result["type"] == "service_account"
        assert result["client_email"] == "test@test-project.iam.gserviceaccount.com"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            validate_service_account_key("/nonexistent/path.json")

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json{{{")
        with pytest.raises(ValueError, match="Invalid JSON"):
            validate_service_account_key(str(path))

    def test_wrong_type(self, tmp_path):
        data = {**VALID_KEY_DATA, "type": "authorized_user"}
        path = _write_key_file(tmp_path, data)
        with pytest.raises(ValueError, match="expected type 'service_account'"):
            validate_service_account_key(path)

    def test_missing_private_key(self, tmp_path):
        data = {k: v for k, v in VALID_KEY_DATA.items() if k != "private_key"}
        path = _write_key_file(tmp_path, data)
        with pytest.raises(ValueError, match="private_key"):
            validate_service_account_key(path)

    def test_missing_client_email(self, tmp_path):
        data = {k: v for k, v in VALID_KEY_DATA.items() if k != "client_email"}
        path = _write_key_file(tmp_path, data)
        with pytest.raises(ValueError, match="client_email"):
            validate_service_account_key(path)

    def test_missing_both_fields(self, tmp_path):
        data = {
            k: v
            for k, v in VALID_KEY_DATA.items()
            if k not in ("private_key", "client_email")
        }
        path = _write_key_file(tmp_path, data)
        with pytest.raises(ValueError, match="private_key.*client_email"):
            validate_service_account_key(path)


class TestAuthMethodPersistence:
    def test_no_auth_method_initially(self, isolated_config_dir):
        assert load_auth_method() is None

    def test_clear_auth_method_noop(self, isolated_config_dir):
        # Should not raise when no file exists
        clear_auth_method()
        assert load_auth_method() is None
