#!/usr/bin/env bash
# Scan Python dependencies for known vulnerabilities.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -d ".venv" ]; then
  PIP=".venv/bin/pip"
  AUDIT=".venv/bin/pip-audit"
elif [ -d "venv" ]; then
  PIP="venv/bin/pip"
  AUDIT="venv/bin/pip-audit"
else
  PIP="pip"
  AUDIT="pip-audit"
fi

if ! command -v "$AUDIT" >/dev/null 2>&1; then
  "$PIP" install pip-audit
  AUDIT="$PIP -m pip_audit"
fi

echo "Running pip-audit on requirements.txt..."
if [ "$AUDIT" = "$PIP -m pip_audit" ]; then
  $AUDIT -r requirements.txt
else
  "$AUDIT" -r requirements.txt
fi
