# Deployment

Target: a **single Linux host** (2 vCPU / 4 GB RAM is enough for the MVP) with Docker
Compose, or equivalent systemd services. No Kubernetes, no microservices.

> Deployments are manual and deliberate. CI never deploys. Pull the reviewed commit,
> take a backup, run migrations, then restart services.

## 1. What runs

| Process | Image / command | Public? |
| --- | --- | --- |
| PostgreSQL 16 | `postgres:16-alpine` | **No** — internal network only |
| API | `infra/api.Dockerfile` → uvicorn on 8000 | Through the reverse proxy (`/api/*`, `/health/*`) |
| Worker | same image, `python -m app.worker.main` | No |
| Web panel | `infra/web.Dockerfile` → Next.js standalone on 3000 | Through the reverse proxy |
| Reverse proxy | Caddy 2 (or nginx) on 80/443 | Yes — TLS termination |

The `/api/v1/telegram/webhook` path is served by the API and must be reachable over
HTTPS.

## 2. Prerequisites

- A DNS record (e.g. `notify.example.com`) pointing to the host.
- Ports 80 and 443 open; 3000 and 8000 should not be exposed publicly.
- Docker Engine 24+ and the Docker Compose plugin.
- A strong PostgreSQL password and a long `SECRET_KEY`.

## 3. First deployment (Docker Compose)

### 3.1 Prepare the environment file

On the server, from the repository root:

```bash
cp .env.example .env
```

Edit `.env` with production values:

```dotenv
ENVIRONMENT=production
LOG_LEVEL=INFO
SECRET_KEY=<48+ random characters>
DATABASE_URL=postgresql+psycopg://netnova:CHANGE_ME@db:5432/netnova   # overridden by compose
COOKIE_SECURE=true
CORS_ORIGINS=https://notify.example.com
NEXT_PUBLIC_SITE_URL=https://notify.example.com
TELEGRAM_BOT_TOKEN=<real bot token>
TELEGRAM_WEBHOOK_SECRET=<32+ random characters>
TELEGRAM_ADAPTER=http
BOOTSTRAP_ADMIN_EMAIL=admin@your-domain.example
BOOTSTRAP_ADMIN_PASSWORD=<strong unique password>
BOOTSTRAP_ADMIN_NAME=مدیر نت نووا
SESSION_TTL_HOURS=12
PAYMENT_REMINDER_DAYS_BEFORE=3
WORKER_POLL_INTERVAL_SECONDS=2
WORKER_BATCH_SIZE=10
WORKER_STALE_SECONDS=300
JOB_MAX_ATTEMPTS=4
JOB_BACKOFF_BASE_SECONDS=30

# Optional additional channels. Leave blank to keep a provider disabled; the panel
# then reports it as "not configured" and projects cannot enable it.
BALE_BOT_TOKEN=
BALE_API_BASE=https://tapi.bale.ai
EITAA_BOT_TOKEN=
EITAA_API_BASE=https://eitaa.com/api
SMSIR_API_KEY=
SMSIR_LINE_NUMBER=
CHANNEL_HTTP_TIMEOUT_SECONDS=10

# Compose-only values (not read by the app directly)
POSTGRES_DB=netnova
POSTGRES_USER=netnova
POSTGRES_PASSWORD=<strong database password>
DOMAIN=notify.example.com
SITE_ORIGIN=https://notify.example.com
WEB_PORT=3000
```

`SECRET_KEY` protects session hashing, license-code HMACs and CSRF material. Losing or
rotating it invalidates license hashes: plan a license re-issue window.

The API **refuses to start** in production if `SECRET_KEY` is weak, `COOKIE_SECURE` is
false, CORS contains `*`, or a real bot token is used without a webhook secret.

### 3.2 Build and start

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

This starts PostgreSQL, runs `alembic upgrade head` once in the `api` container, starts
the API, waits for its readiness check, then starts the worker and the web panel.

Check status:

```bash
docker compose --env-file .env -f infra/docker-compose.yml ps
docker compose --env-file .env -f infra/docker-compose.yml logs -f api
```

### 3.3 Enable HTTPS

The default stack exposes the panel on port 3000 for testing. For production, enable the
Caddy profile:

```bash
docker compose --env-file .env -f infra/docker-compose.yml --profile production up -d
```

Caddy obtains a certificate for `DOMAIN`, redirects HTTP to HTTPS, adds HSTS and routes
`/api/*` and `/health/*` to the API and everything else to Next.js.

