# SANGYAN hackathon brief

RAKSHAKAI is a public-good investor resilience prototype aligned with Track A (Digital Fraud & Scam Resilience), with supporting investor awareness, education, and financial-content literacy journeys. It is not a trading or investment recommendation product.

## Five-minute demo

1. Register and sign in with a synthetic account; show the protected dashboard.
2. Analyze the synthetic text `Guaranteed 30% monthly return. SEBI registered advisor. Limited slots. Send payment immediately.`
3. Explain the detected text-pattern indicators and why they are not proof of fraud. Point to independent verification steps.
4. Switch the interface to Hindi and use speech playback. Browser speech support varies by device and language.
5. Analyze the bundled synthetic WhatsApp screenshot. Explain OCR availability and the temporary handling of the file.
6. Complete the Guaranteed Returns lesson quiz; show saved progress.
7. Open Emergency Help and Recovery guidance. Show 1930, the National Cyber Crime Reporting Portal, SEBI/SCORES for eligible securities grievances, and 112 for immediate emergencies.

Do not demo with real private messages, credentials, personal identifiers, or financial records. All examples must be synthetic.

## Ten-slide pitch

1. The problem: fraud pressure and complex financial content reach first-time investors.
2. Target persona: a Tier-2/3 investor who needs an understandable second look.
3. Product promise: verify before you trust; indicators with uncertainty, not verdicts.
4. Main journey: submit, extract, identify patterns, explain, verify, learn, recover.
5. Live prototype: message and screenshot analysis, multilingual interface, voice playback, and the Gemini safety assistant when its backend key is configured.
6. Trust boundaries: no investment advice, no fabricated verification, no private-channel scraping.
7. Recovery: preserve evidence and reach official cybercrime, regulator, and emergency channels.
8. Technical architecture: Next.js client, FastAPI service, SQL database, modular OCR and AI adapters.
9. Bharat-first design: English, Hindi, Kannada, responsive layouts, low-bandwidth direction.
10. Roadmap: independent evaluation, verified source refresh process, secure reset delivery, accessibility and language validation, deployment hardening.

## Demonstrated vs planned

Pattern analysis is local and heuristic. It does not check SEBI registration, discover the owner of a URL, verify a live claim, classify content with a trained model, or confirm fraud. The conversational assistant is a separate Gemini-backed feature and requires a backend API key; it provides general information and may be unavailable. OCR depends on local Tesseract configuration. WhatsApp and Telegram screens are examples, not active messaging integrations. Password-reset delivery is not configured. Explain these limits during judging.
