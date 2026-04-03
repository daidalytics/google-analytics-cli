#!/usr/bin/env python3
"""Check GA4 Discovery documents for API changes.

Fetches live Discovery JSON documents for the 4 GA4 APIs, compares them
against stored snapshots, and outputs a structured semantic diff. Designed
to run in GitHub Actions (writes to $GITHUB_OUTPUT) but works locally too.

Usage:
    python scripts/check_api_changes.py            # Check for changes
    python scripts/check_api_changes.py --update    # Update snapshots
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

DISCOVERY_URLS = {
    "analyticsadmin_v1beta": "https://analyticsadmin.googleapis.com/$discovery/rest?version=v1beta",
    "analyticsadmin_v1alpha": "https://analyticsadmin.googleapis.com/$discovery/rest?version=v1alpha",
    "analyticsdata_v1beta": "https://analyticsdata.googleapis.com/$discovery/rest?version=v1beta",
    "analyticsdata_v1alpha": "https://analyticsdata.googleapis.com/$discovery/rest?version=v1alpha",
}

DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / ".api-snapshots"


def fetch_discovery(url: str) -> dict:
    """Fetch a Discovery document from the given URL."""
    try:
        with urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())
    except (URLError, OSError) as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}") from e


def load_snapshot(path: Path) -> dict:
    """Load a snapshot JSON file. Returns empty dict if missing."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_snapshot(path: Path, doc: dict) -> None:
    """Write a Discovery document as a formatted JSON snapshot."""
    path.write_text(json.dumps(doc, indent=2) + "\n")


def flatten_methods(
    resources: dict, prefix: str = ""
) -> dict[str, dict]:
    """Recursively flatten the resources tree into a flat method map.

    Returns e.g. {"properties.dataStreams.list": {method_def}, ...}
    """
    methods = {}
    for resource_name, resource in resources.items():
        resource_path = f"{prefix}{resource_name}" if not prefix else f"{prefix}.{resource_name}"
        for method_name, method_def in resource.get("methods", {}).items():
            methods[f"{resource_path}.{method_name}"] = method_def
        if "resources" in resource:
            methods.update(flatten_methods(resource["resources"], resource_path))
    return methods


def diff_methods(old_methods: dict, new_methods: dict) -> list[str]:
    """Diff two flat method maps. Returns list of change descriptions."""
    changes = []
    old_keys = set(old_methods)
    new_keys = set(new_methods)

    for key in sorted(new_keys - old_keys):
        http = new_methods[key].get("httpMethod", "?")
        changes.append(f"Added method `{key}` ({http})")

    for key in sorted(old_keys - new_keys):
        changes.append(f"Removed method `{key}`")

    for key in sorted(old_keys & new_keys):
        old_m = old_methods[key]
        new_m = new_methods[key]

        if old_m.get("httpMethod") != new_m.get("httpMethod"):
            changes.append(
                f"Method `{key}`: httpMethod changed "
                f"`{old_m.get('httpMethod')}` -> `{new_m.get('httpMethod')}`"
            )

        old_params = old_m.get("parameters", {})
        new_params = new_m.get("parameters", {})
        for p in sorted(set(new_params) - set(old_params)):
            req = " (required)" if new_params[p].get("required") else ""
            changes.append(f"Method `{key}`: new parameter `{p}`{req}")
        for p in sorted(set(old_params) - set(new_params)):
            changes.append(f"Method `{key}`: removed parameter `{p}`")

        if not old_m.get("deprecated") and new_m.get("deprecated"):
            changes.append(f"Method `{key}`: now deprecated")

    return changes


