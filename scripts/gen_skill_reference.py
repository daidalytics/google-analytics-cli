#!/usr/bin/env python3
"""Generate the command listing in the agent skill's reference from the CLI schema.

Hand-written command references drift and get flags wrong (an early draft of
the skill shipped a non-existent `ga property-settings get`). This renders the
per-group listing in skills/ga-cli/references/commands.md from the CLI's own
schema, built in-process via build_cli_schema() so it reflects the checked-out
code rather than whatever `ga` is on PATH.

Only the span between the BEGIN/END GENERATED markers is rewritten; the
hand-written sections around it are left alone.

Usage:
    uv run python scripts/gen_skill_reference.py           # Print the generated block
    uv run python scripts/gen_skill_reference.py --write   # Rewrite the span between markers
    uv run python scripts/gen_skill_reference.py --check   # Exit 1 if the committed block is stale
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_MD = REPO_ROOT / "skills" / "ga-cli" / "references" / "commands.md"

BEGIN_MARKER = "<!-- BEGIN GENERATED: ga --describe -->"
END_MARKER = "<!-- END GENERATED -->"
WRITE_COMMAND = "uv run python scripts/gen_skill_reference.py --write"

# Identity flags are surfaced even when the CLI treats them as optional: they
# fall back to config defaults, which is exactly what trips agents up.
IDENTITY_PARAMS = ("account_id", "property_id", "stream_id")
# Optional params not worth listing under "opts:" (-o is on every read command).
HIDDEN_OPTIONAL_PARAMS = frozenset({"output_format", "yes", *IDENTITY_PARAMS})
MAX_OPTS_SHOWN = 10


class MarkerError(ValueError):
    """The target document doesn't contain exactly one well-ordered marker pair."""


def build_schema() -> dict:
    """Build the `ga --describe` schema from the checked-out code."""
    from ga_cli.main import app
    from ga_cli.utils.describe import build_cli_schema

    return build_cli_schema(app)


def _short_flag(prop: dict) -> str:
    """Prefer a parameter's short alias, falling back to its long flag."""
    return (prop.get("aliases") or [prop.get("flag")])[0]


def render(schema: dict) -> str:
    """Render the per-group command listing as Markdown (ends with one newline)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for full_name, spec in schema["commands"].items():
        parts = full_name.split()
        props = spec["parameters"].get("properties", {})
        required = set(spec["parameters"].get("required", []))
        groups[parts[1]].append({
            "name": full_name,
            "req": [_short_flag(props[n]) for n in props if n in required],
            "ident": [
                _short_flag(props[n])
                for n in IDENTITY_PARAMS
                if n in props and n not in required
            ],
            "opt": [
                _short_flag(props[n])
                for n in props
                if n not in required and n not in HIDDEN_OPTIONAL_PARAMS
            ],
            "mutative": spec.get("mutative", False),
            "dry_run": spec.get("supports_dry_run", False),
        })

    sections = []
    for group in sorted(groups):
        lines = [f"### ga {group}", ""]
        for cmd in sorted(groups[group], key=lambda c: c["name"]):
            sig = [f"`{cmd['name']}`"]
            sig.extend(f"{flag} X" for flag in cmd["req"])
            if cmd["ident"]:
                sig.append("[" + " | ".join(cmd["ident"]) + "]")
            marks = []
            if cmd["mutative"]:
                marks.append("MUTATES")
            if cmd["dry_run"]:
                marks.append("--dry-run")
            suffix = f"  _{', '.join(marks)}_" if marks else ""
            lines.append(f"- {' '.join(sig)}{suffix}")
            if cmd["opt"]:
                shown = ", ".join(cmd["opt"][:MAX_OPTS_SHOWN])
                more = ", …" if len(cmd["opt"]) > MAX_OPTS_SHOWN else ""
                lines.append(f"  - opts: {shown}{more}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def _marker_span(document: str) -> tuple[int, int]:
    """Return the (start, end) offsets of the text between the markers."""
    if document.count(BEGIN_MARKER) != 1 or document.count(END_MARKER) != 1:
        raise MarkerError(
            f"expected exactly one {BEGIN_MARKER!r} and one {END_MARKER!r} marker"
        )
    start = document.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end = document.index(END_MARKER)
    if end < start:
        raise MarkerError(f"{END_MARKER!r} comes before {BEGIN_MARKER!r}")
    return start, end


def extract_block(document: str) -> str:
    """Return the generated block currently between the markers."""
    start, end = _marker_span(document)
    return document[start:end].strip("\n") + "\n"


def splice(document: str, block: str) -> str:
    """Replace the text between the markers with block, framed by blank lines."""
    start, end = _marker_span(document)
    return f"{document[:start]}\n\n{block}\n{document[end:]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Rewrite the generated span in place")
    mode.add_argument("--check", action="store_true", help="Exit 1 if the generated span is stale")
    parser.add_argument(
        "--path", type=Path, default=COMMANDS_MD, help="Markdown file holding the markers"
    )
    args = parser.parse_args(argv)

    block = render(build_schema())
    if not (args.write or args.check):
        sys.stdout.write(block)
        return 0

    try:
        document = args.path.read_text()
        updated = splice(document, block)
    except (OSError, MarkerError) as e:
        print(f"Error: {args.path}: {e}", file=sys.stderr)
        return 1

    if args.check:
        if updated != document:
            print(
                f"{args.path} is out of date with the CLI.\nRun: {WRITE_COMMAND}",
                file=sys.stderr,
            )
            return 1
        print(f"{args.path} is up to date.")
        return 0

    if updated != document:
        args.path.write_text(updated)
        print(f"Updated {args.path}")
    else:
        print(f"{args.path} already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
