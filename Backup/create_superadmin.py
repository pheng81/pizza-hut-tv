import os
import sqlite3
import argparse
from werkzeug.security import generate_password_hash

"""
Seed or update a Super Admin account in the local SQLite database.

- Uses the same DB path convention as app.py: env USERS_DB_PATH or 'database.db'
- Creates the superadmins table if it doesn't exist
- Idempotent: upserts by username

Usage (PowerShell):
  python .\create_superadmin.py --username master --password "StrongPass123!"

Optionally:
  $env:USERS_DB_PATH = "C:\\path\\to\\database.db"; python .\create_superadmin.py --username master --password "..."
"""

def db_path() -> str:
    return os.environ.get('USERS_DB_PATH') or 'database.db'

def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        'CREATE TABLE IF NOT EXISTS superadmins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)'
    )
    conn.commit()


def upsert_superadmin(conn: sqlite3.Connection, username: str, password: str) -> None:
    password_hash = generate_password_hash(password)
    # SQLite upsert compatible with 3.24+
    conn.execute(
        """
        INSERT INTO superadmins (username, password_hash)
        VALUES (?, ?)
        ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash
        """,
        (username, password_hash),
    )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Create or update a Super Admin account.')
    parser.add_argument('--username', required=False, help='Super admin username (email or name)')
    parser.add_argument('--password', required=False, help='Super admin password')
    args = parser.parse_args()

    username = args.username or os.environ.get('SUPERADMIN_USERNAME')
    password = args.password or os.environ.get('SUPERADMIN_PASSWORD')

    if not username or not password:
        raise SystemExit('Missing credentials. Provide --username and --password or set SUPERADMIN_USERNAME and SUPERADMIN_PASSWORD environment variables.')

    path = db_path()
    print(f'Using database: {os.path.abspath(path)}')
    conn = sqlite3.connect(path)
    try:
        ensure_table(conn)
        upsert_superadmin(conn, username, password)
        print(f'Success: Super Admin "{username}" has been created/updated.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
