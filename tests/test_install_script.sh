#!/usr/bin/env bash
# Smoke tests for install.sh
set -euo pipefail

SCRIPT="$(dirname "$0")/../install.sh"
PASS=0
FAIL=0

assert() {
    local name="$1"
    shift
    if "$@" &>/dev/null; then
        echo "  PASS: ${name}"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: ${name}"
        FAIL=$((FAIL + 1))
    fi
}

echo "Running install.sh smoke tests..."
echo ""

assert "script is valid bash" bash -n "${SCRIPT}"
assert "script has set -euo pipefail" grep -q "set -euo pipefail" "${SCRIPT}"
assert "script detects platform" grep -q "uname" "${SCRIPT}"
assert "script checks pipx" grep -q "pipx" "${SCRIPT}"
assert "script checks uv" grep -q "uv" "${SCRIPT}"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"

if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi
