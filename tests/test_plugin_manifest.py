"""Tests for packaging metadata: console-script alias and Claude Code plugin manifests."""

import json
import struct
from importlib.metadata import entry_points, version
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / ".claude-plugin"
PLUGIN_JSON = PLUGIN_DIR / "plugin.json"
MARKETPLACE_JSON = PLUGIN_DIR / "marketplace.json"
PLUGIN_ICON = PLUGIN_DIR / "icon.png"

PACKAGE_NAME = "google-analytics-cli"
ENTRY_TARGET = "ga_cli.main:run"


def _load(path: Path) -> dict:
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def plugin() -> dict:
    return _load(PLUGIN_JSON)


@pytest.fixture
def marketplace() -> dict:
    return _load(MARKETPLACE_JSON)


class TestConsoleScripts:
    @pytest.mark.parametrize("name", ["ga", PACKAGE_NAME])
    def test_entry_point_targets_main_run(self, name):
        """Both `ga` and `google-analytics-cli` resolve to ga_cli.main:run."""
        scripts = {ep.name: ep.value for ep in entry_points(group="console_scripts")}

        assert name in scripts, (
            f"console script {name!r} not installed; check [project.scripts] in "
            "pyproject.toml and re-run `uv sync`"
        )
        assert scripts[name] == ENTRY_TARGET


class TestPluginJson:
    def test_name(self, plugin):
        assert plugin["name"] == PACKAGE_NAME

    @pytest.mark.parametrize(
        "field", ["description", "homepage", "repository", "license"]
    )
    def test_string_fields_present(self, plugin, field):
        assert isinstance(plugin.get(field), str)
        assert plugin[field].strip()

    def test_author_name(self, plugin):
        assert isinstance(plugin.get("author"), dict)
        assert plugin["author"].get("name")

    def test_keywords(self, plugin):
        keywords = plugin.get("keywords")
        assert isinstance(keywords, list)
        assert keywords
        assert all(isinstance(k, str) and k for k in keywords)

    def test_version_matches_package(self, plugin):
        """plugin.json version must track the installed package version."""
        package_version = version(PACKAGE_NAME)

        assert plugin.get("version") == package_version, (
            f".claude-plugin/plugin.json version is {plugin.get('version')!r} but "
            f"pyproject.toml version is {package_version!r}. Bump both files together "
            "in the release commit: Claude Code only offers plugin updates when the "
            "plugin.json version changes."
        )


class TestMarketplaceJson:
    def test_name(self, marketplace):
        assert marketplace["name"] == "daidalytics"

    def test_owner_name(self, marketplace):
        assert isinstance(marketplace.get("owner"), dict)
        assert marketplace["owner"].get("name")

    def test_single_plugin_entry(self, marketplace):
        plugins = marketplace.get("plugins")

        assert isinstance(plugins, list)
        assert len(plugins) == 1
        entry = plugins[0]
        assert entry["name"] == PACKAGE_NAME
        assert entry["source"] == "./"
        assert isinstance(entry.get("description"), str)
        assert entry["description"].strip()

    def test_plugin_entry_matches_plugin_json(self, marketplace, plugin):
        """The marketplace entry installs the plugin defined in plugin.json."""
        assert marketplace["plugins"][0]["name"] == plugin["name"]


class TestPluginIcon:
    """The developer portal takes .claude-plugin/icon.png as the listing icon the first
    time the plugin is saved or submitted, and never updates it afterwards. It must be a
    square PNG or JPEG of 512-2048 px per side and under 2 MB (no SVG or WebP)."""

    PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

    def _header(self) -> bytes:
        assert PLUGIN_ICON.is_file(), f"{PLUGIN_ICON.relative_to(REPO_ROOT)} is missing"
        return PLUGIN_ICON.read_bytes()[:24]

    def test_is_png(self):
        header = self._header()
        assert header[:8] == self.PNG_SIGNATURE
        assert header[12:16] == b"IHDR"

    def test_is_square_and_within_size_limits(self):
        width, height = struct.unpack(">II", self._header()[16:24])

        assert width == height, f"icon must be square, got {width}x{height}"
        assert 512 <= width <= 2048, f"icon must be 512-2048 px per side, got {width}"

    def test_under_two_megabytes(self):
        self._header()
        assert PLUGIN_ICON.stat().st_size < 2 * 1024 * 1024
