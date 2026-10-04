# REST API

OpenAPI documentation is served at `/docs`. Private routes require `Authorization: Bearer <token>`.

| Area | Endpoints | Purpose |
| --- | --- | --- |
| Authentication | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/users/me`, `PATCH /api/users/me/language` | Account and session operations |
| Assistant | `POST /api/assistant/chat` | Authenticated general safety questions; Gemini is called server-side when configured, with a safe JSON fallback on provider failure |
| Analysis | `POST /api/analyze/message`, `/url`, `/image`, `/document` | Message, local URL structure, screenshot, and document analysis |
| History | `GET /api/analysis/history?limit=&offset=&risk=&kind=`, `GET/DELETE /api/analysis/{id}` | Paginated, owner-scoped history; delete is soft |
| Education | `GET /api/education`, `GET /api/education/{slug}`, `POST /api/education/{slug}/quiz-attempt`, `GET /api/education/progress` | Ten maintained lessons, three-question quizzes, saved scores and progress |
| Rights | `GET /api/rights` | Editable general investor-rights guidance |
| Grievance | `GET /api/grievance`, `GET /api/grievance/{slug}` | Issue categories, relevant information, general steps, and official-channel guidance |
| Feedback | `POST /api/feedback` | Authenticated feedback submission |
| Notifications | `GET /api/notifications`, `PATCH /api/notifications/{id}/read` | User-scoped notifications |
| Admin | `GET /api/admin/overview`, `/audit`, `/feedback`; `PUT /api/admin/guides/{slug}` | Role-protected summaries, audit metadata, feedback, and content updates |
| Demo | `GET /api/demo/examples` | Synthetic examples (`synthetic: true`) |

Image OCR is opt-in with `OCR_PROVIDER=tesseract`; the Docker backend image includes Tesseract and the initial English/Hindi/Kannada language data. Text PDFs use PyMuPDF. Uploads are signature checked, bounded, processed temporarily, and discarded. The analyzer reports when OCR is unavailable and accepts manual text as fallback.

URL inspection does not resolve DNS or make network requests; redirects, live reputation, and registration metadata are reported as unchecked. Private, localhost, link-local, and reserved destinations are rejected.

Grievance content is stored in `grievance_guides` and can be edited by an administrator through the protected API. The assistant provides general guidance only and never claims to file a complaint. Read [SECURITY.md](SECURITY.md) before exposing the API beyond local demo use.
