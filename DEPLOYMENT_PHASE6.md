# CBE PMS Web V73 — Phase 6: Live Deployment

Phase 6 prepares the application for public hosting. The application is **not automatically deployed** because deployment requires access to a hosting provider account and a domain/DNS account owned by the school.

## Option A — Render

1. Create a PostgreSQL database and web service from this repository/ZIP after placing the project in GitHub/GitLab.
2. Render can use the included `render.yaml` Blueprint.
3. Confirm the generated `SECRET_KEY` is present.
4. Confirm `DATABASE_URL` points to the managed PostgreSQL database.
5. Open `/health`; it should return `status: ok` and `database: ok`.
6. Add the school's custom domain in the hosting provider and enable HTTPS.

## Option B — VPS/Docker

1. Copy `.env.production.example` to `.env` and replace every placeholder.
2. Run:
   `docker compose -f production-compose.yml up -d --build`
3. Put Nginx/Caddy/another reverse proxy in front of port 5000.
4. Configure HTTPS with a valid certificate.
5. Point the school's DNS A/AAAA record to the server.

## Database migration

For the original desktop SQLite database:

`DATABASE_URL='postgresql://...' python migrate_sqlite_to_postgres.py /path/to/cbe_pms.db`

Back up the original SQLite database first. After migration, verify learner, assessment, assignment and score counts.

## PostgreSQL backups

Use the hosting provider's automated backups. For a VPS, `backup_postgres.sh` creates a timestamped PostgreSQL custom-format dump. Store copies outside the application server.

## First login security

Immediately change the sample administrator password and remove/disable sample accounts before giving the URL to teachers.

## Production checklist

- [ ] PostgreSQL connected
- [ ] SECRET_KEY generated and private
- [ ] Sample credentials changed/removed
- [ ] HTTPS enabled
- [ ] Custom domain configured
- [ ] Database backups enabled
- [ ] `/health` returns OK
- [ ] Excel import tested
- [ ] PDF downloads tested
- [ ] Admin/Teacher permissions tested
- [ ] Assessment deadline locking tested
- [ ] Real school data migrated and verified
