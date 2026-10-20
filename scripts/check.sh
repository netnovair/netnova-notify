#!/usr/bin/env bash
# Run every local quality gate: backend lint/tests, frontend lint/types/tests/build.
# Usage: ./scripts/check.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "error: .venv is missing. Create it and install requirements-dev.txt first." >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "error: DATABASE_URL must point to a disposable PostgreSQL database whose name contains 'test'." >&2
  exit 1
fi

echo "== Backend: ruff =="
(cd apps/api && ../../.venv/bin/ruff check app tests scripts)
(cd apps/api && ../../.venv/bin/ruff format --check app tests scripts)

echo "== Backend: pytest =="
(cd apps/api && ../../.venv/bin/pytest -q --cov=app)

echo "== Frontend: lint / typecheck / tests =="
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test

echo "== Frontend: production build =="
npm --prefix apps/web run build

echo "All checks passed."
