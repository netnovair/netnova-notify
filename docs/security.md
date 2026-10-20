# Security

This document describes the controls that are implemented, how they are tested, and
what still depends on deployment/operations. It intentionally separates **implemented**
from **recommended** measures.

## 1. Assets

| Asset | Impact if exposed |
| --- | --- |
| Telegram bot token | Full control of the central bot; ability to message all employers |
| License codes | Can bind an attacker to a project (until revoked) |
| Admin session cookie / CSRF token | Full admin access |
| Project, notification and payment data | Privacy and financial confidentiality |
| Employer Telegram IDs | Personal data, targeted abuse |
| `SECRET_KEY` | License hash forgery, session/CSRF integrity |

## 2. Implemented controls

### 2.1 Admin authentication

- Passwords hashed with **Argon2id** (`time_cost=2`, `memory_cost=64 MiB`,
  `parallelism=2`), never logged or returned.
- Session token: `secrets.token_urlsafe(32)`; the database stores only its
  **SHA-256 hash**. Cookies are `HttpOnly`, `SameSite=Lax`, `Path=/`, and `Secure` when
  `COOKIE_SECURE=true`.
- Development previews: when `ENVIRONMENT=development`, `DEV_PREVIEW_ORIGIN_REGEX`
  is set and the request comes from a matching host (`Origin` or
  `X-Forwarded-Host`), the session cookie is issued as
  `SameSite=None; Secure; Partitioned`. Such a page is embedded in another site, so a
  `Lax` cookie would be stored but never sent and the login would bounce back. The
  branch is unreachable in production/test, and CSRF is enforced by the per-session
  token (not by the cookie attribute), so the relaxed `SameSite` does not weaken it.
  If the browser blocks even partitioned cookies, the login response in development
  also carries `dev_session_token`; the panel keeps it in `sessionStorage` and sends
  `Authorization: Bearer` and the custom `X-NN-Session` header (some hosting proxies
  strip the standard header). The API accepts either header only after the cookie
  lookup fails and only when `ENVIRONMENT=development`; production and test return
  `dev_session_token: null` and reject header-only sessions. The token is kept in
  memory, `sessionStorage` and (development builds only) `window.name`, so a reload or
  Fast Refresh cannot silently drop the session; it is re-read on every request. The
  panel verifies the session with `GET /auth/me` before leaving the login page, so a
  browser that stores nothing gets a clear error instead of a redirect loop.
- Session TTL `SESSION_TTL_HOURS` (default 12, max 30 days), enforced server-side;
  expired/revoked sessions are rejected.
- Logout revokes the server-side session and clears the cookie.
- CSRF: every non-GET admin request requires `X-CSRF-Token` equal to the per-session
  token, compared in constant time. Mismatch ⇒ `403 csrf_failed`.
- Origin check on browser-facing POSTs: a foreign `Origin` ⇒ `403 forbidden`.
- Login rate limit: 10/minute per IP (`LOGIN_RATE_LIMIT`), in-process.
- Failed logins are audited (`auth.login_failed`) without the submitted password.
- No public signup. The first admin is created once from environment variables when the
  table is empty. Further admins are created only by an authenticated admin.
- Password change requires the current password, enforces a minimum length and revokes
  every other session of that admin. Admin-initiated reset returns a random temporary
  password exactly once and revokes all sessions of the target admin. Neither path logs
  the password.
- Guard rails: the last active admin cannot be deactivated and nobody can deactivate
  themselves, so the panel cannot lock the agency out.
- `GET /api/v1/auth/bootstrap-status` exposes only a boolean.

### 2.2 License codes

- Format `NN-XXXX-XXXX-XXXX-XXXX`; no ambiguous characters.
- Stored as `HMAC-SHA256(SECRET_KEY, normalized_code)`, 64 hex chars, plus a 5-char
  prefix for display. A database dump alone cannot verify guesses without
  `SECRET_KEY`.
- The raw code is returned **only once**, in the issuing response. Every list/detail
  endpoint serializes only the prefix. No code is written to logs or audit context.
- At most one live license per project (partial unique index); issuing a new one revokes
  the previous one.
- Expiry is enforced server-side; an expired license yields `license_expired`.
- Revoking a license revokes the linked member's access.
- Activation attempts are rate-limited (10/minute per IP, `ACTIVATION_RATE_LIMIT`) and
  audited; invalid attempts return a generic message.

### 2.3 Telegram webhook

- `X-Telegram-Bot-Api-Secret-Token` is compared in constant time with
  `TELEGRAM_WEBHOOK_SECRET`.
- In production a missing secret fails closed (`503 webhook_secret_missing`);
  a wrong/missing header is `403`.
- Updates are deduplicated by `update_id` in the database, so Telegram retries cannot
  cause duplicate activation messages or repeated side effects.
- The payload is validated (`400 invalid_update` for malformed bodies). Unknown update
  types are ignored.
