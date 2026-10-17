#!/usr/bin/env bash
# Create a virtualenv and install the backend. Usage: scripts/setup_backend.sh [ml|training|dev]
set -euo pipefail
cd "$(dirname "$0")/../backend"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
case "${1:-core}" in
  ml)       pip install -r requirements-ml.txt ;;
  training) pip install -r requirements-training.txt ;;
  dev)      pip install -r requirements-dev.txt ;;
  *)        pip install -r requirements.txt ;;
esac
python -m spacy download en_core_web_sm
echo "Done. Activate with: source backend/.venv/bin/activate"
