"""Migrate the uploaded CBE PMS SQLite database into PostgreSQL.

Run from the project directory:
  DATABASE_URL='postgresql://...' SECRET_KEY='...' python migrate_sqlite_to_postgres.py --dry-run /path/to/cbe_pms.db
  DATABASE_URL='postgresql://...' SECRET_KEY='...' python migrate_sqlite_to_postgres.py /path/to/cbe_pms.db

The script is restartable by primary key. It preserves legacy SHA-256 password
hashes for one-time upgrade on the user's next successful login, but deliberately
clears the old plaintext password_display field.
"""
import argparse
import os
import sqlite3
os.environ['CBE_PMS_SKIP_INIT'] = '1'
from datetime import datetime
from sqlalchemy import text
from app import app, db, User, Teacher, Learner, Assessment, Score, Assignment, ClassTeacherAssignment, GraduatingClass, GraduatingClassMember, Setting

TABLES = [
    ('users', User),
    ('teachers', Teacher),
    ('learners', Learner),
    ('assessments', Assessment),
    ('teacher_assignments', Assignment),
    ('class_teacher_assignments', ClassTeacherAssignment),
    ('graduating_classes', GraduatingClass),
    ('graduating_class_members', GraduatingClassMember),
    ('scores', Score),
    ('settings', Setting),
]
DATETIME_COLUMNS = {'created_at', 'analyzed_at', 'deleted_at'}

def convert_value(column, value):
    if value is None:
        return None
    if column in DATETIME_COLUMNS and isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
    return value

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('sqlite_file')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    source_path = os.path.abspath(args.sqlite_file)
    if not os.path.isfile(source_path):
        raise SystemExit(f'SQLite database not found: {source_path}')
    if not os.environ.get('DATABASE_URL'):
        raise SystemExit('Set DATABASE_URL to the PostgreSQL connection string.')
    src = sqlite3.connect(f'file:{source_path}?mode=ro', uri=True)
    src.row_factory = sqlite3.Row
    source_tables = {r['name'] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {}
    for table, _model in TABLES:
        if table in source_tables:
            expected[table] = src.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print('Source database:', source_path)
    print('Source table counts:')
    for table, count in expected.items():
        print(f'  {table}: {count}')
    if args.dry_run:
        print('Dry run only: no PostgreSQL records were written.')
        src.close()
        return
    with app.app_context():
        db.create_all()
        for table, model in TABLES:
            if table not in source_tables:
                print(f'SKIP {table}: not present in source')
                continue
            source_rows = src.execute(f'SELECT * FROM "{table}" ORDER BY id' if table != 'settings' else 'SELECT * FROM settings ORDER BY key').fetchall()
            mapped = {c.name for c in model.__table__.columns}
            copied = 0
            for row in source_rows:
                values = {k: convert_value(k, row[k]) for k in row.keys() if k in mapped}
                if table == 'users':
                    # Never carry forward the desktop app's plaintext password display.
                    values['password_display'] = ''
                pk_name = 'key' if table == 'settings' else 'id'
                pk_value = values.get(pk_name)
                if pk_value is not None and db.session.get(model, pk_value) is not None:
                    continue
                db.session.add(model(**values))
                copied += 1
                if copied % 500 == 0:
                    db.session.commit()
            db.session.commit()
            actual = model.query.count()
            print(f'{table}: inserted {copied}; PostgreSQL total now {actual}')
        # Ensure PostgreSQL sequences start above the preserved SQLite IDs.
        if db.engine.dialect.name == 'postgresql':
            for table in ('user','teacher','learner','assessment','score','assignment','class_teacher_assignment','graduating_class','graduating_class_member'):
                db.session.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), GREATEST(COALESCE((SELECT MAX(id) FROM \"{table}\"), 1), 1), true)"
                ))
            db.session.commit()
        print('\nMigration verification:')
        for source_table, model in TABLES:
            if source_table in expected:
                count = model.query.count()
                print(f'  {source_table}: source={expected[source_table]} destination={count}')
                if count < expected[source_table]:
                    raise SystemExit(f'Count verification failed for {source_table}.')
    src.close()
    print('\nMigration completed. Verify sample learners, scores and teacher logins before opening the site to users.')

if __name__ == '__main__':
    main()
