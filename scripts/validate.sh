#!/usr/bin/env bash
# Validation gates (Linux/macOS).  scripts/validate.sh [built|source|release] [--browser]
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-built}"; BROWSER="${2:-}"; PORT="${PORT:-8765}"
PY="${PYTHON:-python3}"; [ -x .venv/bin/python ] && PY=.venv/bin/python
fail=0
"$PY" tests/run_unit.py || fail=1
if [ "$BROWSER" = "--browser" ] || [ "$MODE" = "release" ]; then
  "$PY" -m pipeline serve --port "$PORT" >/dev/null 2>&1 & srv=$!
  trap 'kill $srv 2>/dev/null || true' EXIT
  sleep 2
  "$PY" tests/smoke_browser.py "http://127.0.0.1:$PORT/" || fail=1
fi
"$PY" -m pipeline check --mode "$MODE" || fail=1
[ "$fail" = 0 ] && echo "All requested gates passed (mode: $MODE)." || { echo "VALIDATION FAILED"; exit 1; }
