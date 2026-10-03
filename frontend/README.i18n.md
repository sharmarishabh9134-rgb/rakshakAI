# Internationalization

The frontend locale catalogs live in `frontend/locales/`. `frontend/src/i18n/index.tsx` owns the language registry, active catalog set, persisted preference, document `lang`/`dir`, and the `useI18n()` translation hook. Components should render user-facing copy through `t('namespace.key')`; English is the fallback catalog. Keep stable identifiers (risk codes, API fields, analytics values) independent of translated labels.

English (`en`), Hindi (`hi`), and Kannada (`kn`) are active. Tamil (`ta`), Telugu (`te`), Marathi (`mr`), Bengali (`bn`), Malayalam (`ml`), Gujarati (`gu`), and Punjabi (`pa`) are registered for future catalog work. To activate a language, add its locale JSON, import it into the catalog map, and add its code to `ACTIVE_LANGUAGES` only after the safety copy has been reviewed.

The selected language is saved in browser storage for signed-out sessions and in `users.preferred_language` for signed-in accounts. The backend accepts the language code on analysis endpoints and uses the account preference when a request omits it. AI provider adapters should use the same language parameter for all user-facing explanation, indicator names, verification steps, and disclaimers. Risk values remain `HIGH`, `MODERATE`, `LOW`, and `UNKNOWN` in storage and API logic; translate only their presentation labels.

Set `document.documentElement.dir` from the language registry. Use logical CSS properties (`margin-inline`, `padding-inline`, `inset-inline`, `text-align: start/end`) for new layout rules so a future RTL locale does not need structural rewrites.
