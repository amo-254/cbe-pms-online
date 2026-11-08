# CBE PMS desktop-to-web feature parity — Phase 9

This matrix prevents the current conversion build from being mistaken for a finished one-to-one recreation of the Tkinter desktop application.

## Implemented in this Phase 9 package (code present; live acceptance tests still required)

- Flask login with Administrator and Teacher roles; password verification supports the old SHA-256 hashes and upgrades successful logins to scrypt.
- PostgreSQL data models and migration coverage for all ten source tables, preserving primary keys and foreign-key references.
- Learner registration, search, edit, delete, Assessment No., Gender, Excel import/template, and Registered Learners PDF.
- Assessment creation, editing while preserving assessment ID and linked scores, soft deletion, restore, permanent deletion, and analysis-state reset after editing.
- Learning-area score entry with teacher assignment checks, 0–100 validation, learner grade/stream validation, and deadline-plus-analysis lock rule.
- Teacher account creation/edit/reset/delete and administrator promotion.
- Learning-area assignments and class-teacher assignments.
- Score-sheet PDF and Excel downloads with four blank score columns.
- Basic merit list with Total Marks default ranking and Total Points alternative; CBE 1–8 points mapping.
- Basic assessment analysis, previous-assessment comparison within the same grade, raw-score PDF, learner PDF, and teacher learning-area results PDF.
- School name/contact/period/opening/closing settings; logo stored in PostgreSQL after re-upload.
- Annual Grade 1–8 promotion and Grade 9 graduating-class archival function, protected Vercel Cron endpoint and idempotency guard.

## Still to implement or verify against the desktop source

- Full desktop dashboard and all single-window navigation sections in a responsive browser interface.
- Complete learner transcript and progress-report variants, all-learners ranked report PDF, and exact one-page learner report layout.
- Full detailed exam-analysis tables: learning-area ranking, performance-level breakdown by learning area, top learners, most-improved categories, combined/per-stream analysis and every comparison rule.
- Merit-list learning-area score columns and per-learning-area level breakdown, plus all original merit filters and export formats.
- Exact desktop PDF styling requirements for every report (logo placement, Times New Roman-compatible font, wrapping, spacing, comments, dates, positions, page layout and page numbers).
- Class-teacher and HOI comment generation and display in individual/all learner reports.
- Forgot-password/recovery workflow, teacher demotion, complete teacher account controls and audit trail.
- Full assignment editing/de-duplication and teacher-facing screens for every assigned learning-area workflow.
- Automatic Jan-1 transition must be tested on the connected Vercel project and confirmed with a safe test database before production use.
- Security hardening before public launch: CSRF protection, rate limiting, audit logging, stronger account recovery, and end-to-end role-authorization tests.

## Data migration notes

The supplied SQLite file passed `PRAGMA integrity_check` and `PRAGMA foreign_key_check`. Source counts are in `SOURCE_DATABASE_INVENTORY.txt`. The desktop `school_logo` setting points to a Windows local path, so the logo must be uploaded again from the online School Settings page. Plaintext password-display values are intentionally not copied to PostgreSQL.
