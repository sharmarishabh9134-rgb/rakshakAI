# Privacy and data handling

RAKSHAKAI is a hackathon prototype. Do not submit OTPs, UPI PINs, passwords, card PINs, banking credentials, Aadhaar, PAN, private chats, or financial documents containing unnecessary personal information.

## What the prototype stores

- Account email, display name, password hash, and preferred language.
- A short analysis summary, risk label, detected indicator codes and labels, and timestamps, scoped to the account. Submitted message text and quoted evidence are not persisted in analysis history.
- Learning progress, quiz attempts, and administrative audit metadata.
- Upload bytes, extracted text, and upload metadata are not stored.

## Processing boundaries

Message text and uploaded file bytes are processed in memory by the API. OCR availability depends on local configuration. URL analysis inspects the submitted URL string and does not fetch the target. The default analyzer is deterministic pattern matching; no external AI provider is called by default. Optional speech recognition is supplied by the browser and may use browser-vendor services; check the browser’s own privacy settings. A recognized transcript is submitted for analysis automatically when recognition completes.

## User controls and limitations

Users can delete individual analysis records from History. Account deletion is not exposed in this demo. The app uses bearer access tokens stored in browser storage; this is less protective against cross-site scripting than an HttpOnly cookie design. Reset-email delivery and refresh-token rotation are not configured. Do not expose the demo to production traffic without implementing those controls, HTTPS, secrets management, and an operational privacy process.

This is not a legal privacy notice and should be reviewed before any real-world deployment.
