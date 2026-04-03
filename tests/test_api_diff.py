"""Tests for scripts/check_api_changes.py."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the standalone script as a module
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_api_changes.py"
spec = importlib.util.spec_from_file_location("check_api_changes", SCRIPT_PATH)
check_api_changes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_api_changes)


# ---------------------------------------------------------------------------
# Fixtures: minimal Discovery document snippets
# ---------------------------------------------------------------------------

MINIMAL_DOC = {
    "revision": "20260301",
    "resources": {
        "properties": {
            "methods": {
                "get": {
                    "httpMethod": "GET",
                    "parameters": {"name": {"required": True, "type": "string"}},
                },
                "list": {
                    "httpMethod": "GET",
                    "parameters": {"parent": {"required": True, "type": "string"}},
                },
            },
            "resources": {
                "dataStreams": {
                    "methods": {
                        "list": {
                            "httpMethod": "GET",
                            "parameters": {"parent": {"required": True, "type": "string"}},
                        },
                    },
                },
            },
        },
    },
    "schemas": {
        "Property": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "industryCategory": {
                    "type": "string",
                    "enum": ["AUTOMOTIVE", "FINANCE"],
                },
            },
        },
        "DataStream": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string"},
            },
        },
    },
}


def _deep_copy(d: dict) -> dict:
    """JSON round-trip deep copy to avoid mutating fixtures."""
    return json.loads(json.dumps(d))


# ---------------------------------------------------------------------------
# TestFlattenMethods
# ---------------------------------------------------------------------------


class TestFlattenMethods:
    def test_flattens_nested_resources(self):
        result = check_api_changes.flatten_methods(MINIMAL_DOC["resources"])
        assert "properties.get" in result
        assert "properties.list" in result
        assert "properties.dataStreams.list" in result

    def test_empty_resources(self):
        assert check_api_changes.flatten_methods({}) == {}

    def test_resource_without_methods(self):
        resources = {
            "accounts": {"resources": {"users": {"methods": {"list": {"httpMethod": "GET"}}}}}
        }
        result = check_api_changes.flatten_methods(resources)
        assert "accounts.users.list" in result
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestDiffMethods
# ---------------------------------------------------------------------------


class TestDiffMethods:
    def test_detects_added_method(self):
        old = {"properties.get": {"httpMethod": "GET"}}
        new = {**old, "properties.create": {"httpMethod": "POST"}}
        changes = check_api_changes.diff_methods(old, new)
        assert any("Added method `properties.create`" in c for c in changes)

    def test_detects_removed_method(self):
        old = {
            "properties.get": {"httpMethod": "GET"},
            "properties.delete": {"httpMethod": "DELETE"},
        }
        new = {"properties.get": {"httpMethod": "GET"}}
        changes = check_api_changes.diff_methods(old, new)
        assert any("Removed method `properties.delete`" in c for c in changes)

    def test_detects_new_required_parameter(self):
        old = {"m": {"httpMethod": "GET", "parameters": {"a": {"required": True}}}}
        new = {
            "m": {
                "httpMethod": "GET",
                "parameters": {"a": {"required": True}, "b": {"required": True}},
            }
        }
        changes = check_api_changes.diff_methods(old, new)
        assert any("new parameter `b` (required)" in c for c in changes)

    def test_detects_removed_parameter(self):
        old = {"m": {"httpMethod": "GET", "parameters": {"a": {}, "b": {}}}}
        new = {"m": {"httpMethod": "GET", "parameters": {"a": {}}}}
        changes = check_api_changes.diff_methods(old, new)
        assert any("removed parameter `b`" in c for c in changes)

    def test_detects_http_method_change(self):
        old = {"m": {"httpMethod": "GET"}}
        new = {"m": {"httpMethod": "POST"}}
        changes = check_api_changes.diff_methods(old, new)
        assert any("httpMethod changed" in c for c in changes)

    def test_detects_deprecated_method(self):
        old = {"m": {"httpMethod": "GET"}}
        new = {"m": {"httpMethod": "GET", "deprecated": True}}
        changes = check_api_changes.diff_methods(old, new)
        assert any("now deprecated" in c for c in changes)

    def test_no_changes(self):
        methods = {"m": {"httpMethod": "GET", "parameters": {"a": {"required": True}}}}
        assert check_api_changes.diff_methods(methods, _deep_copy(methods)) == []


# ---------------------------------------------------------------------------
# TestDiffSchemas
# ---------------------------------------------------------------------------


class TestDiffSchemas:
    def test_detects_added_schema(self):
        old = {"A": {"type": "object", "properties": {}}}
        new = {**old, "B": {"type": "object", "properties": {}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("Added schema `B`" in c for c in changes)

    def test_detects_removed_schema(self):
        old = {"A": {"type": "object", "properties": {}}, "B": {"type": "object", "properties": {}}}
        new = {"A": {"type": "object", "properties": {}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("Removed schema `B`" in c for c in changes)

    def test_detects_new_property(self):
        old = {"S": {"properties": {"a": {"type": "string"}}}}
        new = {"S": {"properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("new property `b` (integer)" in c for c in changes)

    def test_detects_removed_property(self):
        old = {"S": {"properties": {"a": {"type": "string"}, "b": {"type": "string"}}}}
        new = {"S": {"properties": {"a": {"type": "string"}}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("removed property `b`" in c for c in changes)

    def test_detects_new_enum_value(self):
        old = {"S": {"properties": {"f": {"enum": ["A", "B"]}}}}
        new = {"S": {"properties": {"f": {"enum": ["A", "B", "C"]}}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("new enum value `C` on `f`" in c for c in changes)

    def test_detects_removed_enum_value(self):
        old = {"S": {"properties": {"f": {"enum": ["A", "B"]}}}}
        new = {"S": {"properties": {"f": {"enum": ["A"]}}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("removed enum value `B` from `f`" in c for c in changes)

    def test_detects_type_change(self):
        old = {"S": {"properties": {"f": {"type": "string"}}}}
        new = {"S": {"properties": {"f": {"type": "integer"}}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("type changed" in c for c in changes)

    def test_detects_deprecated_property(self):
        old = {"S": {"properties": {"f": {"type": "string"}}}}
        new = {"S": {"properties": {"f": {"type": "string", "deprecated": True}}}}
        changes = check_api_changes.diff_schemas(old, new)
        assert any("now deprecated" in c for c in changes)

    def test_no_changes(self):
        schemas = {"S": {"properties": {"f": {"type": "string", "enum": ["A"]}}}}
        assert check_api_changes.diff_schemas(schemas, _deep_copy(schemas)) == []


# ---------------------------------------------------------------------------
# TestDiffDocument
# ---------------------------------------------------------------------------


class TestDiffDocument:
    def test_detects_revision_change(self):
        old = {"revision": "20260301", "resources": {}, "schemas": {}}
        new = {"revision": "20260401", "resources": {}, "schemas": {}}
        changes = check_api_changes.diff_document(old, new)
        assert any("Revision changed" in c for c in changes)

    def test_combines_method_and_schema_changes(self):
        old = _deep_copy(MINIMAL_DOC)
        new = _deep_copy(MINIMAL_DOC)
        new["resources"]["properties"]["methods"]["create"] = {"httpMethod": "POST"}
        new["schemas"]["NewSchema"] = {"type": "object", "properties": {}}
        changes = check_api_changes.diff_document(old, new)
        assert any("Added method" in c for c in changes)
        assert any("Added schema" in c for c in changes)

    def test_no_changes_returns_empty(self):
        doc = _deep_copy(MINIMAL_DOC)
        assert check_api_changes.diff_document(doc, _deep_copy(doc)) == []


# ---------------------------------------------------------------------------
# TestFormatMarkdown
# ---------------------------------------------------------------------------


class TestFormatMarkdown:
    def test_formats_changes_with_headers(self):
        all_changes = {
            "analyticsadmin_v1beta": ["Added method `foo` (POST)"],
            "analyticsdata_v1beta": [],
        }
        md = check_api_changes.format_markdown(all_changes)
        assert "### analyticsadmin v1beta" in md
        assert "- Added method `foo` (POST)" in md
        assert "No changes detected." in md

    def test_no_changes_section(self):
        all_changes = {"api_v1": []}
        md = check_api_changes.format_markdown(all_changes)
        assert "No changes detected." in md

    def test_includes_date(self):
        md = check_api_changes.format_markdown({"api": []})
        assert "**Date:**" in md

    def test_includes_update_hint(self):
        md = check_api_changes.format_markdown({"api": []})
        assert "--update" in md


# ---------------------------------------------------------------------------
# TestFetchDiscovery
# ---------------------------------------------------------------------------


class TestFetchDiscovery:
    def test_successful_fetch(self):
        mock_data = json.dumps({"revision": "123"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(check_api_changes, "urlopen", return_value=mock_resp):
            result = check_api_changes.fetch_discovery("https://example.com")
        assert result == {"revision": "123"}

    def test_http_error_raises(self):
        from urllib.error import URLError

        with patch.object(check_api_changes, "urlopen", side_effect=URLError("timeout")):
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                check_api_changes.fetch_discovery("https://example.com")


# ---------------------------------------------------------------------------
# TestSetGithubOutput
# ---------------------------------------------------------------------------


class TestSetGithubOutput:
    def test_writes_simple_value(self, tmp_path):
        output_file = tmp_path / "github_output"
        output_file.touch()
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            check_api_changes.set_github_output("has_changes", "true")
        content = output_file.read_text()
        assert "has_changes=true" in content

    def test_writes_multiline_value(self, tmp_path):
        output_file = tmp_path / "github_output"
        output_file.touch()
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            check_api_changes.set_github_output("body", "line1\nline2")
        content = output_file.read_text()
        assert "line1\nline2" in content
        assert "body<<" in content

    def test_noop_without_env_var(self):
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise
            check_api_changes.set_github_output("key", "value")


# ---------------------------------------------------------------------------
# TestMainIntegration
# ---------------------------------------------------------------------------


class TestMainIntegration:
    def test_check_mode_with_changes(self, tmp_path, capsys):
        old_doc = _deep_copy(MINIMAL_DOC)
        new_doc = _deep_copy(MINIMAL_DOC)
        new_doc["resources"]["properties"]["methods"]["create"] = {"httpMethod": "POST"}

        # Write snapshot for one API, mock fetching
        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()

        # Write all 4 snapshots (same old_doc)
        for api_name in check_api_changes.DISCOVERY_URLS:
            (snapshot_dir / f"{api_name}.json").write_text(json.dumps(old_doc))

        def mock_fetch(url):
            return _deep_copy(new_doc)

        with patch.object(check_api_changes, "fetch_discovery", side_effect=mock_fetch):
            check_api_changes.main(["--snapshot-dir", str(snapshot_dir)])

        out = capsys.readouterr().out
        assert "Added method" in out

    def test_check_mode_no_changes(self, tmp_path, capsys):
        doc = _deep_copy(MINIMAL_DOC)
        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()

        for api_name in check_api_changes.DISCOVERY_URLS:
            (snapshot_dir / f"{api_name}.json").write_text(json.dumps(doc))

        with patch.object(check_api_changes, "fetch_discovery", return_value=_deep_copy(doc)):
            check_api_changes.main(["--snapshot-dir", str(snapshot_dir)])

        out = capsys.readouterr().out
        assert "No changes detected." in out

    def test_update_mode(self, tmp_path):
        snapshot_dir = tmp_path / "snapshots"

        doc = {"revision": "123", "resources": {}, "schemas": {}}
        with patch.object(check_api_changes, "fetch_discovery", return_value=doc):
            check_api_changes.main(["--update", "--snapshot-dir", str(snapshot_dir)])

        for api_name in check_api_changes.DISCOVERY_URLS:
            path = snapshot_dir / f"{api_name}.json"
            assert path.exists()
            assert json.loads(path.read_text())["revision"] == "123"

    def test_missing_snapshot_warns(self, tmp_path, capsys):
        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()

        with patch.object(check_api_changes, "fetch_discovery"):
            check_api_changes.main(["--snapshot-dir", str(snapshot_dir)])

        out = capsys.readouterr().out
        assert "--update" in out
