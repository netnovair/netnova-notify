# NetNova Notify

A production-oriented Telegram notification platform for NetNova's client projects.
One central Telegram bot serves every project; each project has its own license,
feature flags, employer access and financial records.

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16
- **Admin panel:** Next.js 16 (App Router), TypeScript, Tailwind CSS 4, RTL Persian, dark-first PWA
- **Worker:** independent process with a durable PostgreSQL-backed job queue
- **Bot:** Telegram Bot API (central bot) with a mock adapter for local development

> Every number, status and message shown in the admin panel is read from the database.
> Features that are not implemented yet are explicitly labelled **«به زودی»** and never
> return fabricated data. Payments are record-and-notify only — there is no payment
> gateway integration and the system never claims a bank transaction was verified.

## Feature status

| Capability | Status | Notes |
| --- | --- | --- |
| Admin sign-in (session cookie + CSRF) | Implemented | Bootstrap account + admin management |
| Admin accounts and password rotation | Implemented | Create/deactivate admins, change own password, reset with one-time temp password, session revocation |
| Projects, feature flags, activation | Implemented | Per-project license, one live license per project |
| Project archive / restore / delete | Implemented | Archive stops operation; deletion requires the exact name; demo data purge |
| License issue / revoke / expiry | Implemented | Raw code shown once, only a keyed hash stored |
| Employer activation in Telegram | Implemented | `/start`, license code, admin approval, project menu |
| Telegram menus | Implemented | «اطلاعیه های من», «اطلاعیه های مالی», «پشتیبانی و تیکت» are real |
| گزارش عملکرد / پیشرفت پروژه | Placeholder | «به زودی» via the capability registry |
| Capability plugins per project | Implemented | Add a module in `app/features/`; no migration or panel change |
| Two-way support tickets | Implemented | Telegram conversation + admin inbox, unread counters, close/reopen |
| Order intake for unlicensed visitors (ثبت سفارش) | Implemented | Service tree, per-service questions, identity asked once, dashboard CRUD |
| Sample works (نمونه کار) | Implemented | Text + optional https image per service, sent by the bot on demand |
| Pre-sales order inbox | Implemented | `/orders` in the panel: filters, counters, status workflow, internal note |
| Bale / Eitaa / SMS.ir channels | Beta | Configured centrally by env; per-project toggle; honest `configured` state |
| Announcement queue + worker | Implemented | Retries, backoff, stale-claim recovery, unknown-result handling |
| Payments and scheduled reminders | Implemented | Statuses unpaid/paid/cancelled, overdue computed, no gateway |
| Audit log | Implemented | Admin, Telegram and system actors |
| PWA install + offline shell | Implemented | Offline page is honest; API responses are never cached |
| Multi-member projects | Data model ready | UI/activation restrict each project to one primary employer in v1 |

## Repository layout

```text
netnova-notify/
├── apps/
│   ├── api/                 FastAPI application
│   │   ├── app/
│   │   │   ├── api/v1/      HTTP routers
│   │   │   ├── adapters/    Telegram adapters (http, mock)
│   │   │   ├── core/        config, security, errors, rate limiting, logging
│   │   │   ├── db/          engine, session, declarative base
│   │   │   ├── domain/      enums, feature registry, menu, Jalali helpers, rules
│   │   │   ├── models/      SQLAlchemy models
│   │   │   ├── repositories/ data access
│   │   │   ├── schemas/     Pydantic request/response models
│   │   │   ├── services/    business logic
│   │   │   └── worker/      job runner and handlers
│   │   ├── alembic/         migrations
│   │   ├── scripts/         seed_demo.py, set_webhook.py
│   │   └── tests/           pytest suite
│   └── web/                 Next.js admin PWA
│       ├── public/          icons, service worker, offline page
│       └── src/
│           ├── app/         routes (login, dashboard, projects, licenses, …)
│           ├── components/  layout, UI primitives, auth, PWA
│           ├── features/    feature-specific UI
│           ├── lib/         API client, formatting, validation, hooks
│           └── types/       API types
├── docs/                    architecture, API contract, data model, security, setup, deployment
├── infra/                   Docker images and docker-compose for a single-host deployment
├── scripts/                 developer helper scripts
└── .github/workflows/       CI pipeline
```

