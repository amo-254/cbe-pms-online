# CBE PMS Web V73 — Phase 8: Production Deployment & Data Migration

Phase 8 packages the application for its final move from desktop V73 data to a hosted PostgreSQL database.

## 1. Create PostgreSQL
Create a managed PostgreSQL database with your hosting provider and copy its connection string into `DATABASE_URL`.

## 2. Configure secrets
Set:
- `SECRET_KEY` to a random value of at least 32 characters.
- `FLASK_ENV=production`
- `COOKIE_SECURE=1`
- `BOOTSTRAP_DEMO_USERS=0`
- `DATABASE_URL=<your PostgreSQL URL>`

Do not put real passwords or database URLs into source files.

## 3. Preflight
Run:
`python production_preflight.py`

## 4. Create the first administrator
Run the included `bootstrap_admin.py` once against the production database, supplying a strong initial password through the environment. Do not enable demo users.

## 5. Migrate existing V73 data
Obtain the desktop V73 SQLite database file (`cbe_pms.db`). First validate it:
`DATABASE_URL='postgresql://...' python migrate_sqlite_to_postgres.py --dry-run /path/to/cbe_pms.db`

Then migrate:
`DATABASE_URL='postgresql://...' python migrate_sqlite_to_postgres.py /path/to/cbe_pms.db`

Back up the PostgreSQL database before migration and verify learner, teacher, assessment and score counts after migration.

## 6. Deploy
The included `render.yaml`, `Dockerfile`, `Procfile`, and `production-compose.yml` support hosted deployment. Configure the service to use Gunicorn and the PostgreSQL URL.

## 7. Verify
Check `/health`, then verify:
- Administrator login
- Teacher login
- Learner search/edit
- Create Assessment with `-` defaults
- Score entry restrictions
- Analyse/Re-analyse
- Merit List filters
- Learner PDF
- Analysis PDF
- Teacher learning-area PDF
- Excel import/export
- School logo/settings

## 8. Domain and HTTPS
Attach the school's domain at the hosting provider, point DNS as instructed by the provider, and require HTTPS. Keep `COOKIE_SECURE=1` in production.

## Important
This package is deployment-ready but cannot create or control a cloud account/domain from this workspace. A live URL will exist only after the package is deployed to a hosting account.
