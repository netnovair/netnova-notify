# Security policy

NetNova Notify handles employer identities, project information and payment records.
Please treat security reports as confidential.

## Supported versions

The `main` branch and the latest deployed release receive security fixes. Older commits
are not supported.

| Version | Supported |
| --- | --- |
| `main` (latest) | Yes |
| Older commits / forks | No |

## Reporting a vulnerability

**Do not open a public GitHub issue for a vulnerability.**

Report privately to the NetNova maintainers through the private security contact
configured for this repository/organization (for example the organization security
mailbox). If you do not have that channel, contact the repository owner directly and ask
for a secure reporting address before sending details.

Please include:

- a description of the issue and the affected component (API, worker, bot, panel, infra);
- reproduction steps or a proof of concept (without real tokens, license codes or
  personal data);
- the commit/version you tested;
- the potential impact and any suggested fix.

**Never include** real bot tokens, session cookies, license codes, employer Telegram
IDs, passwords or production database dumps in a report, issue, pull request or chat.

## What to expect

- Acknowledgement as soon as practical (best effort; this is a small team).
- An assessment and, when confirmed, a fix in a private branch and a release.
- Credit in the advisory if you wish, after the fix is deployed.

Please allow reasonable time for remediation before public disclosure. We will
coordinate disclosure with you.

## Out of scope

- Findings that require a compromised admin session, leaked bot token or physical access
  to the server.
- Missing hardening that is already documented as an operational responsibility
  (TLS termination, database network isolation, backups, host patching).
- Spam/abuse of the Telegram bot that does not bypass the license/activation controls.
- Reports from automated scanners without a demonstrated, realistic impact.
- Denial of service through extremely high request volume.

## Security-relevant behaviour

The implemented controls and known limitations are documented in
[docs/security.md](docs/security.md). Highlights:

- Argon2id password hashing, hashed session tokens, CSRF tokens, origin checks,
  rate-limited login/activation.
- License codes are stored only as a keyed HMAC; the raw code is shown once.
- Telegram webhook secret validation and `update_id` deduplication.
- Durable job queue with duplicate-safe claims; ambiguous Telegram timeouts are never
  reported as delivered.
- API responses are `no-store`; the service worker never caches `/api/`.
- Production refuses to start with placeholder secrets or insecure cookies.

## Safe harbour

We will not pursue legal action against researchers who act in good faith, avoid privacy
violations and service disruption, and follow this policy.
