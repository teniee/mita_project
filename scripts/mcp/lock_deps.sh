#!/usr/bin/env bash
# Regenerate requirements-mcp.lock from requirements-mcp.txt in a clean venv.
set -euo pipefail
cd "$(dirname "$0")/../.."
tmp="$(mktemp -d)"
python3 -m venv "$tmp/venv"
"$tmp/venv/bin/pip" install -q --upgrade pip
"$tmp/venv/bin/pip" install -q -r requirements-mcp.txt
{
  echo "# Full, exact dependency lock for the MCP image (generated from requirements-mcp.txt"
  echo "# in a clean virtualenv on $(date -u +%Y-%m-%d); regenerate with scripts/mcp/lock_deps.sh)."
  "$tmp/venv/bin/pip" freeze --all | grep -v -E "^(pip|setuptools|wheel)=="
} > requirements-mcp.lock
rm -rf "$tmp"
echo "requirements-mcp.lock updated"
