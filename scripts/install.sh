#!/usr/bin/env bash
# Install the harness CLI from the GitHub release, the way a stranger would.
# Usage: install.sh [TAG]   (default: latest)
set -euo pipefail

REPO="BoozeLee/harness"
TAG="${1:-latest}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

gh release download "$TAG" --repo "$REPO" --pattern 'harness_agent-*.whl' --dir "$TMP"

if command -v uv >/dev/null 2>&1; then
  uv tool install --reinstall "$TMP"/harness_agent-*.whl
  harness --version
else
  VENV="${HOME}/.local/share/harness-venv"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q "$TMP"/harness_agent-*.whl
  "$VENV/bin/harness" --version
  echo "installed at $VENV/bin/harness (add it to PATH)"
fi
