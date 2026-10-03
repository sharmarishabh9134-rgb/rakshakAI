# RAKSHAKAI security architecture

## Security boundaries

RAKSHAKAI analyzes only text or files that a user submits to its analyzer. It does not log in to, scrape, or read private WhatsApp or Telegram conversations. WhatsApp Business and Telegram Bot API interfaces are protocols only; no adapter is instantiated until an authorized provider, webhook verification, and deployment secrets are configured. Replies are educational, never trading recommendations.

The message and URL analyzers use local pattern checks. URL analysis does not resolve, request, crawl, or follow the submitted URL. Private networks, localhost, and restricted URL targets are rejected by validation. Live reputation and domain metadata are not queried in the demo.

## Identity and access

- Passwords are hashed with bcrypt and are never included in logs or API responses.
- Authentication uses signed HS256 bearer JWTs with expiration. Configure a unique, randomly generated `JWT_SECRET` of at least 32 characters in production. Production startup rejects the built-in development secret.
- Account, analysis history, progress, quiz attempts, notifications, and feedback endpoints require authentication and scope reads/writes to the authenticated user.
- Admin APIs check the `admin` role; role grants are represented by the `roles` and `user_roles` tables. Provision the first administrator out of band through a trusted database operation.
- Logout clears the client token. The demo does not implement token revocation or refresh tokens.

## Browser and API protections

- CORS uses explicit configured origins and does not allow credentialed cross-origin requests.
- The browser stores the demo bearer token in local storage. API authentication does not use cookies, so CSRF is not used as an authorization mechanism. Production should move sessions to secure, HttpOnly, SameSite cookies and add CSRF protection.
- React renders user-provided text as escaped text. Do not add raw HTML rendering for submitted messages, OCR output, or provider responses.
- SQLAlchemy parameterized statements are used for database access; user content is not interpolated into SQL.
- The API applies content-length request limits, endpoint rate limits, Pydantic validation, and structured error responses. The demo limiter is in-memory and per process; use a shared Redis-backed limiter and edge protections when scaling.
- Responses include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a restrictive API Content Security Policy. HSTS is enabled when `APP_ENV=production`; terminate HTTPS at a trusted proxy and configure forwarded headers deliberately.

## Files and sensitive content

- Uploads accept only PNG, JPEG, WEBP, and PDF after extension, MIME, signature, and size validation. The backend caps file reads, sanitizes the displayed filename, rejects unsupported content, processes bytes in memory, and does not persist upload bytes or extracted text.
- OCR is opt-in through a local Tesseract installation (`OCR_PROVIDER=tesseract`). Treat OCR as untrusted input; recognition can be wrong. If extraction is unavailable, users can paste text manually.
- Never log passwords, JWTs, OTPs, financial credentials, raw message bodies, document contents, or OCR output. Audit entries store action and record metadata only. Server access logs should not be configured to include authorization headers or request bodies.
- Analysis history stores a short generated explanation and indicator categories when a user is signed in; quoted evidence is returned only in the immediate response and is not saved. Users can soft-delete analysis records. Uploaded document metadata model stores only file metadata and hashes, and current upload processing does not write a record.
- The demo does not implement retention scheduling, account deletion, token revocation, password reset, or a formal breach response workflow. Define and operate these before production.

## Secrets and operations

Keep secrets in deployment secret storage or environment configuration. Never commit `.env`, provider credentials, signing keys, or put server secrets in `NEXT_PUBLIC_*` variables. The sample compose password and JWT fallback are for local demonstrations only. Replace them before exposing services to a network.

Alembic owns schema changes. Apply migrations before starting the API (`alembic upgrade head`); the Docker backend service performs this step at startup. Back up PostgreSQL and restrict database network access.

## Before production

Use HTTPS, a managed secret store, production-grade password reset and session revocation, distributed rate limiting, upload sandboxing and malware scanning, retention and deletion jobs, monitoring, backups, security review of any AI/OCR provider, and verified links/content review for official grievance routes. Do not claim to file complaints unless an authorized filing API is implemented and its result is confirmed.
