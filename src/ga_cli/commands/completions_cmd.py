"""Shell completion script generation."""

from __future__ import annotations

import typer
from click.shell_completion import (
    BashComplete,
    FishComplete,
    ZshComplete,
)

completions_app = typer.Typer(
    name="completions", help="Generate shell completion scripts", no_args_is_help=True
)

# The prog_name used by the installed entry point
_PROG_NAME = "ga"


def _get_source_vars() -> dict[str, str]:
    """Build the template vars that Click's completion classes need."""
    func_name = f"_{_PROG_NAME}_completion"
    complete_var = f"_{_PROG_NAME.upper()}_COMPLETE"
    return {
        "complete_func": func_name,
        "complete_var": complete_var,
        "prog_name": _PROG_NAME,
    }


@completions_app.command("bash")
def bash_cmd():
    """Generate bash completion script.

    Usage: ga completions bash > ~/.bash_completion.d/ga
    """
    print(BashComplete.source_template % _get_source_vars())


@completions_app.command("zsh")
def zsh_cmd():
    """Generate zsh completion script.

    Usage: ga completions zsh > ~/.zsh/completions/_ga
    """
    print(ZshComplete.source_template % _get_source_vars())


@completions_app.command("fish")
def fish_cmd():
    """Generate fish completion script.

    Usage: ga completions fish > ~/.config/fish/completions/ga.fish
    """
    print(FishComplete.source_template % _get_source_vars())