- Group/supergroup chats are ignored; the bot only serves private chats.
- Access is re-checked on every callback: project status, license state and member
  status. Callback payloads carry no secrets, IDs or amounts — only a project index.
- The bot never echoes license codes or tokens.

### 2.4 Authorization (IDOR)

- Every admin route depends on `get_admin_context`; there is no anonymous data route
  except health, login, bootstrap status and the webhook.
- Project-scoped resources are looked up **through the project** (or by a UUID that is
  then scoped); a member/license of another project cannot be operated through the wrong
  project URL.
- Telegram callbacks are authorized against the sender's own memberships; a stale or
  foreign project index yields a neutral error, not another project's data.
- Employer-facing views (announcements, financial) are scoped to the active membership
  and license.

### 2.5 Job queue integrity

- Claims use `FOR UPDATE SKIP LOCKED`; two workers cannot process the same job.
- Unique `dedupe_key` avoids duplicate scheduled messages.
- Delivery attempts are recorded per chat; chats already `sent` are never re-sent.
- Stale `processing` jobs are recovered after `WORKER_STALE_SECONDS`.
- **Timeout/unknown result policy:** an ambiguous Telegram timeout is never retried
  automatically and never reported as `sent`; the delivery is marked `unknown`, the
  notification `failed`, and an admin must verify and retry explicitly.

### 2.6 Data exposure and caching

- All API responses send `Cache-Control: no-store`.
- Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, restrictive `Permissions-Policy`,
  `X-Robots-Tag: noindex, nofollow`; HSTS in production.
- The PWA service worker **never** intercepts `/api/`; it caches only static assets and
  an offline page. Private project/financial data is not persisted offline.
- The Next.js client keeps the CSRF token in memory (not `localStorage`); the session
  cookie is `HttpOnly`, so JavaScript cannot read it.
- Error responses contain no stack traces, SQL or secrets; validation errors are
  normalized by a global handler.

### 2.7 Multi-channel delivery and tickets

- Provider credentials (Telegram, Bale, Eitaa, SMS.ir) exist only in environment
  variables. The panel reads a catalog with `configured: true/false` and never receives
  a token, and `GET /channels` returns no secrets. Enabling a channel that is not
  configured on the server is refused (`409`), so the UI cannot advertise a channel that
  would silently do nothing.
- Per-project `settings` JSON is whitelisted (`sms_template`, `signature`, `reply_to`)
  and length-limited; arbitrary keys are dropped.
- A delivery attempt row is committed before the network call. On a worker restart,
  attempts left in `sending` are marked `unknown` and the notification fails instead of
  being resent, preventing duplicate messages.
- Unknown outcomes are never treated as success and never retried automatically.
- Ticket access is scoped by project membership: the admin endpoints require a session;
  employer replies compare `ticket.member_id` with the caller's own membership before
  writing, and callbacks address tickets by an ordinal re-resolved for that member, never
  by a database id.
- Ticket notifications sent to Telegram contain only a subject and a truncated preview;
  the thread stays in the panel.
- SMS bodies are converted to plain text; Telegram HTML is never sent to SMS providers.

### 2.7.1 Logging

- `SensitiveDataFilter` blocks log records whose text contains `password`,
  `license_code`, `secret` or `bot_token` (defense in depth).
- Application code does not log request bodies, cookies, tokens or full license codes.
- Telegram errors are truncated before storage (`last_error` max 1000 chars).
- Audit context contains safe metadata only.

### 2.8 Configuration hardening

`Settings.validate_runtime()` refuses to start in production when:

- `SECRET_KEY` is a placeholder or shorter than 32 characters;
- `COOKIE_SECURE` is not `true`;
- a real bot token is configured without `TELEGRAM_WEBHOOK_SECRET`;
- `CORS_ORIGINS` contains `*`.

`DEV_PREVIEW_ORIGIN_REGEX` is ignored outside `ENVIRONMENT=development`.

### 2.9 Payments

- Record-and-notify only. No card data, no bank credentials, no gateway callbacks.
- The UI and docs never claim a transaction was verified by a bank.
- Amounts are integers with an explicit currency; overdue is computed, not stored.
- Paid/cancelled payments are immutable for financial fields and receive no reminders.

### 2.10 Dependency and supply chain

- Backend dependencies are pinned in `requirements.txt` / `requirements-dev.txt`;
  frontend uses a committed lockfile (`package-lock.json`) and `npm ci` in CI.
- CI runs lint, type checking, tests and a production build for every change.
- Recommended (not automated here): enable Dependabot, `pip-audit` and `npm audit` in the
  repository settings; review new transitive dependencies before merging.

## 3. Test coverage relevant to security

The pytest suite includes (see `apps/api/tests`):

