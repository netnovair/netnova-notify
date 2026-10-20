#!/usr/bin/env bash
# Create a compressed PostgreSQL backup for NetNova Notify.
#
# Usage:
#   DATABASE_URL='postgresql+psycopg://user:pass@host:5432/netnova' ./scripts/backup.sh [output-dir]
#
# The file is written with restrictive permissions (0600). Keep backups off-host and
# encrypted; a backup plus SECRET_KEY is required to verify existing license codes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DATABASE_URL:-}" && -f .env ]]; then
  # Read only DATABASE_URL; .env may contain unquoted non-shell values.
  DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' .env | head -n 1)"
  DATABASE_URL="${DATABASE_URL%\"}"; DATABASE_URL="${DATABASE_URL#\"}"
  DATABASE_URL="${DATABASE_URL%\'}"; DATABASE_URL="${DATABASE_URL#\'}"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "error: DATABASE_URL is not set and .env does not define it." >&2
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "error: pg_dump is not installed or not on PATH." >&2
  echo "       For Docker deployments run pg_dump via:" >&2
  echo "       docker compose --env-file .env -f infra/docker-compose.yml exec -T db \\" >&2
  echo "         pg_dump -U \"\$POSTGRES_USER\" -Fc \"\$POSTGRES_DB\" > backup.dump" >&2
  exit 1
fi

output_dir="${1:-backups}"
mkdir -p "$output_dir"

# libpq accepts postgresql:// but not the SQLAlchemy driver suffix.
libpq_url="${DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
umask 077
timestamp="$(date +%Y%m%d-%H%M%S)"
file="$output_dir/netnova-$timestamp.dump"

pg_dump --format=custom --no-owner --no-privileges --file="$file" "$libpq_url"
echo "Backup written to $file"
