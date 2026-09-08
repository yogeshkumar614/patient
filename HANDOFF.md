# Four-person handoff

This build follows the original 4-person / 2-day SIH26047 planner, with the later supplied three-table schema taking precedence over the early prototype.

## Person 1: UI and dashboard
Explain how the uploaded sidebar/card/table design became shared Jinja templates. Demonstrate the dark workspace, patient search, responsive form layout, and keyboard navigation. Original CSS/JS were missing; the finished stylesheet is a reconstruction.

## Person 2: backend and authentication
Explain browser → Flask route → database → Jinja rendering. Forms post the schema's field names. Sessions contain only the user ID and CSRF token, never clinical records. Passwords are hashed. Logout and all mutations use POST. One clinic workspace is shared by all accounts.

## Person 3: database and patient/case engine
Explain one patient → many cases → many timestamped vitals. Patient IDs use a transactional counter. Every SQL connection enables foreign keys. Deletion cascades deliberately after confirmation. Vitals are checked against the owning case at database level. Existing clinical text comes from the treating user, not an AI generator.

## Person 4: reports, QA and demonstration
Run the test command in README. Follow the 7-step demo. Show print preview and choose Save as PDF. Disable browser-added headers and footers if you want a clean PDF. Reports include all case sections and recorded vitals; missing entries explicitly say Not recorded. The browser handles PDF creation without an extra server library.

## Final acceptance checklist
- Sign in; confirm 10 patients and 15 cases in the untouched seed.
- Search Ravi, patient ID, phone, and blood group.
- Add a patient, reload, edit it, attempt a matching duplicate.
- Add a case with notes and vitals; check history and report.
- Add a second vitals reading; verify both readings remain.
- Edit the case and set Closed; confirm active count changes.
- Check a nonexistent record URL displays a 404.
- Sign out; revisit a record URL and confirm sign-in is required.
- At mobile width, use navigation and fill the patient/case forms.
- Print the case report; check dark navigation is excluded.
- Delete only a disposable test patient using typed-ID confirmation.

## Deliberate scope limits
No diagnosis engine, medication recommendations, attachments, appointment scheduling, Aadhaar, or hospital ERP. No roles beyond shared authenticated care-team access. Case editing updates notes in place (not an audit history); vitals history is append-only. Search is intended for a small local hackathon dataset; pagination and indexing for large-scale full-name search can be future work.
