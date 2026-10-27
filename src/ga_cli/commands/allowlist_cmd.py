"""Allowlist command: show the active account/property allowlist.

The allowlist itself is changed with `ga config set allowed_account_ids …` /
`allowed_property_ids …`, from an interactive terminal only.
"""

from datetime import datetime, timezone
from typing import Optional

import typer

from ..config.allowlist import Allowlist, AllowlistSource, is_allowlist_configured, load_allowlist
from ..config.constants import get_active_profile, is_named_profile, profile_exists
from ..utils import handle_error, info, output, resolve_output_format
from ..utils.errors import ProfileNotFoundError

allowlist_app = typer.Typer(
    name="allowlist",
    help="Show the account/property allowlist",
    no_args_is_help=True,
)


def _source_dict(source: Optional[AllowlistSource]) -> Optional[dict]:
    if source is None:
        return None

    def ids(values):
        return None if values is None else sorted(values, key=int)

    return {"accounts": ids(source.accounts), "properties": ids(source.properties)}


def _effective_properties(allowlist: Allowlist, cache) -> list[dict]:
    """Allowed properties the credentials can see, plus listed ones they can't."""
    props = [
        {"id": pid, "account": aid, "displayName": cache.names.get(pid)}
        for pid, aid in cache.properties.items()
        if allowlist.allows_property(pid, lambda a=aid: a)
    ]
    props += [
        {"id": pid, "account": None, "displayName": None}
        for pid in allowlist.listed_properties()
        if pid not in cache.properties and allowlist.lists_property(pid)
    ]
    return sorted(props, key=lambda p: int(p["id"]))


def build_report(allowlist: Allowlist, cache) -> dict:
    profile = get_active_profile()
    by_name = {s.name: s for s in allowlist.sources}
    # "profile" only in a named profile: the default profile's file is "config"
    sources = {"config": _source_dict(by_name.get("config"))}
    if is_named_profile():
        sources["profile"] = _source_dict(by_name.get(f"profile {profile}"))
    sources["env"] = _source_dict(by_name.get("env"))
    fetched_at = cache.fetched_at or 0
    return {
        "enabled": True,
        "profile": profile,
        "sources": sources,
        "effective": {
            "accounts": sorted(allowlist.allowed_accounts() or (), key=int),
            "properties": _effective_properties(allowlist, cache),
        },
        "cache": {
            "fetched_at": datetime.fromtimestamp(fetched_at, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "age_seconds": max(0, int(datetime.now(timezone.utc).timestamp() - fetched_at)),
        },
    }


def _describe_source(source: Optional[AllowlistSource]) -> str:
    return source.summary() if source else "(not set)"


@allowlist_app.command("show")
def show_cmd(
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Show the active allowlist, its sources and the properties it allows."""
    try:
        effective_format = resolve_output_format(output_format)
        # Like `config get`: a typo in --profile exits 2 instead of reading as the
        # root allowlist alone, or as "off", or exiting 5 on an unreadable root file
        profile = get_active_profile()
        if not profile_exists(profile):
            raise ProfileNotFoundError.for_profile(profile)
        if not is_allowlist_configured():
            output({"enabled": False}, effective_format)
            return

        allowlist = load_allowlist()
        from ..api.client import get_allowlist_cache

        cache = get_allowlist_cache()
        # Loads from disk, or refreshes a stale/missing cache or one that lacks a listed property
        cache.prop_map(allowlist.listed_properties())
        report = build_report(allowlist, cache)

        if effective_format != "table":
            output(report, effective_format)
            return

        accounts = report["effective"]["accounts"]
        sources = {s.name: s for s in allowlist.sources}
        output(
            {
                "Enabled": "yes (a request must pass every source)",
                "Profile": profile,
                "Config file (all profiles)": _describe_source(sources.get("config")),
                # None leaves the row out: the default profile's file is the config file
                "Profile file": (
                    _describe_source(sources.get(f"profile {profile}"))
                    if is_named_profile() else None
                ),
                "Environment": _describe_source(sources.get("env")),
                "Allowed accounts": ", ".join(
                    f"{a} ({cache.account_names[a]})" if cache.account_names.get(a) else a
                    for a in accounts
                ) or "(none: account-level calls are denied)",
                "Cache": f"{report['cache']['fetched_at']} "
                         f"({report['cache']['age_seconds']} s old)",
            },
            effective_format,
        )
        if report["effective"]["properties"]:
            output(
                [
                    {**p, "account": p["account"] or "(not visible)"}
                    for p in report["effective"]["properties"]
                ],
                effective_format,
                columns=["id", "displayName", "account"],
                headers=["Property ID", "Display Name", "Account ID"],
            )
        else:
            info("No allowed properties are visible to these credentials.")
    except Exception as e:
        handle_error(e)
