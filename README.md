# RakshakAI

RakshakAI is an investor-safety prototype for reviewing suspicious messages, URLs, screenshots, and documents. It provides informational risk indicators and verification guidance; it does not determine whether something is fraud or give investment advice.

## Quick start

### Backend (Python 3.10+)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs. SQLite is the default for a quick demo. To use PostgreSQL locally, start the database and API together from the repository root with `docker compose up --build -d`; the backend container waits for PostgreSQL, applies Alembic migrations, then serves the API at http://localhost:8000. The database uses a persistent Docker volume. The compose credentials are local-demo defaults; replace them and set a strong `JWT_SECRET` before exposing services.

### Frontend (Node 20+)

```powershell
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in `frontend/.env.local` if the API runs elsewhere. Demo mode is enabled by default and uses synthetic examples.

### Gemini enquiry assistant

The dashboard assistant uses Google’s Gemini `generateContent` REST API from the backend. Set `GEMINI_API_KEY` in the backend process environment and optionally set `GEMINI_MODEL` (default `gemini-3.8-flash`), then restart the API. These variables can be configured in Voroa’s backend service environment. Never set the key in frontend variables. The API retries transient quota/server/network failures with bounded delays and returns a safe, user-friendly fallback if Gemini is unavailable. `/api/health` reports whether a key is configured and which model is selected; it never returns the key. Chat turns remain in browser memory and are not added to RakshakAI analysis history.

## Included

- FastAPI API with password hashing, JWT auth, analysis history/deletion, message and URL analyzers, education, rights, grievance guidance, feedback, and demo content.
- Next.js TypeScript interface with dashboard, message/URL analysis, safety center, education/quiz, rights, grievance, history, privacy, profile/settings and admin pages.
- Verified Platform Checker at `/platforms`, including searchable directory entries, platform details, URL structure verification, manual verification requests, official resources, and admin-only content endpoints (`/api/admin/platforms`). Directory records are stored in `frontend/src/data/platforms.json` and served to the API from `backend/data/official_platforms.json`.
- English, Hindi, Kannada, Marathi, Telugu, and Malayalam language choices with localized navigation, primary analyzer copy, safety findings, and analysis explanations. Browser speech input/output uses matching installed device voices where available.
- Ten database-backed education lessons with three-question quizzes, saved scores and completion progress; grievance and investor-rights content can be updated through admin APIs.
- The message and URL risk analyzer uses local pattern rules. The separate conversational assistant calls Gemini from the backend only when `GEMINI_API_KEY` is configured; chat content is sent to Google for that response and is not added to RakshakAI analysis history. If the provider is unavailable, the API returns a safe fallback.
- Screenshot and scanned-PDF OCR use local Tesseract when enabled. WhatsApp and Telegram pages are educational examples; the application does not connect to private accounts or read conversations.
- Platform and SEBI registry verification is intentionally incomplete while no authoritative live lookup provider is configured. The URL checker does not fetch submitted hosts or follow redirects. Platform examples and directory review dates are not proof of registration, site ownership, app publisher, or current status.

## Safety boundary

Risk describes detected indicators only. It is not a legal determination. Do not enter credentials, OTPs, PINs, or private chat content. Uploaded raw content is not retained by the demo. URL inspection is local and does not fetch the target URL.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SECURITY.md](docs/SECURITY.md), [docs/PRIVACY.md](docs/PRIVACY.md), [docs/API.md](docs/API.md), [docs/AI_SAFETY.md](docs/AI_SAFETY.md), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), [docs/DEMO.md](docs/DEMO.md), and [docs/HACKATHON.md](docs/HACKATHON.md) for the runbook, judging walkthrough, and limits.