| Area | Example assertions |
| --- | --- |
| Authentication | wrong password rejected, session required, logout revokes |
| CSRF | mutation without header ⇒ 403; wrong token ⇒ 403 |
| Origin | foreign origin ⇒ 403; trusted/localhost accepted |
| Rate limiting | repeated login attempts ⇒ 429 |
| Webhook | missing/wrong secret ⇒ 403; duplicate `update_id` ⇒ one side effect |
| License | invalid/revoked/expired license rejected; second employer rejected; reissue rebinds safely |
| IDOR | member/license operations scoped to the project; cross-project access fails |
| Queue | duplicate claims impossible; retry/backoff; unknown timeout is not marked sent |
| Payments | settled/cancelled payments get no reminder; reminders cancelled on settle |
| Admins | password change revokes other sessions; weak password rejected; last/self deactivation refused; reset returns a one-time temp password and closes sessions |
| Tickets | employer-only reply checks ownership; closed ticket reopens explicitly; status transitions audited |
| Channels | catalog never reports an unconfigured provider as ready; enabling an unconfigured channel is refused; SMS dispatch uses the member identity; permanent provider error fails without retry |
| Project lifecycle | archive stops the bot; restore re-enables; deletion needs the exact name; demo purge leaves real projects; audit rows survive deletion |
| Headers | `Cache-Control: no-store` on API responses |

Frontend tests assert that private content is not rendered before the session is
confirmed, that login errors are displayed, and that status labels render correctly.

## 4. Deployment requirements (operator)

1. **HTTPS only** in production (`COOKIE_SECURE=true`, HSTS at the proxy). Never expose
   the API or PostgreSQL without TLS/network restrictions.
2. Put PostgreSQL on a private network; use a dedicated least-privilege role.
3. Inject secrets through the process manager or a secret store; never bake them into
   images, compose files committed to Git, or CI logs.
4. Rotate `SECRET_KEY` only with a plan: it invalidates license hashes
   (`code_hash`) and existing sessions. Re-issue licenses after rotation.
5. Rotate the bot token via BotFather if leaked, then update `TELEGRAM_BOT_TOKEN` and
   re-register the webhook with `python -m scripts.set_webhook --url …`.
6. Back up PostgreSQL (`pg_dump`) encrypted, off-host, with tested restores.
7. Restrict admin access by network policy/VPN where possible.
8. Monitor failed logins, webhook errors and `failed_jobs` in `/api/v1/system/status`.
9. Keep the host, Python, Node and PostgreSQL patched.

## 5. Known limitations and residual risks

- **In-memory rate limiting** is per process. With multiple API replicas, limits are
  multiplied. Move to Redis or a reverse-proxy limiter before horizontal scaling.
- Admin accounts have no 2FA and no password change UI. Enforce a strong bootstrap
  password, keep the secret manager authoritative, and rotate by recreating the account
  through an operational procedure.
- The bot secret protects the webhook, but Telegram itself is the trust anchor for
  sender identity. A leaked bot token allows impersonation of the bot — rotate and
  re-register immediately.
- License codes are bearer secrets during delivery. New codes are stored twice: a
  keyed hash for lookup and an AES-GCM ciphertext (`LICENSE_ENCRYPTION_KEY`, intentionally
  separate from `SECRET_KEY`). Losing the encryption key makes codes unreadable but does
  not invalidate them; rotate by reissuing. Legacy hash-only rows have no ciphertext and
  must be reissued before they can be shown. Revealing a code is audited and limited to
  10 requests per minute per administrator.
- The AI advisor receives only the employer's question and a short project context
  (name, status, description). It never receives amounts, license codes, Telegram ids or
  the database. Without a configured key the feature answers «به زودی»; no answer is
  fabricated and provider errors never leak into the chat. A provider outage or timeout
  is reported as `409 advisor_unavailable`, never as a 500 with internals.
- The advisor API key is sent in the `x-goog-api-key` header, not in the query string,
  so it cannot land in a proxy or access log.
- Rich text is sanitized twice (on save and on render) against Telegram's own tag list;
  text that is cut for length never leaves a tag half-open, because Telegram would reject
  the whole message. The panel renders it with a React parser, never
  `dangerouslySetInnerHTML`.
- Admin-authored rich text in a ticket reply is stored as markup but the employer side
  only receives Telegram's allow-listed subset; employer text is always escaped.
- Audit logs are append-only through the API but not cryptographically signed; a
  database administrator can alter them.
- Session fixation is mitigated by creating a new token at login and deleting the old
  session on logout; there is no device management UI.
- No automated vulnerability scanning or dependency audit runs in this repository yet.
- The offline page is static and can be outdated; it never claims cached data is current.

## 6. Reporting a vulnerability

Do not open a public issue with secrets or personal data. Contact NetNova through the
private channel documented in [SECURITY.md](../SECURITY.md), include reproduction steps
and affected versions, and allow reasonable time for a fix before disclosure.

## Appendix: development diagnostics

In `ENVIRONMENT=development` the panel may post a small report to
`POST /api/v1/diagnostics/client` (registered only in development) so a hosted
preview that blocks cookies and storage can be diagnosed from the server log. The
payload is limited to booleans, one HTTP status and the user agent; tokens, cookie
values, URLs and operational data are rejected by `extra="forbid"`. Production never
registers the route.
