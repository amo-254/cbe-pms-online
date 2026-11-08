# CBE PMS Online — Vercel Conversion Phase 9

This project is a Flask web conversion based on the supplied CBE PMS desktop source and the supplied `cbe_pms.db` SQLite data file.

## What this phase includes

- Flask web application with Administrator and Teacher login roles.
- PostgreSQL-compatible SQLAlchemy models for users, teachers, learners, assessments, scores, learning-area assignments, class-teacher assignments, graduating classes, graduating-class members and school settings.
- SQLite-to-PostgreSQL migration script that maps all ten school tables and preserves IDs and legacy password hashes. It clears the old plaintext `password_display` field; successful logins upgrade SHA-256 hashes to scrypt.
- Learner Assessment Number and Gender fields, learner editing and deletion, Excel import/template, assessment and score entry, merit/analysis and report routes from the prior web conversion.
- Class teacher assignment screen, score-sheet PDF/Excel templates, registered-learners PDF, assessment editing without changing the assessment ID, and an idempotent annual grade-transition endpoint that archives Grade 9 and promotes Grades 1–8.
- School logo stored in the PostgreSQL settings table as base64 data so it is not lost on Vercel's temporary filesystem.
- Vercel Flask project configuration and public stylesheet.

## Important scope note

This is an incremental web-conversion build, not a claim that every desktop Tkinter screen has already been recreated. Some advanced desktop report layouts, detailed analysis breakdowns, transcript/progress report variants and class-teacher comments still need dedicated implementation. The annual transition cron is included but must be verified in the live Vercel project before production use. The desktop source remains the reference for those features.

## Local setup

1. Install Python 3.12+.
2. Create and activate a virtual environment.
3. Run `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set `SECRET_KEY` and a local `DATABASE_URL`.
5. Start with `python app.py`.

For local development, SQLite is used only when `DATABASE_URL` is omitted. On Vercel, `DATABASE_URL` is mandatory.

## PostgreSQL data migration

First create a managed PostgreSQL database (for example, Neon) and set `DATABASE_URL` in your terminal. Do not put the connection string in source code or commit it to Git.

Validate the supplied SQLite database:

```bash
python migrate_sqlite_to_postgres.py --dry-run /path/to/cbe_pms.db
```

Run the migration:

```bash
python migrate_sqlite_to_postgres.py /path/to/cbe_pms.db
```

The migration is restartable by primary key. Review the source/destination count report. The old desktop password hashes are retained for compatibility and are upgraded to scrypt after each user's first successful login. The old plaintext password-display field is intentionally not copied. The database stores the previous desktop logo as a local Windows path, which will not work online; upload the school logo again in School Settings after migration.

## Vercel deployment

1. Push the contents of this folder to a GitHub repository.
2. Import the repository into Vercel.
3. Add these Environment Variables in Vercel Project Settings:
   - `DATABASE_URL` — PostgreSQL connection string, preferably the provider's pooled/runtime URL.
   - `SECRET_KEY` — a random secret with at least 32 characters.
   - `FLASK_ENV` = `production`.
   - `COOKIE_SECURE` = `1`.
   - `BOOTSTRAP_DEMO_USERS` = `0`.
   - `CRON_SECRET` — a separate random secret used to authenticate the annual grade-transition cron endpoint.
4. Deploy. Check `/health` and confirm it reports both application and database healthy.

Vercel's Python runtime supports Flask WSGI applications. The root `app.py` exposes the Flask `app` object. Static CSS is in `public/style.css`.

## First admin login

The migrated `admin` account keeps its legacy hash and will upgrade on a successful login. The supplied database's initial desktop credentials were `admin` / `admin123`; change this immediately after the first login. Never expose the password or database URL in GitHub.

## Production checklist still required

- Confirm Neon connection and complete the migration from a secure local terminal.
- Test all 13 existing login accounts and reset any credentials that should not remain active.
- Test teacher assignment enforcement and deadline/analyzed lock rules.
- Configure a database backup schedule and test a restore. Confirm the Vercel Cron job runs on January 1 (UTC schedule; 03:00 East Africa Time) and that `CRON_SECRET` is configured.
- Review CSRF protection, audit logging, rate limiting and account recovery before public production use.
- Complete feature-by-feature acceptance testing against the desktop source before declaring full parity.
