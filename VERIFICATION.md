# Verification

Verified on Windows with Python 3.13.15 and SQLite, using isolated temporary databases for automated checks.

## Automated suite
Eight integration tests pass:
1. Protected routes, valid/invalid login, CSRF (including malformed tokens), logout, and security headers.
2. Idempotent seed (10 patients, 15 cases), all application pages, missing-record 404s, and foreign-key integrity.
3. Patient create/read/edit/delete, normalized duplicate detection, literal search, and non-reused IDs.
4. Patient validation and HTML escaping.
5. Case creation/history/report, case edit and closure, appended vitals, and patient deletion cascade.
6. Invalid/non-finite vitals rejected without partially saved cases.
7. Database-level rejection of vitals linked to the wrong patient.
8. Persistent login-attempt throttling.

## Live browser checks
- Started the app using Waitress at localhost:5000.
- Signed in with the demo account; dashboard displayed 10 patients, 15 cases and 10 active cases.
- Searched Ravi and opened the correct patient with two historical consultations.
- Opened the structured case form and inspected its 390px mobile layout; no document-width overflow.
- Inspected the desktop dashboard and case report visually.
- Checked browser warning/error logs: none reported during these checks.

The print action uses standard `window.print()` and A4 print CSS. The embedded preview did not display an operating-system print dialog, so a completed physical print/PDF export was not verified there. Use a full browser as described in README. No public deployment or real patient-data validation is claimed.

## Google sign-in update
Six additional tests cover registered-account recovery, verified/authoritative email requirements, stable Google identity binding, CSRF-protected initiation, state/nonce/PKCE generation, rejection of forged OAuth state, provider failures, cancellation and missing credentials. Fourteen total tests now pass. Provider responses are mocked; no live Google exchange was possible without the app owner's OAuth credentials. Setup is documented in `GOOGLE_SIGN_IN.md`.
