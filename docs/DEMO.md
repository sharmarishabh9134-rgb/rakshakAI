# Five-minute RAKSHAKAI demo

Use invented content only. The sample screenshot at `/demo-whatsapp-screenshot.png` is labeled synthetic and contains no real person, account, phone number, or payment destination.

## Prepare once

1. From the repository root, run `docker compose up --build -d`. This starts PostgreSQL and the backend; startup applies Alembic migrations. The container includes local Tesseract OCR with English, Hindi, and Kannada data.
2. Start the UI in another terminal: `cd frontend; npm install; npm run dev`.
3. Open `http://localhost:3000/register` and create a demo account, then log in. The UI and analysis explanations support English, Hindi, Kannada, Marathi, Telugu, and Malayalam. Speech recognition and spoken playback depend on browser support and installed device language voices; if a matching voice is missing, the written explanation stays available. Review your browser’s speech privacy behavior before dictating sensitive content.

## Live walkthrough (about five minutes)

1. **Login and dashboard (20 sec):** Open `/login`, sign in, and point out that completed lessons, quiz scores, and progress update from saved account data.
2. **Paste analyzer (40 sec):** Open `/analyze`, choose Message, and paste this clearly synthetic example:

   `Guaranteed 30% monthly return. Invest today. Limited slots. Send payment immediately.`

   Click Analyze. Show guaranteed-return language, urgency, pressure, and payment request findings. Explain that indicators are warning signs, not proof of fraud.
3. **Language and voice (30 sec):** Choose Hindi in the site language control and re-analyze, or use the mic and say “Is this investment message safe?” Review transcript before reading its result aloud. Kannada and English are available too. Speech input is never treated as permission to transact.
4. **Screenshot and OCR (45 sec):** Select Screenshot, upload `frontend/public/demo-whatsapp-screenshot.png`, and analyze. The image is synthetic. Show the retained-on-screen original preview, extracted text, highlighted warning phrases, explanation, and safer next steps. If recognition is not available, paste the visible text manually; uploads are discarded after processing.
5. **Education and quiz (60 sec):** Open Investor Education, choose **Guaranteed returns**, read the synthetic example and verification checklist, answer the three quiz questions, submit, and show the score and completed lesson state.
6. **Rights and grievance (45 sec):** Open Investor Rights to show disclosures, records, safe communication, official contact verification, and general grievance process. Open Grievance Guidance, choose a category, and show relevant records, general next steps, and the reminder that RAKSHAKAI does not file complaints.
7. **Privacy and history (30 sec):** Open Privacy Center to explain what the demo stores and does not store. Open History and show that the signed-in analysis metadata is scoped to this account and can be deleted.

All examples are synthetic. Never demo with private WhatsApp/Telegram conversations, OTPs, credentials, or real financial documents. No screen provides trading recommendations.
