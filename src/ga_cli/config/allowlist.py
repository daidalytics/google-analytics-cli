"""Account/property allowlist: configuration and resolution.

The allowlist comes from up to two sources: the ``allowed_account_ids`` /
``allowed_property_ids`` keys in config.json, and the ``GA_CLI_ALLOWED_ACCOUNTS`` /
``GA_CLI_ALLOWED_PROPERTIES`` env vars. A request must be allowed by every configured
source, so env can narrow the file allowlist but never widen it. With no source
configured the guard is off.

This is a client-side guardrail, not a security boundary.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Union

from ..utils.errors import AllowlistError

ENV_ACCOUNTS = "GA_CLI_ALLOWED_ACCOUNTS"
ENV_PROPERTIES = "GA_CLI_ALLOWED_PROPERTIES"

_PREFIX = {"accounts": "accounts/", "properties": "properties/"}
_DIGITS = re.compile(r"^[0-9]+$")


def parse_ids(value: Union[str, Iterable[str]], kind: str, origin: str) -> frozenset[str]:
    """Parse a comma-separated string or a list into bare numeric IDs.

    ``kind`` is "accounts" or "properties"; the matching ``accounts/`` or ``properties/``
    prefix is stripped. Blank entries are ignored. Anything else that isn't numeric
    raises AllowlistError naming ``origin``.
    """
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
    else:
        raise AllowlistError(origin, f"Invalid {kind} list in {origin}: expected a list of IDs")
    ids = set()
    for raw in items:
        if not isinstance(raw, str):
            raise AllowlistError(origin, f"Invalid {kind} entry {raw!r} in {origin}")
        entry = raw.strip()
        if not entry:
            continue
        prefix = _PREFIX[kind]
        if entry.startswith(prefix):
            entry = entry[len(prefix):]
        if not _DIGITS.match(entry):
            raise AllowlistError(
                origin,
                f"Invalid {kind} ID {raw.strip()!r} in {origin}: expected a numeric ID",
            )
        ids.add(entry)
    return frozenset(ids)


@dataclass(frozen=True)
class AllowlistSource:
    name: str  # "config" | "env"
    accounts: Optional[frozenset[str]]  # None = key not set
    properties: Optional[frozenset[str]]

    def summary(self) -> str:
        """``accounts 1, 2; properties (none)``: the keys that are set, IDs in numeric order."""
        parts = []
        for kind, ids in (("accounts", self.accounts), ("properties", self.properties)):
            if ids is not None:
                parts.append(f"{kind} {', '.join(sorted(ids, key=int)) or '(none)'}")
        return "; ".join(parts)

    def describe(self) -> str:
        return f"{self.name}: {self.summary()}"


@dataclass(frozen=True)
class Allowlist:
    sources: tuple[AllowlistSource, ...] = ()  # empty → guard off

    @property
    def enabled(self) -> bool:
        return bool(self.sources)

    def describe(self) -> str:
        return " | ".join(s.describe() for s in self.sources)

    def listed_properties(self) -> frozenset[str]:
        """Every property ID that some source names directly."""
        return frozenset().union(*(s.properties or () for s in self.sources))

    def lists_property(self, pid: str) -> bool:
        """True if every source names ``pid`` directly (no account lookup needed)."""
        return all(s.properties is not None and pid in s.properties for s in self.sources)

    def allows_account(self, aid: str) -> bool:
        """Account-level calls need the account in every source's ``accounts``."""
        return all(s.accounts is not None and aid in s.accounts for s in self.sources)

    def allows_property(self, pid: str, account_of: Callable[[], Optional[str]]) -> bool:
        """A property is allowed if each source lists it or lists its account.

        ``account_of`` is only called when some source doesn't list ``pid`` directly.
        """
        resolved = False
        account: Optional[str] = None
        for s in self.sources:
            if s.properties is not None and pid in s.properties:
                continue
            if not s.accounts:
                return False
            if not resolved:
                account = account_of()
                resolved = True
            if account is None or account not in s.accounts:
                return False
        return True

    def allowed_accounts(self) -> Optional[frozenset[str]]:
        """Accounts with an account-level allow, or None when the guard is off."""
        if not self.sources:
            return None
        result: Optional[frozenset[str]] = None
        for s in self.sources:
            accounts = s.accounts or frozenset()
            result = accounts if result is None else result & accounts
        return result

    def visible_accounts(self, prop_map: dict[str, str]) -> set[str]:
        """Accounts with an account-level allow or at least one allowed property.

        ``prop_map`` maps property ID → account ID for everything the credentials see.
        """
        visible = set(self.allowed_accounts() or ())
        for pid, aid in prop_map.items():
            if aid not in visible and self.allows_property(pid, lambda a=aid: a):
                visible.add(aid)
        return visible


def _source(
    name: str,
    accounts: object,
    properties: object,
    origins: tuple[str, str],
) -> Optional[AllowlistSource]:
    if accounts is None and properties is None:
        return None
    return AllowlistSource(
        name=name,
        accounts=None if accounts is None else parse_ids(accounts, "accounts", origins[0]),
        properties=(
            None if properties is None else parse_ids(properties, "properties", origins[1])
        ),
    )


def load_allowlist() -> Allowlist:
    """Build the effective allowlist from config.json and the environment.

    Raises AllowlistError if any configured entry is malformed, or if config.json
    can't be read: it may hold an allowlist, so the guard fails closed.
    """
    from .store import config_error, load_config

    config = load_config()
    reason = config_error()
    if reason:
        raise AllowlistError("config.json", f"{reason}, so the allowlist can't be checked")
    sources = [
        _source(
            "config",
            config.allowed_account_ids,
            config.allowed_property_ids,
            ("config key allowed_account_ids", "config key allowed_property_ids"),
        ),
        _source(
            "env",
            os.environ.get(ENV_ACCOUNTS),
            os.environ.get(ENV_PROPERTIES),
            (ENV_ACCOUNTS, ENV_PROPERTIES),
        ),
    ]
    return Allowlist(tuple(s for s in sources if s is not None))


def is_allowlist_configured() -> bool:
    """Whether any allowlist source is set, without validating it (no network).

    An unreadable config.json counts as set, since load_allowlist() denies on it.
    """
    from .store import config_error, load_config

    config = load_config()
    return (
        config_error() is not None
        or config.allowed_account_ids is not None
        or config.allowed_property_ids is not None
        or ENV_ACCOUNTS in os.environ
        or ENV_PROPERTIES in os.environ
    )
