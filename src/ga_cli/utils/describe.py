"""Schema introspection for --describe flag.

Auto-extracts command schemas from Typer/Click internals.
No manual registration needed — parameters, types, flags, and
metadata (mutative, dry-run, json-input) are all derived from
the live command definitions.

Commands, parameters and types are matched by duck typing rather than
isinstance() against the `click` package: Typer >= 0.26 vendors its own copy
of Click, whose classes are unrelated to the standalone package's.
"""

import json
import sys
from typing import Any

import typer

# Keyed by class name: stable across standalone and vendored Click, whereas
# ParamType.name is not ("integer" vs "int").
_JSON_TYPES = {
    "IntParamType": "integer",
    "IntRange": "integer",
    "FloatParamType": "number",
    "FloatRange": "number",
    "BoolParamType": "boolean",
}


def _click_type_to_json(param_type: Any) -> str:
    """Map a Click parameter type to a JSON Schema type string."""
    return _JSON_TYPES.get(type(param_type).__name__, "string")


def _is_group(cmd: Any) -> bool:
    """True for Click groups (commands that contain sub-commands)."""
    return hasattr(cmd, "list_commands") and hasattr(cmd, "get_command")


# Parameters to exclude from schema output (meta/infrastructure flags).
_EXCLUDED_PARAMS = frozenset({
    "help", "version", "quiet", "no_color", "describe",
    "dry_run", "json_input",
})


def _param_to_schema(param: Any) -> tuple[str, dict] | None:
    """Convert a Click parameter to a (name, JSON Schema property) pair.

    Returns None for parameters that should be excluded from output.
    """
    if getattr(param, "param_type_name", None) != "option":
        return None
    if param.name in _EXCLUDED_PARAMS:
        return None

    prop: dict = {
        "type": _click_type_to_json(param.type),
        "description": param.help or "",
    }

    long_flags = [o for o in param.opts if o.startswith("--")]
    short_flags = [o for o in param.opts if o.startswith("-") and not o.startswith("--")]
    if long_flags:
        prop["flag"] = long_flags[0]
    if short_flags:
        prop["aliases"] = short_flags

    choices = getattr(param.type, "choices", None)
    if choices:
        prop["enum"] = list(choices)

    if param.default is not None and not param.required:
        prop["default"] = param.default

    return param.name, prop


def _introspect_command(cmd: Any, prefix: str) -> dict:
    """Build a JSON-Schema-like descriptor for a single Click command."""
    full_name = f"{prefix} {cmd.name}" if prefix else cmd.name

    properties: dict = {}
    required: list[str] = []
    has_dry_run = False
    has_json_input = False

    for param in cmd.params:
        if param.name == "dry_run":
            has_dry_run = True
        if param.name == "json_input":
            has_json_input = True

        result = _param_to_schema(param)
        if result is None:
            continue
        name, prop = result
        properties[name] = prop
        if param.required:
            required.append(name)

    schema: dict = {
        "command": full_name,
        "description": cmd.help or "",
        "parameters": {
            "type": "object",
            "properties": properties,
        },
        "mutative": has_dry_run,
        "supports_dry_run": has_dry_run,
        "supports_json_input": has_json_input,
    }
    if required:
        schema["parameters"]["required"] = required

    return schema


def _introspect_group(group: Any, prefix: str) -> list[dict]:
    """Recursively introspect a Click group and all its sub-commands."""
    commands: list[dict] = []
    for name in sorted(group.list_commands(None)):  # type: ignore[arg-type]
        cmd = group.get_command(None, name)  # type: ignore[arg-type]
        if cmd is None:
            continue
        full_prefix = f"{prefix} {name}" if prefix else name
        if _is_group(cmd):
            commands.extend(_introspect_group(cmd, full_prefix))
        else:
            commands.append(_introspect_command(cmd, prefix))
    return commands


def build_cli_schema(typer_app: typer.Typer) -> dict:
    """Build the schema for all CLI commands without printing anything.

    Returns exactly the dict that ``ga --describe`` prints, so dev tooling
    (e.g. the skill reference generator) can use it in-process.
    """
    click_group = typer.main.get_group(typer_app)
    schemas = _introspect_group(click_group, "ga")
    return {
        "cli": "ga-cli",
        "commands": {s["command"]: s for s in schemas},
    }


def handle_describe_all(typer_app: typer.Typer) -> None:
    """Output schemas for all CLI commands as JSON and exit."""
    print(json.dumps(build_cli_schema(typer_app), indent=2), file=sys.stdout)
    raise typer.Exit(0)
