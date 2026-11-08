# CBE PMS V73 Web — Phase 7: Production Launch

## What changed
- WSGI startup now initializes the database schema automatically, so Gunicorn/Render can start from a fresh database.
- Demo/default accounts are **disabled by default**. Set `BOOTSTRAP_DEMO_USERS=1` only for a controlled test environment.
- Added `bootstrap_admin.py` for creating/resetting the first administrator without storing a default password in source code.
- Production Render blueprint is included.
- PostgreSQL remains the recommended production database.

## Render launch
1. Create a Render account and connect the repository containing this project.
2. Deploy using `render.yaml`, which creates the web service and PostgreSQL database.
3. Wait for `/health` to report `status=ok` and `database=ok`.
4. Create the first administrator using `bootstrap_admin.py` as a one-off job/shell, supplying `ADMIN_USERNAME` and `ADMIN_PASSWORD` as temporary environment variables.
5. Remove those temporary variables after the administrator is created.
6. Change the administrator password immediately after first login.
7. Configure the school's custom domain and HTTPS in the hosting provider.

## Existing V73 data
For existing SQLite data, run the supplied `migrate_sqlite_to_postgres.py` against the source database and the production `DATABASE_URL`. Test the migrated data before opening the system to teachers.

## Important production checklist
- [ ] PostgreSQL connected
- [ ] First administrator created
- [ ] Default/demo accounts not enabled
- [ ] School name, phone, address and logo configured
- [ ] Existing learner/assessment data migrated and verified
- [ ] HTTPS/custom domain enabled
- [ ] Backup policy configured
- [ ] Teacher accounts and assignments verified
- [ ] Test score entry, analysis, merit list and PDF downloads
- [ ] Test mobile browser access
