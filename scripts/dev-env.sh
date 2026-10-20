#!/usr/bin/env bash
# Rebuild the local (non-Docker) development stack after a fresh checkout or a
# reset sandbox. It is idempotent: existing keys in .env are preserved.
#
#   1. python venv + backend dependencies
#   2. web dependencies
#   3. an embedded PostgreSQL instance (pgserver) with the app/test databases
#   4. Alembic migrations, the bootstrap admin and optional demo data
#
# It never writes secrets to Git: the generated .env is gitignored.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv"
PGDATA="${PGDATA:-/tmp/netnova-pgdata}"
ADMIN_EMAIL="${BOOTSTRAP_ADMIN_EMAIL:-admin@netnova.ir}"
# No default development password is committed. A random one is generated when
# .env is created and printed once at the end of the run.
ADMIN_PASSWORD="${BOOTSTRAP_ADMIN_PASSWORD:-}"

echo "==> 1/5 Python environment"
if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --disable-pip-version-check -r apps/api/requirements-dev.txt

echo "==> 2/5 Web dependencies"
if [ ! -d apps/web/node_modules ]; then
  (cd apps/web && npm ci --no-audit --no-fund)
fi

echo "==> 3/5 Local .env"
if [ ! -f .env ]; then
  if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(9))')"
  fi
  "$VENV/bin/python" - "$ADMIN_EMAIL" "$ADMIN_PASSWORD" <<'PY'
import secrets
import sys
from pathlib import Path

email, password = sys.argv[1], sys.argv[2]
values = {
    "ENVIRONMENT": "development",
    "LOG_LEVEL": "INFO",
    "SECRET_KEY": secrets.token_urlsafe(48),
    "DATABASE_URL": "postgresql+psycopg://postgres@/netnova?host=/tmp/netnova-pgdata",
    "SESSION_TTL_HOURS": "12",
    "COOKIE_SECURE": "false",
    "CORS_ORIGINS": "http://localhost:3000",
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_WEBHOOK_SECRET": secrets.token_urlsafe(32),
    "TELEGRAM_ADAPTER": "mock",
    "ADMIN_TELEGRAM_CHAT_ID": "",
    "BOOTSTRAP_ADMIN_EMAIL": email,
    "BOOTSTRAP_ADMIN_PASSWORD": password,
    "BOOTSTRAP_ADMIN_NAME": "مدیر نت نووا",
    "WORKER_POLL_INTERVAL_SECONDS": "2",
    "WORKER_BATCH_SIZE": "10",
    "WORKER_STALE_SECONDS": "300",
    "JOB_MAX_ATTEMPTS": "4",
    "JOB_BACKOFF_BASE_SECONDS": "30",
    "TEHRAN_TIMEZONE": "Asia/Tehran",
    "PAYMENT_REMINDER_DAYS_BEFORE": "3",
    "LOGIN_RATE_LIMIT": "10",
    "ACTIVATION_RATE_LIMIT": "10",
    "API_INTERNAL_URL": "http://127.0.0.1:8000",
    "NEXT_PUBLIC_SITE_URL": "http://localhost:3000",
    "DEV_PREVIEW_ORIGIN_REGEX": r"^https://[a-z0-9.-]+\.e2b\.app$",
}
body = "\n".join(f"{key}={value}" for key, value in values.items())
Path(".env").write_text(
    "# Local development environment (gitignored). Not for production use.\n" + body + "\n"
)
print("    created .env")
PY
else
  echo "    .env exists, left untouched"
fi

# License codes are encrypted with their own key. Local development needs one so
# the panel can reveal a code; it is generated once and stays in the gitignored .env.
if ! grep -q '^LICENSE_ENCRYPTION_KEY=' .env; then
  "$VENV/bin/python" -c "import secrets, pathlib; path = pathlib.Path('.env'); path.open('a', encoding='utf-8').write('LICENSE_ENCRYPTION_KEY=' + secrets.token_hex(32) + chr(10)); print('    added a generated LICENSE_ENCRYPTION_KEY to .env')"
fi

echo "==> 4/5 PostgreSQL (pgserver at $PGDATA)"
if ! "$VENV/bin/python" - "$PGDATA" <<'PY' >/dev/null 2>&1
import psycopg
import sys

with psycopg.connect(dbname="postgres", host=sys.argv[1], user="postgres") as connection:
    connection.execute("select 1")
PY
then
  echo "    starting the embedded server in the background"
  mkdir -p "$PGDATA"
  nohup "$VENV/bin/python" -c \
    "import pgserver, time, pathlib; pathlib.Path('$PGDATA').mkdir(parents=True, exist_ok=True); pgserver.get_server('$PGDATA'); time.sleep(10**9)" \
    >/tmp/netnova-pg.log 2>&1 &
  for _ in $(seq 1 30); do
    if "$VENV/bin/python" - "$PGDATA" <<'PY' >/dev/null 2>&1
import psycopg
import sys

with psycopg.connect(dbname="postgres", host=sys.argv[1], user="postgres") as connection:
    connection.execute("select 1")
PY
    then
      break
    fi
    sleep 1
  done
fi
"$VENV/bin/python" - "$PGDATA" <<'PY'
import sys

import psycopg

with psycopg.connect(dbname="postgres", host=sys.argv[1], user="postgres", autocommit=True) as conn:
    for database in ("netnova", "netnova_test"):
        if not conn.execute("select 1 from pg_database where datname = %s", (database,)).fetchone():
            conn.execute(f'create database "{database}"')
            print(f"    created database {database}")
PY

echo "==> 5/5 Migrations, admin and demo data"
(cd apps/api && "$VENV/bin/python" -m alembic upgrade head >/dev/null && echo "    migrations applied")
(cd apps/api && "$VENV/bin/python" -m scripts.seed_demo || echo "    demo seed skipped (already present)")

# Always report the credentials that are actually in .env, not a default.
ADMIN_EMAIL="$(grep -E '^BOOTSTRAP_ADMIN_EMAIL=' .env | head -1 | cut -d= -f2-)"
ADMIN_PASSWORD="$(grep -E '^BOOTSTRAP_ADMIN_PASSWORD=' .env | head -1 | cut -d= -f2-)"

cat <<EOF

Ready. Start the services in three terminals (or as background processes):

  cd apps/api && ../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
  cd apps/api && ../../.venv/bin/python -m app.worker.main
  cd apps/web && npm run dev

Admin login: $ADMIN_EMAIL / $ADMIN_PASSWORD
(This password is generated once, stored only in the gitignored .env, and can be
changed from the panel after the first sign-in.)
EOF