## Quick start (Linux / macOS)

Requirements: Python 3.11+, Node.js 22+, PostgreSQL 16+ (or Docker).

For a disposable sandbox or CI-like machine that has no system PostgreSQL, one script
builds everything (venv, web dependencies, a local `.env`, an embedded PostgreSQL
instance, migrations and demo data):

```bash
./scripts/dev-env.sh
```

Then start the three services as shown below. The script is idempotent and never
overwrites an existing `.env`. The first admin password is generated randomly, stored only
in the gitignored `.env`, and printed once when the script finishes; change it from the
panel after the first sign-in.

With a real PostgreSQL server:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements-dev.txt

cp .env.example .env          # edit every placeholder
# create the database, e.g.:
#   createdb netnova

cd apps/api
alembic upgrade head
cd ../..

npm --prefix apps/web ci

# terminal 1
cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# terminal 2
cd apps/api && python -m app.worker.main
# terminal 3
cd apps/web && npm run dev
```

Open <http://localhost:3000>. The Next.js server proxies `/api/v1/*` to the API, so the
browser only talks to the web origin. The admin account is created on first API start
from `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` (only when no admin exists).

Windows users: see [docs/local-setup-windows.md](docs/local-setup-windows.md).

### Demo data (development only)

```bash
cd apps/api
TELEGRAM_ADAPTER=mock python -m scripts.seed_demo
```

The seed is idempotent for its own demo rows, refuses to run against a real bot, and
prints license codes exactly once. Demo projects are flagged `is_demo` and labelled
«نمایشی» in the UI; they are never mixed with operational reporting.

## Configuration

All settings are environment variables (see [.env.example](.env.example)); the API and
worker read the same `.env` at the repository root. Key values:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Session token hashing, license HMAC, CSRF material (≥32 random chars) |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/dbname` |
| `COOKIE_SECURE` | Must be `true` behind HTTPS |
| `TELEGRAM_BOT_TOKEN` | Central bot token; empty ⇒ mock mode |
| `TELEGRAM_ADAPTER` | `auto` / `http` / `mock` |
| `TELEGRAM_WEBHOOK_SECRET` | Validated against `X-Telegram-Bot-Api-Secret-Token` |
| `BOOTSTRAP_ADMIN_*` | One-time creation of the first admin |
| `WORKER_*`, `JOB_*` | Polling interval, batch size, stale-claim window, retry policy |
| `PAYMENT_REMINDER_DAYS_BEFORE` | Reminder lead time (default 3 days) |

Never commit a real `.env`, bot token, session cookie or license code.
Production refuses to start with placeholder secrets or `COOKIE_SECURE=false`.

## Telegram bot flows

1. Admin creates a project → a license is issued automatically. The raw code is shown once.
2. The employer opens the central bot and sends `/start`.
3. They submit the license code; the bot validates it, checks project status and expiry,
   and records an activation request (pending admin approval when required).
4. The admin approves the request in the panel (or the project is configured to
   auto-approve). Membership becomes `active`, and the project menu appears.
5. Menu buttons are built from the Feature Registry and the project's enabled flags.
   Access is re-checked on every callback; revoked licenses or disabled projects stop
   working immediately.
6. Callback payloads are short, index-based (`p:<n>`, `<n>:ann`, `<n>:fin`,
   `<n>:tickets`, `<n>:ticket:<ordinal>`, `<n>:soon:<key>`) and never contain license
   codes, chat IDs, database ids or amounts.
7. «پشتیبانی و تیکت» opens the employer's own tickets, lets them open a new ticket or
   reply to an existing thread. Messages go through `telegram_conversations`, so the
   callback data stays id-free. The admin answers from **پشتیبانی** in the panel and the
   employer gets a short Telegram notice.

### Order intake (ثبت سفارش)

The same bot serves visitors who have **no license and no project**:

1. `/start` shows «ثبت سفارش» and «نمونه کارها», plus a persistent reply keyboard
   (`ثبت سفارش` / `منوی من` / `راهنما`). `/start`, `/menu`, `/cancel`, `/help` are
   registered with Telegram through `setMyCommands`.
2. «ثبت سفارش» lists the active main services from the database, so the panel is the
   only place that defines the menu. Callback data is index based (`oc:<n>`,
   `oi:<n>:<m>`, `oq:<q>:<o>`) and re-resolved against the current tree on every tap.
3. The visitor picks a sub service and answers its questions. Questions are ordinary
   rows in `service_questions`: text, long text, number (with min/max), multiple choice
   or phone. Choice questions become buttons.
4. Name and phone are asked once per Telegram user and stored in
   `telegram_users.contact_name/contact_phone`; later orders skip straight to the
   questions. Phone numbers are normalised (`+98`, Persian digits) and validated as
   `09xxxxxxxxx`.
5. Every sub service can expose «نمونه کارها»: a text plus an optional public https
   image, both edited in the panel. Nothing is fabricated — the copy is whatever the
   team enters.
6. The review screen shows the answers; «ثبت نهایی سفارش» writes `service_requests`,
   replies with a tracking number and (when `ADMIN_TELEGRAM_CHAT_ID` is set) pings the
   admin. The panel side lives at **سفارش ها**.
7. **خدمات** in the panel is the CRUD editor for main services, sub services and their
   questions. Deleting is refused while orders reference the row; deactivate instead to
   hide it from the bot immediately.

## Delivery channels

Telegram is the default. Bale, Eitaa and SMS.ir are optional providers configured once
for the agency through environment variables (`BALE_*`, `EITAA_*`, `SMSIR_*`); each
project can enable them individually in **قابلیت ها و کانال ها**. Non-Telegram
destinations are stored per member in **کاربران مجاز**. The panel shows the real
`configured` state and refuses to enable a provider that has no credentials. Unknown
send outcomes are never retried automatically and never reported as success.

## Capability plugins

Adding a capability does not touch the dispatcher, menu builder, database schema or the
web panel:

```python
# app/features/invoice.py
from app.features.base import FeatureContext, FeatureDefinition, register

FEATURE = FeatureDefinition(
    key="invoice", label="فاکتورها", description="دانلود فاکتورهای پروژه",
    implemented=True, default_enabled=False, order=25, action="invoice",
)

def handle(ctx: FeatureContext) -> None:
    ...  # ctx.db, ctx.adapter, ctx.member, ctx.chat_id, ctx.index, ctx.bot
```

Register `FEATURE`/`handle` in `app/features/__init__.py`; the capability appears in
`GET /api/v1/features`, in every project's toggles, and in the employer menu when enabled.

## Testing and CI

```bash
# Backend (needs a disposable PostgreSQL database whose name contains "test")
cd apps/api
DATABASE_URL='postgresql+psycopg://postgres@/netnova_test?host=/tmp/pgdata' \
  pytest -q --cov=app

# Frontend
cd apps/web
npm run lint
npm run typecheck
npm run test
npm run build
```

Recorded results for this repository state:

- Backend: **123 passed**, **88%** statement coverage (`pytest --cov=app`).
- Frontend: **45 passed** across 7 files (`vitest`), ESLint clean (0 errors, 6 warnings),
  TypeScript clean, `next build` succeeds (12 routes).

CI (`.github/workflows/ci.yml`) runs both suites, linting, type checking and a production
build against a PostgreSQL service container. No deployment happens from CI.

## Documentation

- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [Data model](docs/data-model.md)
- [Security](docs/security.md)
- [Local setup on Windows](docs/local-setup-windows.md)
- [Deployment](docs/deployment.md)

## Security

See [SECURITY.md](SECURITY.md). Report vulnerabilities privately; do not open a public
issue containing a license code, token or personal data.

## Known limitations

- Payments are recorded manually; there is no gateway, receipt upload or reconciliation.
- One primary employer per project (the schema supports multiple members; the v1 flow
  and UI intentionally keep one active employer).
- The performance/progress menu items are placeholders by design; support is real.
- Bale, Eitaa and SMS.ir adapters are implemented against their published APIs but are
  labeled beta until verified with real agency accounts.
- Tickets support text only (no attachments), and the employer side lives in Telegram; a
  separate employer web login is not planned for v1.
- In-memory rate limiting is per-process; run a single API process or move limits to a
  shared store before scaling horizontally.
- The PWA never caches API responses; offline mode only shows the shell and an honest
  connection notice.
