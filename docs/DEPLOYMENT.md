# Deployment

Run the API behind TLS with a PostgreSQL `DATABASE_URL`, strong `JWT_SECRET`, restricted `FRONTEND_ORIGINS`, backups, and a managed secret store. Set the frontend's `NEXT_PUBLIC_API_URL` to the public backend origin at build time. If enabling the Gemini assistant, set `GEMINI_API_KEY` and optionally `GEMINI_MODEL` in backend-only secret/environment settings; never expose the key through a `NEXT_PUBLIC_*` variable. The chat assistant sends submitted questions and recent chat context to Google Gemini, so publish an appropriate privacy notice and review provider terms before accepting real user data.

Before serving production traffic, add secure cookie sessions, shared rate limiting, monitoring, retention and deletion processes, and a security/privacy review. The checked-in SQLite database and compose credentials are local-demo conveniences, not production configuration.
