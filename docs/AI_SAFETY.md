# AI safety and limitations

## What the system does

The message and URL risk analyzer uses deterministic pattern rules. It reports matching indicators and general verification steps; it is not a trained fraud classifier, legal authority, or live registry lookup. A high-risk result is a reason to pause and verify, not proof that a person or organization committed fraud.

The optional conversational assistant uses Google Gemini through a backend-only integration when `GEMINI_API_KEY` is configured. The backend sends the current question and recent chat context to Gemini to generate a response. RakshakAI does not add those chat turns to its analysis history. Do not enter sensitive personal or financial information. If the provider is unavailable, the API returns a fixed safety fallback.

## Safety boundaries

- No personalized investment, tax, or legal advice; no buy, sell, or hold recommendations; and no stock or return predictions.
- The assistant must not ask users for OTPs, PINs, passwords, card details, or bank credentials.
- Treat submitted messages and documents as untrusted input. Provider output is screened by an application-level safety filter, but automated screening is not a guarantee that every response is correct or safe.
- Direct users to official sources for verification. For suspected ongoing cyber financial fraud in India, advise contacting 1930 promptly; use 112 for immediate emergencies.
- Translated safety guidance should be reviewed by fluent human reviewers before it is presented as authoritative.
