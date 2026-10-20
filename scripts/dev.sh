#!/usr/bin/env bash
# Start the API, worker and admin panel for local development.
# Requires: .venv, node_modules and a reachable PostgreSQL configured in .env.
# Usage: ./scripts/dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "error: .env is missing. Copy .env.example to .env and edit it." >&2
  exit 1
fi

if [[ ! -d apps/web/node_modules ]]; then
  echo "error: apps/web/node_modules is missing. Run 'npm --prefix apps/web ci'." >&2
  exit 1
fi

pids=()
cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "Applying database migrations..."
(cd apps/api && ../../.venv/bin/alembic upgrade head)

echo "Starting API on http://127.0.0.1:8000 ..."
(cd apps/api && ../../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
pids+=($!)

echo "Starting worker..."
(cd apps/api && ../../.venv/bin/python -m app.worker.main) &
pids+=($!)

echo "Starting admin panel on http://localhost:3000 ..."
(cd apps/web && npm run dev) &
pids+=($!)

echo "Press Ctrl+C to stop all processes."
wait
