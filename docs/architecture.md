# Architecture

## 1. Context

NetNova runs marketing/digital projects for multiple clients ("employers"). It needs a
single place to notify each client about project announcements and financial state
through Telegram, without creating a new bot per project and without exposing one
client's data to another.

NetNova Notify provides:

- an **admin panel** used only by NetNova staff;
- one **central Telegram bot** used by all employers;
- **per-project licenses** that bind a Telegram user to exactly one project;
- a **durable job queue** for outbound Telegram messages and payment reminders;
- an **audit trail** of sensitive operations.

## 2. Deployment topology

```text
                        HTTPS
Browser (admin, PWA) ───────────► Reverse proxy (Caddy / nginx)
                                     │
                                     ├── /            → Next.js (apps/web)
                                     └── /api/v1/*    → FastAPI (apps/api)
                                                            │
Telegram cloud  ── webhook ──► /api/v1/telegram/webhook ────┤
                                                            ├── PostgreSQL 16
Worker process (app.worker.main) ───────────────────────────┘
```

- The browser only talks to the web origin. Next.js rewrites `/api/v1/:path*` to the
  internal API URL (`API_INTERNAL_URL`), so cookies stay first-party and no CORS
  preflight is needed for the panel.
- The API and the worker are separate processes sharing the same database. The worker
  never serves HTTP.
- Telegram calls the webhook over the public HTTPS URL. The webhook secret is validated
  before any processing.

## 3. Code structure and responsibilities

The backend follows a layered structure; dependencies point inward.

| Layer | Location | Responsibility |
| --- | --- | --- |
| Adapters | `app/adapters/telegram` | Bot API transport (`http`), simulation (`mock`), message formatting |
| API | `app/api/v1` | HTTP parsing, dependencies, response models |
| Services | `app/services` | Business rules, transactions, audit entries |
| Domain | `app/domain` | Enums, feature registry, menu building, Jalali helpers, notification/payment rules |
| Repositories | `app/repositories` | SQLAlchemy queries, locking, pagination |
| Models | `app/models` | Tables, constraints, relationships |
| Schemas | `app/schemas` | Pydantic validation and serialization |
| Worker | `app/worker` | Job claim loop, handlers, heartbeat, stale recovery |

Key rules enforced by the service layer:

- A project always has a license; issuing a new license revokes the previous live one.
- Raw license codes never leave the process after creation; only `code_prefix` and a
  keyed hash (`HMAC-SHA256(SECRET_KEY, code)`) are stored.
- Employer access requires: license live (pending/active, not revoked/expired), project
  active, and member status `active`.
- Membership checks happen on every Telegram callback, not only at activation time.
- Notifications are queued as jobs in the same transaction as their state change.

## 4. Key flows

### 4.1 Admin session

1. `POST /api/v1/auth/login` validates credentials with Argon2id.
2. A random 256-bit session token is generated; the database stores its SHA-256 hash,
   a per-session CSRF token, expiry and client metadata.
3. The token is sent as an `HttpOnly`, `SameSite=Lax` cookie (`Secure` when
   `COOKIE_SECURE=true`).
4. Mutating requests must send `X-CSRF-Token`, compared in constant time.
5. `GET /api/v1/auth/me` returns the admin profile and CSRF token, which the panel keeps
   in memory only.

The Next.js middleware equivalent is implemented in the client (`AppShell`): while the
session state is loading or anonymous, private content is never rendered.

### 4.2 License activation

```text
Employer → Bot /start → "send your license code"
Employer → code ──► POST /api/v1/telegram/webhook ─► webhook secret check
                                                   ─► update_id dedupe (DB unique)
                                                   ─► rate limit per chat
                                                   ─► license hash lookup
                                                   ─► project active? license live?
                                                   ─► create/reactivate ProjectMember (pending_approval)
                                                   ─► audit member.activation_requested
                                                   ─► admin notification (optional)
Employer → menu (only after approval, unless auto-approve policy applies)
```

Activation is idempotent for the same Telegram user: repeating the flow never creates
duplicate members or duplicate welcome messages. A second Telegram user cannot bind to
a license already bound to another employer. Revoking the license revokes the linked
member's access.

### 4.3 Notification lifecycle

```text
draft ──► queued ──► sending ──► sent
              │          │
              │          ├──► retry_wait ──► queued (backoff)
              │          ├──► failed  (permanent error / attempts exhausted)
              │          └──► unknown result (timeout) — never reported as sent
              └──► cancelled
```