If you use nginx instead, the equivalent rules are:

```nginx
server {
    listen 443 ssl http2;
    server_name notify.example.com;

    location /api/    { proxy_pass http://127.0.0.1:3000; }   # through Next rewrite
    # or: location /api/ { proxy_pass http://127.0.0.1:8000; }
    location /health/ { proxy_pass http://127.0.0.1:8000; }
    location /        { proxy_pass http://127.0.0.1:3000; }

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Use one consistent path for `/api/*`; do not expose port 8000 directly.

> **Important:** `API_INTERNAL_URL` is compiled into the Next.js build (rewrites are part
> of the build manifest). Rebuild the web image when the internal API address changes.

### 3.4 Register the Telegram webhook

```bash
docker compose --env-file .env -f infra/docker-compose.yml exec api \
  python -m scripts.set_webhook --url https://notify.example.com/api/v1/telegram/webhook
```

The command requires `TELEGRAM_ADAPTER=http` and a webhook secret. Verify in the panel:
Settings → Telegram shows «ربات واقعی» and «Secret وب هوک: تنظیم شده».

### 3.5 First login

Open `https://notify.example.com`, sign in with `BOOTSTRAP_ADMIN_EMAIL` /
`BOOTSTRAP_ADMIN_PASSWORD`. The bootstrap account is created **only** when no admin
exists. Change the operational procedure for passwords (see Security) and never reuse
the bootstrap password.

Create the first project, copy the license code shown once, and send it to the employer
over a secure channel.

## 4. Without Docker (systemd reference)

```ini
# /etc/systemd/system/netnova-api.service
[Unit]
Description=NetNova Notify API
After=network.target postgresql.service

[Service]
User=netnova
WorkingDirectory=/srv/netnova-notify/apps/api
EnvironmentFile=/etc/netnova/notify.env
ExecStart=/srv/netnova-notify/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/netnova-worker.service
[Unit]
Description=NetNova Notify worker
After=network.target postgresql.service netnova-api.service

[Service]
User=netnova
WorkingDirectory=/srv/netnova-notify/apps/api
EnvironmentFile=/etc/netnova/notify.env
ExecStart=/srv/netnova-notify/.venv/bin/python -m app.worker.main
Restart=always
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

For the panel run `next start` (or the standalone server) behind the same proxy. Run
`alembic upgrade head` manually before restarting the API and worker.

### 4.1 Enabling Bale, Eitaa or SMS.ir

1. Put the provider credentials in `.env` and restart the API **and** the worker (the
   worker sends messages; the API only validates configuration).
2. Open the panel → **تنظیمات** → **کانال های ارسال** and confirm the provider now reads
   «تنظیم شده». If it still reads «تنظیم نشده», the variable name or value is wrong; the
   panel intentionally shows the honest state and never the token.
3. Open the project → **قابلیت ها و کانال ها** and enable the channel for that project.
4. Register each employer's destination in **کاربران مجاز** (`member_channel_identities`):
   a Bale/Eitaa chat id or `09xxxxxxxxx` for SMS. Telegram uses the bot identity and needs
   no extra row.
5. Send a test notification and verify the per-destination rows in the notification
   detail (`channel`, `recipient`, `status`).

Notes:

- Bale and Eitaa use their Telegram-compatible bot APIs and accept HTML formatting;
  SMS.ir receives plain text and truncates to 1000 characters. Buttons are never sent to
  SMS.
- These providers are labeled **بتا** in the panel until the agency has verified them with
  real accounts; do not promise them to clients before that.
- If a provider is misconfigured, its send fails with a permanent error. The notification
  is marked `failed` with the provider message; it is never reported as sent.

## 5. Upgrades

```bash
cd /srv/netnova-notify
git fetch --all
git checkout <reviewed-commit-or-tag>

# 1. Backup first
./scripts/backup.sh

# 2. Rebuild and migrate
docker compose --env-file .env -f infra/docker-compose.yml up -d --build

# 3. Verify
curl -fsS https://notify.example.com/api/v1/health/ready
docker compose --env-file .env -f infra/docker-compose.yml logs --tail=100 api worker
```

Notes:

- Migrations run automatically in the `api` container before uvicorn starts. If a
  migration fails, the API container exits; fix forward before restarting.
- Roll back the application image only if the new migrations are backward compatible.
  Destructive migrations require a restore from backup.
- Never edit applied migration files. Add a new revision.

## 6. Backups and restore

PostgreSQL is the only stateful component.

```bash
# Backup (custom format, compressed)
docker compose --env-file .env -f infra/docker-compose.yml exec -T db \
  pg_dump -U netnova -Fc netnova > /var/backups/netnova-$(date +%F-%H%M).dump

# Restore into a fresh database (stop api/worker first)
docker compose --env-file .env -f infra/docker-compose.yml exec -T db \
  createdb -U netnova netnova_restore
docker compose --env-file .env -f infra/docker-compose.yml exec -T db \
  pg_restore -U netnova -d netnova_restore --clean --if-exists < backup.dump
```

- Store backups off-host, encrypted, with a retention policy.
- Test a restore on a staging host at least once per quarter.
- A backup without `SECRET_KEY` cannot verify existing license codes; keep the secret in
  the secret manager, not in the database backup.
- `scripts/backup.sh` wraps the pg_dump command for local/native installs.

## 7. Monitoring and health

| Check | How |
| --- | --- |
| Liveness | `GET /api/v1/health/live` → `200` |
| Readiness | `GET /api/v1/health/ready` → `200`, `503` if DB is down |
| Worker | Panel Settings or `GET /api/v1/system/status` → `worker.status` |
| Queue | `pending_jobs`, `failed_jobs` in `/system/status` |
| API errors | Container logs (`api`, `worker`), filtered for secrets |
| API schema | Disabled in production (`/api/docs` and `/api/openapi.json` return 404) |
| Disk usage | PostgreSQL volume and Docker logs |

Recommended alerts:

- readiness failing for > 2 minutes;
- `failed_jobs > 0` or `queued_notifications` growing while the worker is offline;
- repeated `auth.login_failed` or `429` on login;
- certificate expiry (Caddy renews automatically; still monitor).

Health endpoints never require authentication and never return private data.

## 8. Security checklist before go-live

- [ ] HTTPS with a valid certificate; `COOKIE_SECURE=true`; HSTS at the proxy.
- [ ] `SECRET_KEY`, bot token, webhook secret and DB password are random and only in the
      secret manager / `.env` outside Git.
- [ ] PostgreSQL port not published; API port not published; only 80/443 exposed.
- [ ] `CORS_ORIGINS` and `NEXT_PUBLIC_SITE_URL` set to the exact HTTPS origin.
- [ ] Webhook secret registered and verified; `TELEGRAM_ADAPTER=http`.
- [ ] Admin bootstrap password unique; consider restricting admin access by IP/VPN.
- [ ] Backups scheduled and a restore has been tested.
- [ ] Worker and API restart policies enabled; logs rotate.
- [ ] `alembic upgrade head` succeeded; `alembic check` clean in development.
- [ ] Demo data is absent from production (`is_demo = false` everywhere).
- [ ] Monitoring for readiness, failed jobs and certificate expiry.

## 9. Rollback

1. Stop the worker and API (`docker compose ... stop worker api`).
2. Restore the database backup if the new release changed the schema incompatibly.
3. Check out the previous commit and rebuild.
4. Start API (migrations for the old revision are not run automatically downward;
   `alembic downgrade` is only safe if the revision supports it — prefer restore).
5. Verify readiness and a test login, then start the worker.
6. Re-register the webhook if the domain changed.

## 10. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `api` exits with "Invalid configuration" | Production hardening rules; read the message and fix the env |
| `api` restarts: `database schema is not ready` | Run `alembic upgrade head` (compose does this automatically) |
| 502 from proxy | API not healthy; check `docker compose logs api` |
| Login succeeds but requests return 401 | Cookie `Secure` + HTTP access mismatch; use HTTPS |
| Login returns to the login screen inside a preview iframe | Third-party cookie blocking. Preview hosts get `SameSite=None; Secure; Partitioned` automatically (development only); otherwise open the preview URL in its own tab |
| Login returns 403 `forbidden` | `Origin` ≠ `CORS_ORIGINS`/`NEXT_PUBLIC_SITE_URL` |
| Telegram webhook 403 | Wrong/missing `X-Telegram-Bot-Api-Secret-Token`; re-run `set_webhook` |
| Webhook 503 in production | `TELEGRAM_WEBHOOK_SECRET` is empty |
| Messages stay queued | Worker container not running, or scheduled time in the future |
| Messages fail with "no approved employer" | Employer has not completed activation/approval |
| `next build` cannot reach API | Build does not need the API; check `API_INTERNAL_URL` build arg |
| Worker shows offline in panel | Heartbeat older than the threshold; inspect worker logs |
