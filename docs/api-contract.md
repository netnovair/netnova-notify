# API contract

Base path: `/api/v1` (the Next.js server also proxies `/api/v1/*`).
Interactive schema (development only): `GET /api/docs` (Swagger UI) and
`GET /api/openapi.json`. They are disabled when `ENVIRONMENT=production`.

All timestamps are ISO-8601 UTC with a `Z`/offset; the UI converts them to
`Asia/Tehran` and the Persian calendar for display. Naive timestamps sent by a client
are interpreted as Tehran local time.

## 1. Authentication

Admin endpoints require the session cookie `nn_session`.

| Endpoint | Auth | Notes |
| --- | --- | --- |
| `POST /auth/login` | public + Origin check + rate limit | Returns admin, `csrf_token`, `expires_at`; sets `nn_session` |
| `GET /auth/me` | session | Returns the current session and CSRF token |
| `POST /auth/logout` | session + CSRF | Revokes the session and clears the cookie |
| `GET /auth/bootstrap-status` | public | `{"admin_configured": true}` so the UI can explain first-run setup |

Session cookie attributes: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` = session TTL,
`Secure` when `COOKIE_SECURE=true`.

**Development preview fallback (never active in staging/production):** in
`ENVIRONMENT=development` the login response also contains `dev_session_token`, and a
development request served over HTTPS gets the cookie as
`SameSite=None; Secure; Partitioned`. The panel keeps that token in memory,
`sessionStorage` and `window.name`, and sends it as both `Authorization: Bearer` and
`X-NN-Session`, because browsers may block third-party cookies inside the preview
iframe and proxies may strip the standard header. The API accepts a header-only session
only when `ENVIRONMENT=development` and only after the cookie lookup fails (so a stale
cookie cannot mask a valid token). Production and test environments return
`dev_session_token: null` and reject header-only sessions. CSRF is still enforced for
every non-GET request.

**CSRF:** every non-GET request must include `X-CSRF-Token` with the value returned by
login or `/auth/me`. Missing/invalid tokens return `403 csrf_failed`.

**Origin check:** login (and other unauthenticated browser-facing POSTs) rejects a
foreign `Origin` with `403 forbidden`, unless it exactly matches `CORS_ORIGINS`,
`NEXT_PUBLIC_SITE_URL` or the development-only `DEV_PREVIEW_ORIGIN_REGEX`.

**Rate limits (per minute, per client IP):**

| Endpoint | Limit | Env var |
| --- | --- | --- |
| `POST /auth/login` | 10 | `LOGIN_RATE_LIMIT` |
| `POST /licenses/activate` | 10 | `ACTIVATION_RATE_LIMIT` |
| Telegram webhook (per chat) | internal limiter | — |

Exceeding a limit returns `429 rate_limited` with `Retry-After`.

## 2. Errors

```json
{
  "error": {
    "code": "invalid_license",
    "message": "کد لایسنس معتبر نیست.",
    "details": { "...": "optional" }
  }
}
```

| Status | Common codes |
| --- | --- |
| 400 | `bad_request`, `invalid_license`, `license_revoked`, `license_expired`, `project_inactive`, `invalid_update` |
| 401 | `unauthorized`, `invalid_credentials` |
| 403 | `forbidden`, `csrf_failed` |
| 404 | `not_found` |
| 409 | `conflict`, `slug_taken`, `invalid_expiry`, `license_already_used` |
| 422 | `validation_error` (Pydantic details) |
| 429 | `rate_limited` |
| 500 | `internal_error` (no stack traces or secrets) |

## 3. Pagination

List endpoints return:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0 }
```

`page` starts at 1, `page_size` is 1–100 (default 20).

## 4. Endpoints

### Auth

`POST /auth/login`

```json
{ "email": "admin@netnova.ir", "password": "••••••••" }
```

```json
{
  "admin": { "id": "uuid", "email": "admin@netnova.ir", "display_name": "مدیر", "last_login_at": "..." },
  "csrf_token": "...",
  "expires_at": "2026-10-20T02:00:00Z"
}
```

`GET /auth/me` → the same `SessionOut` shape.

### Dashboard

`GET /dashboard`

```json
{
  "projects_total": 2,
  "projects_active": 2,
  "notifications_total": 1,
  "queued_notifications": 1,
  "failed_notifications": 0,
  "open_payments": 1,
  "open_payments_amount_by_currency": { "IRT": 5000000 },
  "pending_members": 0,
  "license_attention": 0,
  "recent_activity": [ /* AuditLog */ ],
  "generated_at": "..."
}
```

All values are computed from the database at request time. `license_attention` counts
live licenses expiring within 14 days.

### System

