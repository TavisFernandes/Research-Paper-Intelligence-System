#!/usr/bin/env bash
# Start the API (http://localhost:8000, docs at /docs). Loads ../.env when present.
set -euo pipefail
cd "$(dirname "$0")/../backend"
[ -f .venv/bin/activate ] && source .venv/bin/activate
set -a; [ -f ../.env ] && source ../.env; set +a
exec uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" ${RELOAD:+--reload}
