"""GA CLI entry point."""

import typer

from .commands.access_reports import access_reports_app
from .commands.account_summaries import account_summaries_app
from .commands.accounts import accounts_app
from .commands.agent_cmd import agent_app
from .commands.annotations import annotations_app
from .commands.auth_cmd import auth_app
from .commands.completions_cmd import completions_app
from .commands.config_cmd import config_app
from .commands.custom_dimensions import custom_dimensions_app
from .commands.custom_metrics import custom_metrics_app
from .commands.data_retention import data_retention_app
from .commands.data_streams import data_streams_app
from .commands.firebase_links import firebase_links_app
from .commands.google_ads_links import google_ads_links_app
from .commands.key_events import key_events_app
from .commands.mp_secrets import mp_secrets_app
from .commands.properties import properties_app
from .commands.reports import reports_app
from .commands.upgrade_cmd import upgrade_app

app = typer.Typer(
    name="ga",
    help="Command-line interface for Google Analytics 4",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")
app.add_typer(accounts_app, name="accounts")
app.add_typer(account_summaries_app, name="account-summaries")
app.add_typer(properties_app, name="properties")
app.add_typer(custom_dimensions_app, name="custom-dimensions")
app.add_typer(custom_metrics_app, name="custom-metrics")
app.add_typer(data_retention_app, name="data-retention")
app.add_typer(data_streams_app, name="data-streams")
app.add_typer(access_reports_app, name="access-reports")
app.add_typer(annotations_app, name="annotations")
app.add_typer(firebase_links_app, name="firebase-links")
app.add_typer(google_ads_links_app, name="google-ads-links")
app.add_typer(key_events_app, name="key-events")
app.add_typer(mp_secrets_app, name="mp-secrets")
app.add_typer(reports_app, name="reports")
app.add_typer(agent_app, name="agent")
app.add_typer(upgrade_app, name="upgrade")
app.add_typer(completions_app, name="completions")


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
):
    """GA CLI — Command-line interface for Google Analytics 4."""
    from .utils.output import set_no_color, set_quiet

    if quiet:
        set_quiet(True)
    if no_color:
        set_no_color(True)

    if version:
        from . import __version__

        print(f"ga-cli {__version__}")
        raise typer.Exit()


def run():
    """Entry point for the CLI (called by pyproject.toml [project.scripts])."""
    from .commands.upgrade_cmd import maybe_check_for_updates

    app()
    maybe_check_for_updates()


if __name__ == "__main__":
    run()
