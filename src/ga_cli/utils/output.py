"""Output formatting utilities.

Supports three formats:
- json: Machine-readable JSON (default when piping)
- table: Human-readable Rich tables (default for TTY)
- compact: Minimal ID + name output

Equivalent to GTM CLI's utils/output.ts.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

OutputFormat = str  # "json" | "table" | "compact"

# Global flags set from main.py callback
_quiet = False


def set_quiet(value: bool) -> None:
    """Enable or disable quiet mode (suppresses info/warn/success)."""
    global _quiet
    _quiet = value


def set_no_color(value: bool) -> None:
    """Enable or disable no-color mode on both consoles."""
    global console, err_console
    if value:
        console = Console(no_color=True, highlight=False)
        err_console = Console(stderr=True, no_color=True, highlight=False)


def is_tty() -> bool:
    """Check if stdout is a terminal."""
    return sys.stdout.isatty()


def get_output_format(requested: Optional[str] = None) -> str:
    """Get effective output format. Defaults to JSON when piping."""
    if requested:
        return requested
    return "table" if is_tty() else "json"


def output(
    data: Any,
    fmt: str = "table",
    columns: Optional[list[str]] = None,
    headers: Optional[list[str]] = None,
) -> None:
    """Output data in the specified format.

    Args:
        data: The data to display (list of dicts, or a single dict).
        fmt: Output format — "json", "table", or "compact".
        columns: Which keys to show in table mode.
        headers: Column headers for table mode.
    """
    effective_fmt = get_output_format(fmt)

    if effective_fmt == "json":
        print(json.dumps(data, indent=2, default=str))

    elif effective_fmt == "compact":
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = item.get("name", item.get("displayName", ""))
                    display = item.get("displayName", "")
                    print(f"{name}\t{display}")
                else:
                    print(str(item))
        else:
            print(json.dumps(data, default=str))

    else:  # table
        if isinstance(data, list) and len(data) > 0:
            _output_table(data, columns, headers)
        elif isinstance(data, dict):
            _output_object(data)
        elif isinstance(data, list) and len(data) == 0:
            console.print("No results found.")
        else:
            print(str(data))


def _output_table(
    data: list[dict],
    columns: Optional[list[str]] = None,
    headers: Optional[list[str]] = None,
) -> None:
    """Render a list of dicts as a Rich table."""
    if not data:
        console.print("No results found.")
        return

    cols = columns or _get_default_columns(data[0])
    hdrs = headers or [_format_header(c) for c in cols]

    table = Table(show_lines=True)
    for h in hdrs:
        table.add_column(h, style="bold")

    for item in data:
        row = [_format_value(item.get(c)) for c in cols]
        table.add_row(*row)

    console.print(table)


def _output_object(data: dict) -> None:
    """Render a single dict as key-value pairs."""
    table = Table(show_lines=True)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key, value in data.items():
        if value is not None:
            table.add_row(_format_header(key), _format_value(value))

    console.print(table)


def _get_default_columns(item: dict) -> list[str]:
    """Pick sensible default columns for GA resources."""
    priority = ["name", "displayName", "type", "createTime", "updateTime"]
    return [c for c in priority if c in item] or list(item.keys())[:5]


def _format_header(key: str) -> str:
    """Convert snake_case or camelCase to Title Case."""
    import re
    # camelCase → spaces
    s = re.sub(r"([A-Z])", r" \1", key)
    # snake_case → spaces
    s = s.replace("_", " ")
    return s.strip().title()


def _format_value(value: Any) -> str:
    """Format a value for table display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "[green]Yes[/green]" if value else "[red]No[/red]"
    if isinstance(value, list):
        return f"[{len(value)} items]" if value else "[]"
    if isinstance(value, dict):
        return json.dumps(value, default=str)
    return str(value)


# Convenience functions for styled messages (equivalent to GTM CLI)
def success(message: str) -> None:
    if not _quiet:
        err_console.print(f"[green]OK[/green] {message}")


def error(message: str) -> None:
    # Errors are NEVER suppressed, even in quiet mode
    err_console.print(f"[red]Error:[/red] {message}")


def warn(message: str) -> None:
    if not _quiet:
        err_console.print(f"[yellow]Warning:[/yellow] {message}")


def info(message: str) -> None:
    if not _quiet:
        err_console.print(f"[blue]Info:[/blue] {message}")
