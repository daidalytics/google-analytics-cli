"""GA CLI — Command-line interface for Google Analytics 4."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("google-analytics-cli")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
