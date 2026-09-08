# MediCase · SIH26047

A complete local hackathon MVP for patient case documentation. Flask + Jinja + SQLite; one authoritative `patient_case.db`. Includes 10 fictional patients, 15 cases, and 15 vitals readings.

## Run on Windows

Install Python 3.10 or newer, extract the ZIP, and open a terminal in the `MediCase` folder (the folder containing `app.py`).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000 in your browser.

Use Chrome, Edge, Firefox, or Safari for Print / Save PDF. Embedded preview browsers may not open a print dialog.

**Demo login:** `doctor@medicase.demo` / `demo123`

**Google login / forgot password:** implemented for existing care-team accounts. Follow [Google sign-in setup](GOOGLE_SIGN_IN.md) to provide your Google OAuth client credentials and enable the button. The fictional demo email cannot authenticate with Google.

The ZIP includes a seeded database. If starting from source without the database, run this before starting the app:

```powershell
.\.venv\Scripts\python.exe seed.py
```

No activation command is required. Stop the server with Ctrl+C. Internet is needed to install dependencies once. Password login and clinical documentation work locally; optional Google sign-in requires internet access. There are no CDN or external font dependencies.

## macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python seed.py
.venv/bin/python app.py
```

## Features

- Session login/logout, hashed passwords, CSRF on every form, eight-hour sessions, basic persistent login throttling and private-response cache headers.
- Patient creation, editing, confirmed deletion, date-derived age, generated patient IDs, search by full name/ID/phone/blood group.
- Duplicate detection using case-insensitive first/last name, birth date and normalized phone. Family members can share a phone. IDs are allocated within a transaction and are never reused after deletion.
- Structured case history, clinical notes, clinician-entered assessment/care plan, Active/Closed state, case editing, and longitudinal timeline.
- Optional vitals on creation and additional timestamped readings later. Case and vitals creation is atomic. All readings are preserved when editing a case.
- Dashboard statistics and recent activity, reports directory, printable individual reports. Print → Save as PDF downloads a PDF through your browser.
- Server validation with retained input, empty states, helpful 404/error pages, responsive dark UI, keyboard focus and field labels.

## Demo sequence (2–3 minutes)

1. Sign in and show the populated dashboard.
2. Search `Ravi`, open Ravi Kumar, and show his previous consultations.
3. Click New case; record the chief complaint and clinician notes.
4. Enter fictional measurements: 101°F, BP 120/80, pulse 82, SpO₂ 98%.
5. Save and review the case details; return to the patient timeline.
6. Open View report → Print / Save PDF.
7. Optionally demonstrate editing a patient and closing a case.

## Files and ownership

| Planner owner | Deliverables |
|---|---|
| Person 1 — UI/dashboard | `templates/`, `static/css/style.css`, responsive navigation and states |
| Person 2 — Backend/authentication | `app.py`, protected routes, session/CSRF/login throttling |
| Person 3 — Database/core records | `database.py`, `schema.sql`, `validation.py`, `seed.py` |
| Person 4 — Reports/QA/demo | report templates, `tests/test_app.py`, this guide, `HANDOFF.md` |

## Source reconciliation

The seven uploaded HTML files supplied the sidebar, dark panel structure, dashboard cards, page hierarchy and branding. Their referenced `css/style.css` and `js/app.js` were not attached. Styling was therefore recreated from those layouts and embedded color hints, rather than claiming pixel-exact recovery. The original HTML is preserved under `reference/frontend/` for comparison.

The supplied newer schema is the foundation: `patients`, `cases`, and `vitals`, using text IDs such as `PAT0001`. No `medicase.db` is used. Initialization preserves existing rows and adds missing MVP fields to the supplied newer schema. This is not a migration utility for the earlier integer-ID prototype.

| Uploaded field | Integrated field |
|---|---|
| patientId | generated `patient_id`, read-only |
| fullName | explicit `first_name` + optional `last_name` |
| age | `date_of_birth`; age calculated when displayed |
| bloodGroup | `blood_group` |
| emergencyContact | `emergency_contact` |
| allergies | patient baseline plus independent case snapshot |

`users`, `counters`, and `login_attempts` support auth and safe IDs. Case additions are duration, examination, status, doctor ID, and modification timestamp. Vitals use °F to match the supplied 101.2 demo value. Blank values are not treated as zero. Times use UTC. Clinical notes belong to their visit; reports display current patient demographics.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests run against temporary databases and do not change the included demo database. Coverage includes complete navigation, auth/CSRF, throttle, patient CRUD/search/duplicates, validation, escaping, case edits, vitals, report rendering, cascade deletion and foreign-key integrity.

## Local presentation server

For a more robust local demo server, use the included Waitress dependency:

```powershell
.\.venv\Scripts\waitress-serve.exe --host=127.0.0.1 --port=5000 --call app:create_app
```

The default Python command runs Flask with debugging disabled. The app creates a local `.secret_key` at first run; keep it private and stable. Set `MEDICASE_SECRET_KEY` to override it. Set `MEDICASE_HTTPS=1` only when serving over HTTPS, as this makes cookies HTTPS-only.

To create another account:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app create-user
```

This prompts for name/email and a password of at least 10 characters. All accounts share the clinic workspace in this MVP.

## Data and scope

This is a production-like **hackathon MVP**, not a certified clinical system. Use synthetic data for demonstration. There is no automated diagnosis or prescribing. Public deployment with actual patient data needs access roles, auditing/versioned notes, encryption/backups, deployment-specific hardening and privacy review. The demo account is intentionally documented; do not expose this seeded database publicly.

Back up `patient_case.db` while the application is stopped. Deleting a patient requires typing its ID and permanently deletes linked cases/vitals. The seed command only adds patient data when the patient table is empty and never resets an existing user password. To start a separate clean demonstration, stop the app and move the existing database to a backup location before running `seed.py`.
