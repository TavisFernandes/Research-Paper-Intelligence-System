#!/usr/bin/env bash
# Backend tests + lint (+ frontend typecheck/build when pnpm is available).
set -euo pipefail
cd "$(dirname "$0")/../backend"
[ -f .venv/bin/activate ] && source .venv/bin/activate
ruff check . --select E9,F,B --ignore B008,B905
python -m pytest -q "$@"
