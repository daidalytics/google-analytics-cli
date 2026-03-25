#!/usr/bin/env bash
set -euo pipefail

PACKAGE="ga-cli"

echo "Installing ${PACKAGE}..."

# 1. Detect platform
OS="$(uname -s)"
case "${OS}" in
    Linux|Darwin) ;;
    *)
        echo "Error: Unsupported platform '${OS}'. Only Linux and macOS are supported." >&2
        exit 1
        ;;
esac

# 2. Find installer and install
if command -v pipx &>/dev/null; then
    echo "Using pipx..."
    pipx install "${PACKAGE}"
elif command -v uv &>/dev/null; then
    echo "Using uv..."
    uv tool install "${PACKAGE}"
elif command -v pip &>/dev/null; then
    echo "Using pip..."
    pip install "${PACKAGE}"
elif command -v pip3 &>/dev/null; then
    echo "Using pip3..."
    pip3 install "${PACKAGE}"
else
    echo "Error: No package installer found. Install pipx, uv, or pip first." >&2
    echo "  pipx: https://pypa.github.io/pipx/" >&2
    echo "  uv:   https://docs.astral.sh/uv/" >&2
    echo "  pip:  https://pip.pypa.io/" >&2
    exit 1
fi

# 3. Verify installation
if command -v ga &>/dev/null; then
    echo ""
    echo "Successfully installed $(ga --version)"
    echo ""
    echo "Get started:"
    echo "  ga auth login        # Authenticate with Google"
    echo "  ga accounts list     # List your GA4 accounts"
    echo "  ga --help            # See all commands"
else
    echo ""
    echo "Warning: 'ga' command not found in PATH." >&2
    echo "You may need to restart your shell or add the install location to PATH." >&2
    exit 1
fi
