# CBE PMS Web V73 — Phase 5 Production Deployment

## 1. Database
Use PostgreSQL in production. Set `DATABASE_URL` to the provider connection string.

## 2. Secret
Generate a strong `SECRET_KEY` and never commit it to source control.

## 3. Run locally
```
pip install -r requirements.txt
flask --app app init-db
python app.py
```
If the `init-db` command is unavailable, run `python app.py` once to create the schema.

## 4. Production
Use Gunicorn:
```
gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app
```
Set `FLASK_ENV=production`, `FLASK_DEBUG=0`, and `COOKIE_SECURE=1` behind HTTPS.

## 5. Migrate an existing desktop SQLite database
```
DATABASE_URL='postgresql://...' python migrate_sqlite_to_postgres.py /path/to/cbe_pms.db
```
Make a backup before migration and verify learner, assessment and score counts afterward.

## 6. Health check
Open `/health`. A healthy installation returns JSON with `status: ok` and `database: ok`.

## 7. Security changes in Phase 5
- Passwords use Werkzeug `scrypt` hashing for new/reset passwords.
- Legacy SHA-256 passwords are upgraded after successful login.
- Production requires `SECRET_KEY`.
- Secure cookie option is enabled for production.
- Security response headers are added.
- Debug mode is disabled unless explicitly enabled.

## 8. Before public launch
- Create a dedicated admin password; do not use the sample credentials.
- Remove the sample teacher/admin accounts if they are not needed.
- Configure HTTPS and a custom domain.
- Configure automated PostgreSQL backups.
- Test PDF, Excel upload/download and score entry with real school data.
