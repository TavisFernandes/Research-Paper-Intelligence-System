#!/usr/bin/env bash
# Start the Vite dev server (http://localhost:5173). Needs Node 20+ and pnpm.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
pnpm install
VITE_API_URL="${VITE_API_URL:-http://localhost:8000}" pnpm --filter @workspace/research-paper-intelligence run dev