- Creating a notification writes the row and a `notification_send` job with a unique
  `dedupe_key` in one transaction (`ON CONFLICT DO NOTHING`).
- The worker claims jobs with `FOR UPDATE SKIP LOCKED`, marks them `processing`, and
  records a delivery row per attempt.
- Telegram errors are classified:
  - `429`, `5xx`, timeouts, connection errors, `Temporary` → retry with exponential
    backoff (`min(30 * 2^(attempt-1), 3600)`), up to `JOB_MAX_ATTEMPTS`.
  - `Permanent` (blocked bot, bad chat, malformed request) → fail immediately.
  - **Unknown result** (timeout after the request may have reached Telegram): the
    delivery is marked `unknown`, no automatic retry is scheduled (to avoid duplicate
    messages), and the notification is never reported as `sent`. An admin can explicitly
    retry after verifying.
- Cancelling removes pending jobs; a notification already delivered is not deleted.
- When a project is disabled, pending notification jobs and payment reminders are
  cancelled.

### 4.4 Worker durability

- Jobs live in `scheduled_jobs` with `status`, `run_at`, `attempts`, `dedupe_key`,
  `locked_at`, `locked_by`.
- Claims use a single `UPDATE … WHERE id IN (SELECT … FOR UPDATE SKIP LOCKED)` statement,
  so two workers never process the same job.
- A heartbeat row (`system_state:worker_heartbeat`) is refreshed periodically; the admin
  panel reports online/offline/unknown from it.
- On startup and periodically, the worker recovers jobs stuck in `processing` beyond
  `WORKER_STALE_SECONDS` and returns them to `pending`.
- Worker exit at any point is safe: uncommitted claims roll back, committed claims are
  recovered by the stale window.

### 4.5 Payment reminders

- Payments store `unpaid` / `paid` / `cancelled`. **Overdue is computed** from `due_at`
  and the current time; it is never stored.
- On create/update of an unpaid payment, a `payment_reminder` job is scheduled at
  `due_at − PAYMENT_REMINDER_DAYS_BEFORE` (or `now + 1 minute` when already overdue),
  deduplicated per payment and reminder date.
- Paying or cancelling a payment cancels its reminder jobs.
- The reminder handler re-checks the payment status at execution time: settled/cancelled
  payments never receive a reminder, even if a stale job exists.
- Financial status and message delivery status are independent; a failed reminder does
  not change the payment status.

## 5. Capability plugins (feature registry)

`app/features/` is the single source of truth for employer-facing capabilities. A
capability is a `FeatureDefinition` plus an optional handler; the menu, the API
catalog and the admin toggles are all derived from the registry.

| Key | Persian label | Implemented | Callback |
| --- | --- | --- | --- |
| `announcements` | اطلاعیه های من | yes | `<n>:ann` |
| `financial` | اطلاعیه های مالی | yes | `<n>:fin` |
| `support` | پشتیبانی و تیکت | yes | `<n>:tickets` |
| `performance` | گزارش عملکرد | no (`به زودی`) | `<n>:soon:performance` |
| `progress` | پیشرفت پروژه | no (`به زودی`) | `<n>:soon:progress` |

### Adding a capability without touching the core

1. create `app/features/<name>.py`;
2. define `FEATURE = FeatureDefinition(key=..., label=..., action=...)`;
3. write `def handle(ctx: FeatureContext) -> None`;
4. import the module in `app/features/__init__.py`.

`project_features.key` is a plain string and `project_features.settings` is JSONB, so
no migration is required. `GET /api/v1/features` returns the catalog and the project
page renders a toggle per entry automatically; `GET /api/v1/projects/{id}` reports the
per-project flags. A defined-but-unimplemented capability answers with an explicit
"به زودی" message and is labeled `implemented: false` in the panel, so it can never
masquerade as working software.

The example in the original request (an invoice generator for one project) fits this
shape: register `invoice`, store its numbering/prefix in `settings`, and render a PDF in
the handler. Nothing in the dispatcher, menu builder or admin UI has to change.

## 6. Channel abstraction (Telegram, Bale, Eitaa, SMS.ir)

Delivery is provider-agnostic:

