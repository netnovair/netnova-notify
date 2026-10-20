# Local setup on Windows

This guide uses **PowerShell**, Python 3.11, Node.js 22 LTS and PostgreSQL 16.
All commands are run from the repository root unless stated otherwise.

> The admin panel and API are separate processes, and the worker is a third process.
> Keep three PowerShell windows open during development.

## 1. Install prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.11+ | Check "Add python.exe to PATH" in the installer |
| Node.js | 22 LTS+ | Includes npm |
| PostgreSQL | 16 | Keep the default port 5432 and remember the `postgres` password |
| Git | latest | Optional if you already have the repository |

Verify in a new PowerShell window:

```powershell
python --version
node --version
npm --version
psql --version
```

If `psql` is not recognized, add `C:\Program Files\PostgreSQL\16\bin` to `PATH`
(Start → "Edit the system environment variables" → Environment Variables).

## 2. Get the code and create the database

```powershell
cd C:\Projects
git clone <repository-url> netnova-notify
cd netnova-notify
```

Create the development database and a test database (tests are destructive):

```powershell
$env:PGPASSWORD = "your-postgres-password"
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres netnova
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres netnova_test
```

## 3. Create the virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r apps\api\requirements-dev.txt
```

If PowerShell blocks activation scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

(Alternatively run `.\.venv\Scripts\python.exe` explicitly for every command.)

## 4. Configure `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Minimum development values:

```dotenv
ENVIRONMENT=development
SECRET_KEY=<paste a random 48+ character value>
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/netnova
COOKIE_SECURE=false
CORS_ORIGINS=http://localhost:3000
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADAPTER=mock
TELEGRAM_WEBHOOK_SECRET=<random 32+ character value>
BOOTSTRAP_ADMIN_EMAIL=admin@netnova.ir
BOOTSTRAP_ADMIN_PASSWORD=<a strong development password>
BOOTSTRAP_ADMIN_NAME=مدیر نت نووا
API_INTERNAL_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

Generate secrets:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Notes:

- `TELEGRAM_BOT_TOKEN` empty + `TELEGRAM_ADAPTER=mock` means **messages are simulated**
  and clearly marked as mock. Nothing is sent to Telegram.
- Never commit `.env`. It is already in `.gitignore`.
- On Windows, use `localhost`/`127.0.0.1` in `DATABASE_URL`; Unix sockets are not used.

## 5. Apply migrations

```powershell
cd apps\api
alembic upgrade head
alembic check        # should report no new upgrade operations
cd ..\..
```

If `alembic` is not recognized, make sure the virtual environment is activated, or run
`python -m alembic upgrade head`.

## 6. Install frontend dependencies

```powershell
cd apps\web
npm ci
cd ..\..
```

`npm ci` uses the committed `package-lock.json` and fails if it drifts.

## 7. Run the three processes

Open three PowerShell windows, activate the venv in each, and run:

**Window 1 — API**

```powershell
cd C:\Projects\netnova-notify\apps\api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Window 2 — worker**

```powershell
cd C:\Projects\netnova-notify\apps\api
python -m app.worker.main
```

**Window 3 — admin panel**

```powershell
cd C:\Projects\netnova-notify\apps\web
npm run dev
```

Open <http://localhost:3000> and sign in with the bootstrap email/password. The account is
created only on the first API start when `admin_users` is empty.

Useful checks:

- API health: <http://localhost:8000/api/v1/health/ready>
- API docs: <http://localhost:8000/api/docs>
- Panel proxy: <http://localhost:3000/api/v1/health/ready>

## 8. Optional demo data

With the API configured for the mock adapter:

```powershell
cd apps\api
python -m scripts.seed_demo
```

The script refuses to run when the real bot adapter is configured, does not duplicate
its own demo rows, and prints license codes once. Demo projects are marked «نمایشی» in
the panel and must not be used as operational data.

## 9. Run tests and checks

Backend (destructive — the database name must contain `test`):

```powershell
cd apps\api
$env:DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/netnova_test"
pytest -q --cov=app
$env:DATABASE_URL = $null
```

Frontend:

```powershell
cd apps\web
npm run lint
npm run typecheck
npm run test
npm run build
```

`npm run build` is a production build of the PWA; it should finish without type errors.

## 10. Telegram (optional, real bot)

1. Create a bot with BotFather (`/newbot`) and keep the token private.
2. Set `TELEGRAM_BOT_TOKEN`, a random `TELEGRAM_WEBHOOK_SECRET`, and
   `TELEGRAM_ADAPTER=http` in `.env`.
3. The webhook must be reachable over **public HTTPS**. For local experiments, use a
   tunnel (for example Cloudflare Tunnel or ngrok) pointing to port 8000.
4. Register the webhook:

```powershell
cd apps\api
python -m scripts.set_webhook --url https://YOUR-PUBLIC-HOST/api/v1/telegram/webhook
```

5. Remove it when finished:

```powershell
python -m scripts.set_webhook --delete
```

Never put a real bot token in Git, issue trackers or chat. If it leaks, revoke it in
BotFather immediately and re-register the webhook.

## 11. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `psql` / `createdb` not found | Add PostgreSQL `bin` to `PATH`, or call the full path |
| `ModuleNotFoundError: psycopg` | Virtual environment not activated; run `.\.venv\Scripts\Activate.ps1` |
| `alembic: command not found` | Use `python -m alembic ...` inside the venv |
| `password authentication failed` | Wrong password in `DATABASE_URL`; URL-encode special characters (`@` → `%40`, `#` → `%23`) |
| `database "netnova" does not exist` | Create it with `createdb -U postgres netnova` |
| API starts but schema errors appear | Run `alembic upgrade head` first |
| Login returns 403 `csrf_failed` | Refresh the page to obtain a new CSRF token; do not call the API by hand without the header |
| Login returns 403 `forbidden` | The browser `Origin` is not allowed. Use `http://localhost:3000` or add the origin to `CORS_ORIGINS` |
| `next dev` port 3000 busy | Stop the other process or run `npm run dev -- -p 3001` and add that origin to `CORS_ORIGINS` |
| Worker shows "بدون گزارش" | Start `python -m app.worker.main`; it writes a heartbeat every few seconds |
| Notifications stay queued | Worker is not running, or the scheduled time is in the future |
| `pytest` refuses to run | `DATABASE_URL` must point to a database whose name contains `test`; tests drop the schema |
| Mock messages | `TELEGRAM_ADAPTER=mock` — expected in development; no real Telegram traffic |

## 12. Stopping

Press `Ctrl+C` in each window. To reset the development database completely:

```powershell
$env:PGPASSWORD = "your-postgres-password"
& "C:\Program Files\PostgreSQL\16\bin\dropdb.exe" -U postgres netnova
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres netnova
cd apps\api
alembic upgrade head
```

This deletes all local data. Never run it against production.
