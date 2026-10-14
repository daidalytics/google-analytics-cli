"""Application constants and configuration paths.

Paths come in two scopes:

- **Per profile** (``get_profile_dir()``): credentials, config, auth method,
  chat sessions. Identity and target property switch together.
- **Global** (``get_config_dir()``): the OAuth client secret and the
  update-check timestamp, which belong to the installed app, not a client.

The default profile *is* the config root, so installs that predate profiles
keep working with no migration.
"""

import os
import re
import shutil
from pathlib import Path

# App identity
APP_NAME = "ga-cli"

# Scope required by the Analytics Data API chat method (v1alpha).
# Added in 0.3.0 — credentials stored before then will not carry it, so
# commands that need it check with auth.credentials.has_scope() first.
CHAT_SCOPE = "https://www.googleapis.com/auth/analytics.chatbot.read"

# OAuth 2.0 scopes
OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
    "https://www.googleapis.com/auth/analytics.manage.users",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    CHAT_SCOPE,
]

# OAuth callback server
OAUTH_CALLBACK_PORT = 8085

# Track whether we've already attempted the legacy macOS migration this process.
_legacy_migration_attempted = False


def _migrate_legacy_macos_config(new_dir: Path) -> None:
    """Move config from the legacy macOS path to the new XDG-style path.

    Versions <=0.2.1 used ``platformdirs``, which on macOS resolves to
    ``~/Library/Application Support/ga-cli/``. We now standardize on
    ``~/.config/ga-cli/`` across all platforms. If the legacy directory exists
    and the new one doesn't, move it. Runs at most once per process.
    """
    global _legacy_migration_attempted
    if _legacy_migration_attempted:
        return
    _legacy_migration_attempted = True

    legacy_dir = Path.home() / "Library" / "Application Support" / APP_NAME
    if legacy_dir.is_dir() and not new_dir.exists():
        try:
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_dir), str(new_dir))
        except OSError:
            # Migration is best-effort; fall through and let callers create
            # the new directory themselves if needed.
            pass


# Configuration directory
# Priority: GA_CLI_CONFIG_DIR env var > ~/.config/ga-cli/ (all platforms)
def get_config_dir() -> Path:
    """Get the configuration directory path.

    Resolution order:
      1. ``GA_CLI_CONFIG_DIR`` environment variable (used in tests too).
      2. ``~/.config/ga-cli/`` on all platforms.
    """
    env_dir = os.environ.get("GA_CLI_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    config_dir = Path.home() / ".config" / APP_NAME
    _migrate_legacy_macos_config(config_dir)
    return config_dir


# Named profiles
# Selection is per invocation (--profile) or per shell (GA_CLI_PROFILE), never
# persisted. Names are a single safe path component: no ".", "..", "/", or
# hidden names, so a profile can never escape the profiles directory.
DEFAULT_PROFILE = "default"
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

_active_profile: str = DEFAULT_PROFILE


def set_active_profile(name: str | None) -> None:
    """Select the profile for this process. Called from the root callback.

    ``None`` and ``""`` select the default profile.

    Raises:
        ValueError: If ``name`` could escape the profiles directory. The
            active profile is left unchanged.
    """
    global _active_profile
    name = name or DEFAULT_PROFILE
    if not PROFILE_NAME_RE.fullmatch(name):
        raise ValueError(
            f"Invalid profile name {name!r}: use letters, digits, '.', '_' or '-', "
            "starting with a letter or digit."
        )
    _active_profile = name


def get_active_profile() -> str:
    """Name of the profile selected for this process."""
    return _active_profile


def is_named_profile() -> bool:
    """True when a profile other than the default is active."""
    return _active_profile != DEFAULT_PROFILE


def get_profiles_root() -> Path:
    """Directory that holds every named profile's directory."""
    return get_config_dir() / "profiles"


def get_profile_dir() -> Path:
    """Directory holding the active profile's auth and config files.

    The default profile *is* the config root. A named profile lives under
    ``profiles/<name>/`` and is created by the first write into it.
    """
    if _active_profile == DEFAULT_PROFILE:
        return get_config_dir()
    return get_profiles_root() / _active_profile


def profile_exists(name: str) -> bool:
    """Whether ``name`` is a known profile. The default profile always exists.

    Invalid names are never known, so this cannot probe outside the profiles
    directory.
    """
    if name == DEFAULT_PROFILE:
        return True
    if not PROFILE_NAME_RE.fullmatch(name):
        return False
    return (get_profiles_root() / name).is_dir()


def list_profiles() -> list[str]:
    """All known profiles: ``"default"`` first, then named profiles sorted.

    Entries under ``profiles/`` that are not directories or whose names are
    not valid profile names are ignored.
    """
    root = get_profiles_root()
    named: list[str] = []
    if root.is_dir():
        named = [
            entry.name
            for entry in root.iterdir()
            if entry.is_dir()
            and entry.name != DEFAULT_PROFILE
            and PROFILE_NAME_RE.fullmatch(entry.name)
        ]
    return [DEFAULT_PROFILE, *sorted(named)]


# Per-profile paths (resolved through get_profile_dir())


def get_credentials_path() -> Path:
    """Path to the active profile's stored OAuth credentials. Per profile."""
    return get_profile_dir() / "credentials.json"


def get_config_path() -> Path:
    """Path to the active profile's user configuration file. Per profile."""
    return get_profile_dir() / "config.json"


def get_auth_method_path() -> Path:
    """Path to the active profile's auth method tracking file. Per profile."""
    return get_profile_dir() / "auth-method.json"


def get_chat_sessions_path() -> Path:
    """Path to the per-property chat session cache used by --continue. Per profile."""
    return get_profile_dir() / "chat-sessions.json"


# Global paths (resolved through get_config_dir(), shared by all profiles)


def get_client_secret_path() -> Path:
    """Path to the OAuth client secret. Global: one app identity for all profiles."""
    return get_config_dir() / "client_secret.json"


def get_update_check_path() -> Path:
    """Path to the update-check timestamp file. Global: it's about the installed binary."""
    return get_config_dir() / "update-check.json"


# Pagination defaults
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