```
NotificationService.deliver
  └── ChannelAdapter (Protocol)      app/adapters/messaging/base.py
        ├── TelegramChannelAdapter   wraps app.adapters.telegram (mock/http)
        ├── BaleAdapter              Telegram-compatible Bot API
        ├── EitaaAdapter             Telegram-compatible Bot API
        └── SmsIrAdapter             sms.ir v1 JSON API, plain text only
```

- Providers are configured **once** for the agency through environment variables. The
  panel never stores credentials; `ProjectChannel` stores only per-project enablement
  and a small whitelisted `settings` JSON (signature/template hints).
- `channel_catalog()` reports honest state (`configured`, `mode`), and the API refuses to
  enable a channel that is not configured on the server.
- Error taxonomy is uniform: temporary errors retry with backoff, permanent errors fail
  the notification, and unknown outcomes (timeouts, transport failures) are recorded as
  `unknown` and **never** retried automatically and never reported as success.
- Each attempt row stores `channel` + `recipient`, so multi-channel fan-out is auditable
  per destination. Telegram-compatible providers receive the HTML subset; SMS receives
  plain text.
- Non-Telegram destinations live in `member_channel_identities` (one row per member and
  provider), managed by the admin.

## 7. Telegram callback safety

- Callback data is limited to 64 bytes and contains no secrets or database ids:
  - `p:<index>` — pick a project from the user's authorized projects
  - `<n>:ann`, `<n>:fin` — authorized views for project index `n`
  - `<n>:tickets` — ticket list
  - `<n>:ticket:<ordinal>` / `<n>:treply:<ordinal>` — an item of *that employer's own*
    ticket list; the ordinal is re-resolved server-side and cannot address another user
  - `<n>:soon:<feature>` — placeholder message
  - `h` — re-send the menu
- Multi-step ticket input (subject, body, reply) uses `telegram_conversations`, keyed by
  user + project, so the target ticket id never travels through Telegram.
- The project/ticket index is resolved against the member's own authorized rows on every
  callback; a foreign or stale index gets a neutral error message.
- Every callback re-checks project status, archive flag, license state and membership.

## 8. Admin panel

- Next.js App Router, all routes client-rendered behind an auth provider; no private
  data is server-rendered into HTML.
- API access goes through a typed client with `credentials: same-origin`, `cache:
  no-store`, CSRF header on mutations and a global 401 handler.
- RTL layout with Vazirmatn, dark-first palette, responsive sidebar/bottom navigation.
- Persian dates via `Intl` (`fa-IR-u-ca-persian`, `Asia/Tehran`) and amounts formatted
  with explicit currency.
- Every mutation uses optimistic UI only for loading state, never for results: the UI
  shows values returned by the server and refetches after mutations.
- The service worker caches only static shell assets and an offline page. It never
  intercepts `/api/`. Offline actions are impossible and stated as such.
- Ticket workspace: inbox + thread view, reply, close/reopen, status filters and unread
  counters. The same component is reused on the project page scoped by project id.
- Project page tabs: overview, license, members, notifications, payments, support,
  capabilities/channels, activity. Capabilities and channels are toggles driven by API
  catalogs; archive/restore and permanent deletion live there with an explicit
  type-the-name confirmation and a two-step (archive first) guard.

## 9. Decisions and trade-offs

| Decision | Reason |
| --- | --- |
| Single central bot | One token to manage; per-project isolation enforced in the database, not by separate bots |
| License code + keyed hash | Codes must be verifiable without storing plaintext; shown once at issue time |
| DB-backed queue | No extra infrastructure; transactional consistency with notifications |
| `FOR UPDATE SKIP LOCKED` | Correct multi-worker claiming without duplicates |
| Overdue computed | Avoids stale derived state and background flips |
| Callback index instead of UUIDs | Short payloads; authorization is re-derived server-side |
| No API caching in the PWA | Prevents private project/financial data leaking through caches |
| One active employer per project (v1) | Simpler access model; schema already supports multiple members |

## 10. Scaling notes

- The API is stateless except for the in-memory rate limiter. Before horizontal scaling,
  move rate limits (and any future cache) to a shared store such as Redis.
- The worker can run multiple replicas thanks to `SKIP LOCKED`; keep
  `WORKER_STALE_SECONDS` comfortably above the longest expected request.
- PostgreSQL is the only stateful dependency. Use managed backups and monitor the
  `scheduled_jobs` table (pending/failed counts are exposed at `/api/v1/system/status`).
- Telegram rate limits are global per bot: keep `WORKER_BATCH_SIZE` modest and rely on
  429 handling with `retry_after`.