`GET /system/status`

```json
{
  "environment": "production",
  "server_time": "...",
  "database": { "status": "ok", "dialect": "postgresql", "latency_ms": 1 },
  "worker": { "status": "online", "last_seen_at": "...", "hostname": "worker-1" },
  "telegram": {
    "mode": "http",
    "bot_configured": true,
    "webhook_secret_configured": true,
    "last_update_at": "...",
    "webhook_path": "/api/v1/telegram/webhook"
  },
  "timezone": "Asia/Tehran",
  "payment_reminder_days_before": 3,
  "session_ttl_hours": 12,
  "https_required": true,
  "site_url": "https://notify.example.com",
  "pending_jobs": 0,
  "failed_jobs": 0
}
```

Never contains tokens or secrets; `bot_configured` is a boolean only.

`GET /health/live` → `{"status": "ok"}`
`GET /health/ready` → database readiness; `503` when the database is unreachable.

### Projects

| Method | Path | Description |
| --- | --- | --- |
| GET | `/projects?search&status&include_archived&page&page_size` | List, `status` = `active`/`inactive`; archived hidden unless requested |
| POST | `/projects` | Create; response includes `license_code` **once** |
| GET | `/projects/{id}` | Detail with features, channels, license, members, counts |
| PATCH | `/projects/{id}` | Name, client, description, `status`, `features` |
| POST | `/projects/{id}/archive` | Archive: stops bot/sends/reminders, sets `status` to `inactive` |
| POST | `/projects/{id}/restore` | Restore from archive (sets `active`) |
| DELETE | `/projects/{id}?confirm=<exact name>` | Permanent deletion; `422` if the name does not match |
| GET | `/projects/{id}/features` | Registry catalog + per-project flags |
| PUT | `/projects/{id}/features` | `{ "features": { "<key>": true/false } }` |
| PUT | `/projects/{id}/channels/{channel}` | `{ "enabled": true, "settings": {...} }` |
| POST | `/projects/demo-purge?confirm=DEMO` | Delete every `is_demo` project (development/demo data) |

`POST /projects`

```json
{
  "name": "فروشگاه آرمان",
  "client_name": "آرمان تجارت",
  "slug": "arman-shop",
  "description": "optional",
  "features": { "announcements": true, "financial": true }
}
```

- `slug` is optional; a unique slug is generated when omitted.
- Unknown feature keys → `422`.
- Creating a project issues a license in the same transaction; the raw code is returned
  only here (`license_code`) and never again.
- Setting `status` to `inactive` cancels pending notification jobs and payment reminders
  for the project and blocks employer access.

### Capability and channel catalogs

| Method | Path | Description |
| --- | --- | --- |
| GET | `/features` | Feature plugin catalog (`implemented`, `default_enabled`, `action`) |
| GET | `/channels` | Provider catalog with `configured`/`mode` (never secrets) |

### Tickets (two-way support)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/tickets?status&project_id&page&page_size` | Inbox, newest activity first |
| GET | `/tickets/{id}` | Thread; marks the admin side as read |
| POST | `/tickets` | Admin opens a ticket for a project (`project_id`, `subject`, `body`, `priority`) |
| POST | `/tickets/{id}/reply` | `{ "body": "..." }`; status becomes `pending_employer` |
| PATCH | `/tickets/{id}/status` | `{ "status": "open|pending_admin|pending_employer|closed" }` |

Statuses: `open`, `pending_admin` (employer waiting), `pending_employer` (admin replied),
`closed`. A reply to a closed ticket reopens it. An admin reply queues a short Telegram
notice for the employer; an employer message queues a notice for `ADMIN_TELEGRAM_CHAT_ID`.
Neither notice contains the full thread.

### Service catalog and orders

| Method | Path | Description |
| --- | --- | --- |
| GET | `/catalog` | Full tree (inactive included) + `seeded` + `public_categories` |
| POST | `/catalog/seed` | Install the default catalog once; never overwrites an existing one |
| POST | `/catalog/categories` | Create a main service |
| PATCH | `/catalog/categories/{id}` | Update title, emoji, description, order, flags, portfolio text/url |
| DELETE | `/catalog/categories/{id}` | `409 category_in_use` once orders reference it |
| POST | `/catalog/categories/{id}/items` | Create a sub service with its questions |
| PATCH | `/catalog/items/{id}` | Update a sub service; `questions` replaces the list when present |
| DELETE | `/catalog/items/{id}` | `409 item_in_use` once orders reference it |