def diff_schemas(old_schemas: dict, new_schemas: dict) -> list[str]:
    """Diff two schema maps. Returns list of change descriptions."""
    changes = []
    old_keys = set(old_schemas)
    new_keys = set(new_schemas)

    for key in sorted(new_keys - old_keys):
        changes.append(f"Added schema `{key}`")

    for key in sorted(old_keys - new_keys):
        changes.append(f"Removed schema `{key}`")

    for key in sorted(old_keys & new_keys):
        old_s = old_schemas[key]
        new_s = new_schemas[key]

        old_props = old_s.get("properties", {})
        new_props = new_s.get("properties", {})

        for p in sorted(set(new_props) - set(old_props)):
            ptype = new_props[p].get("type", new_props[p].get("$ref", "unknown"))
            changes.append(f"Schema `{key}`: new property `{p}` ({ptype})")
        for p in sorted(set(old_props) - set(new_props)):
            changes.append(f"Schema `{key}`: removed property `{p}`")

        for p in sorted(set(old_props) & set(new_props)):
            old_p = old_props[p]
            new_p = new_props[p]

            old_type = old_p.get("type")
            new_type = new_p.get("type")
            if old_type != new_type:
                changes.append(
                    f"Schema `{key}`: property `{p}` type changed "
                    f"`{old_type}` -> `{new_type}`"
                )

            old_enum = set(old_p.get("enum", []))
            new_enum = set(new_p.get("enum", []))
            for v in sorted(new_enum - old_enum):
                changes.append(
                    f"Schema `{key}`: new enum value `{v}` on `{p}`"
                )
            for v in sorted(old_enum - new_enum):
                changes.append(
                    f"Schema `{key}`: removed enum value `{v}` from `{p}`"
                )

            if not old_p.get("deprecated") and new_p.get("deprecated"):
                changes.append(f"Schema `{key}`: property `{p}` now deprecated")

    return changes


def diff_document(old_doc: dict, new_doc: dict) -> list[str]:
    """Produce a semantic diff between two Discovery documents."""
    changes = []

    old_rev = old_doc.get("revision", "unknown")
    new_rev = new_doc.get("revision", "unknown")
    if old_rev != new_rev:
        changes.append(f"Revision changed: `{old_rev}` -> `{new_rev}`")

    old_methods = flatten_methods(old_doc.get("resources", {}))
    new_methods = flatten_methods(new_doc.get("resources", {}))
    changes.extend(diff_methods(old_methods, new_methods))

    changes.extend(diff_schemas(
        old_doc.get("schemas", {}),
        new_doc.get("schemas", {}),
    ))

    return changes


def format_markdown(all_changes: dict[str, list[str]]) -> str:
    """Format all API changes as a markdown document."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "## GA4 API Changes Detected",
        "",
        f"**Date:** {today}",
        "",
    ]

    for api_name, changes in all_changes.items():
        display_name = api_name.replace("_", " ")
        if changes:
            lines.append(f"### {display_name}")
            for change in changes:
                lines.append(f"- {change}")
            lines.append("")
        else:
            lines.append(f"### {display_name}")
            lines.append("No changes detected.")
            lines.append("")

    lines.append("---")
    lines.append("> To update snapshots: `python scripts/check_api_changes.py --update`")
    lines.append("")
    return "\n".join(lines)


def set_github_output(key: str, value: str) -> None:
    """Write a key-value pair to $GITHUB_OUTPUT (no-op outside CI)."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a") as f:
        if "\n" in value:
            delimiter = f"ghadelimiter_{uuid.uuid4()}"
            f.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
        else:
            f.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Fetch and save new snapshots instead of diffing",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help="Directory containing snapshot files",
    )
    args = parser.parse_args(argv)

    snapshot_dir: Path = args.snapshot_dir
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    if args.update:
        for api_name, url in DISCOVERY_URLS.items():
            print(f"Fetching {api_name}...")
            doc = fetch_discovery(url)
            save_snapshot(snapshot_dir / f"{api_name}.json", doc)
            print(f"  Saved {api_name}.json (revision: {doc.get('revision', '?')})")
        print(f"\nUpdated {len(DISCOVERY_URLS)} snapshots in {snapshot_dir}")
        return

    # Check mode (default)
    all_changes: dict[str, list[str]] = {}
    has_any_changes = False

    for api_name, url in DISCOVERY_URLS.items():
        snapshot_path = snapshot_dir / f"{api_name}.json"
        old_doc = load_snapshot(snapshot_path)
        if not old_doc:
            print(f"Warning: No snapshot found for {api_name}, skipping diff", file=sys.stderr)
            all_changes[api_name] = [
                f"No snapshot found at `{snapshot_path.name}` — run with `--update` first"
            ]
            has_any_changes = True
            continue

        print(f"Fetching {api_name}...", file=sys.stderr)
        new_doc = fetch_discovery(url)
        changes = diff_document(old_doc, new_doc)
        all_changes[api_name] = changes
        if changes:
            has_any_changes = True

    markdown = format_markdown(all_changes)
    print(markdown)

    set_github_output("has_changes", str(has_any_changes).lower())
    if has_any_changes:
        set_github_output("issue_body", markdown)


if __name__ == "__main__":
    main()