```json
{
  "title": "طراحی کارت ویزیت",
  "description": "کارت ویزیت با فایل آماده چاپ.",
  "is_active": true,
  "show_portfolio": true,
  "portfolio_text": "نمونه کارها ...",
  "portfolio_url": "https://example.com/samples/card.jpg",
  "questions": [
    { "label": "کارت افقی باشد یا عمودی؟", "field_type": "choice",
      "options": ["افقی", "عمودی"], "required": true },
    { "label": "توضیحات تکمیلی", "field_type": "long_text", "required": false }
  ]
}
```

`field_type` is one of `text`, `long_text`, `number`, `choice`, `phone`. Choice
questions need at least two options; `number` accepts optional `min_value`/`max_value`.
`portfolio_url` must be `https://` or empty — the bot hands the URL to Telegram
(`sendPhoto`), the API never proxies or stores the image.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/orders?status&search&page&page_size` | Pre-sales order inbox, newest first |
| GET | `/orders/counters` | Count per status + `total` |
| GET | `/orders/{id}` | Full answers snapshot, contact, admin note |
| PATCH | `/orders/{id}` | `{ "status": "...", "admin_note": "..." }` |

Statuses: `new`, `contacted`, `quoted`, `won`, `lost`, `cancelled`. Answers are stored
as a JSON snapshot (`key`, `label`, `value`) so editing the catalog never rewrites
history. `contact_phone` is normalised to `09xxxxxxxxx` before storage.

### Admins

| Method | Path | Description |
| --- | --- | --- |
| GET | `/admins` | List admin users |
| POST | `/admins` | Create (`email`, `display_name`, `password`, min 10 chars) |
| PATCH | `/admins/{id}` | `display_name`, `is_active`; cannot deactivate self or the last active admin |
| POST | `/admins/me/password` | `{ current_password, new_password }`; revokes other sessions |
| POST | `/admins/{id}/reset-password` | `{ confirm_email }`; returns a one-time temporary password and revokes sessions |

### Licenses

| Method | Path | Description |
| --- | --- | --- |
| GET | `/licenses?status&page&page_size` | All licenses with `project_name` |
| GET | `/projects/{id}/licenses` | License history for one project |
| POST | `/projects/{id}/licenses` | Issue a new license (revokes the live one) |
| GET | `/projects/{id}/license` | Current live license |
| POST | `/licenses/{id}/revoke` | Revoke a license and its members' access |
| POST | `/licenses/activate` | **Bot-secret protected** activation request |

`POST /projects/{id}/licenses` body: `{ "expires_at": "2027-10-19T23:59:00Z" }` or `null`
for no expiry. Expiry must be in the future (`409 invalid_expiry`).

Response `201` includes `code` (raw, once). Other responses only include `code_prefix`.

`POST /licenses/activate` (called by the bot service, not the browser) requires
`X-Telegram-Bot-Api-Secret-Token` and:

```json
{
  "code": "NN-XXXX-XXXX-XXXX-XXXX",
  "telegram_id": 123456789,
  "username": "employer",
  "first_name": "کارفرما"
}
```

```json
{
  "status": "pending_approval",
  "project_id": "uuid",
  "project_name": "فروشگاه آرمان",
  "requires_approval": true
}
```

Error codes: `invalid_license`, `license_expired`, `license_revoked`,
`project_inactive`, `license_already_used`, `rate_limited`.

### Members

| Method | Path | Description |
| --- | --- | --- |
| GET | `/projects/{id}/members` | Pending, active and revoked members |
| POST | `/projects/{id}/members/{member_id}/approve` | Approve activation; queues welcome message |
| POST | `/projects/{id}/members/{member_id}/revoke` | Revoke access (license unchanged) |
| GET | `/projects/{id}/members/{member_id}/channels` | Non-Telegram destinations of a member |
| PUT | `/projects/{id}/members/{member_id}/channels/{channel}` | `{ "external_id": "chat id or 09xxxxxxxxx", "label": "..." }` |
| DELETE | `/projects/{id}/members/{member_id}/channels/{channel}` | Remove a destination |

`channel` must be one of `bale`, `eitaa`, `smsir`. Telegram is resolved from the bot
identity and is rejected here. Destinations are unique across the whole system, so the
same phone number cannot silently belong to two employers.

### Notifications

| Method | Path | Description |
| --- | --- | --- |
| GET | `/notifications?status&project_id&page&page_size` | Global history |
| GET | `/projects/{id}/notifications?status&page&page_size` | Project history |
| POST | `/projects/{id}/notifications` | Create and queue |
| GET | `/notifications/{id}` | Detail + delivery attempts |
| POST | `/notifications/{id}/send` | Send now / retry |
| POST | `/notifications/{id}/cancel` | Cancel queued notification |
| GET | `/notifications/{id}/deliveries` | Delivery attempts only |

Create body:

```json
{
  "type": "announcement | financial | system",
  "title": "عنوان",
  "body": "متن",
  "scheduled_at": "2026-10-20T09:00:00Z",
  "channels": ["telegram", "smsir"]
}
```

- `channels` defaults to `["telegram"]`; every requested channel must be enabled for the
  project, otherwise the API answers `409`. The worker contacts each recipient on the
  intersection of requested channels, project enablement and configured providers.
  Different channels can carry the same notification in parallel; per-destination outcome
  is stored in `deliveries[]` with `channel` and `recipient`.

- `scheduled_at` omitted/`null` ⇒ send as soon as possible.
- If no approved employer exists yet, the notification is still queued and the worker
  later marks it `failed` with an explicit reason («کارفرمای متصل و تاییدشده ای ...»).
  It is never reported as sent, and no synthetic recipient is invented.
- Sending to a disabled project is blocked (`409` on create) or failed by the worker if
  the project is disabled after queueing; both paths are audited.

Notification fields: `status` (`draft`, `queued`, `sending`, `sent`, `failed`,
`retry_wait`, `cancelled`), `attempt_count`, `last_error`, `telegram_message_id`,
`deliveries[]` (`status` = `pending|sending|sent|failed|unknown`, `channel`, `recipient`,
`is_mock`, `error`).

Status is **message delivery** status, independent of payment status.

### Payments

| Method | Path | Description |
| --- | --- | --- |
| GET | `/payments?project_id&status&page&page_size` | Global list with `project_name`, `next_reminder_at` |
| GET | `/projects/{id}/payments?status&page&page_size` | Project list |
| POST | `/projects/{id}/payments` | Create + schedule reminder |
| PATCH | `/payments/{id}` | Edit unpaid payment (settled rows are immutable) |
| POST | `/payments/{id}/mark-paid` | Mark settled, cancel reminders |
| POST | `/payments/{id}/cancel` | Cancel, cancel reminders |

Create/update body:

```json
{
  "title": "پرداخت مرحله اول",
  "amount_minor": 5000000,
  "currency": "IRT",
  "due_at": "2026-11-01T20:30:00Z",
  "notes": "optional"
}
```

- `amount_minor` is an integer in the currency's smallest unit: IRR/IRT `1`, USD/EUR
  `1/100`. The UI converts major units before sending.
- `currency` ∈ `IRR`, `IRT`, `USD`, `EUR`; there is no implicit default conversion.
- `is_overdue` is computed (`status = unpaid` and `due_at < now`), never stored.
- Reminders are scheduled at `due_at − PAYMENT_REMINDER_DAYS_BEFORE`; if that moment has
  passed, `now + 1 minute`. Settled/cancelled payments get no reminders.

### Audit

`GET /projects/{id}/audit-logs?page&page_size` → `Page<AuditLog>`.

```json
{
  "id": "uuid",
  "actor_type": "admin | telegram_user | system",
  "actor_label": "مدیر نت نووا",
  "action": "license.issued",
  "action_label": "صدور لایسنس",
  "entity_type": "license",
  "entity_id": "uuid",
  "project_id": "uuid",
  "context": { "prefix": "NN-AB", "reason": "project_created" },
  "created_at": "..."
}
```

Context never contains raw license codes, session tokens, CSRF tokens or bot tokens.

### Telegram webhook

`POST /telegram/webhook`

- Requires `X-Telegram-Bot-Api-Secret-Token` equal to `TELEGRAM_WEBHOOK_SECRET`
  (constant-time comparison). In production a missing secret is a `503`; a wrong one is
  `403`.
- `update_id` is deduplicated in the database (unique constraint); repeated deliveries
  return `200` without side effects.
- Validates the update structure (`400 invalid_update` for malformed bodies).
- Ignores group/supergroup chats and non-message updates.
- Always answers `200` for accepted updates so Telegram does not retry indefinitely;
  processing errors are logged without secrets.
- This endpoint is **not** for browser use and does not return project data.

## 5. Frontend integration notes

- Use relative URLs (`/api/v1/...`) from the browser; the Next.js rewrite proxies to the
  API. Never call `localhost` from browser code.
- Always send `credentials: "same-origin"` and keep the CSRF token in memory only.
- Send `cache: "no-store"`; responses include `Cache-Control: no-store`.
- On `401`, clear local auth state and go to `/login?next=<current path>`.
- On `403 csrf_failed`, refresh the session (`/auth/me`) and retry once; do not loop.
- Treat `unknown` delivery state as **not sent** in the UI.

## 6. Caching and headers

API responses carry `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive
`Permissions-Policy` and `X-Robots-Tag: noindex, nofollow`.
