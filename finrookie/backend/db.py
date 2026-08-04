import os, sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), 'finrookie.db')

def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path):
    conn = get_conn(db_path)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt          TEXT NOT NULL,
        created_at    TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token      TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS user_data (
        user_id    INTEGER PRIMARY KEY REFERENCES users(id),
        data_json  TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS content_items (
        id         TEXT PRIMARY KEY,
        type       TEXT NOT NULL,
        data       JSON NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(username),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS content_versions (
        id         TEXT PRIMARY KEY,
        content_id TEXT NOT NULL REFERENCES content_items(id),
        type       TEXT NOT NULL,
        changed_by TEXT NOT NULL REFERENCES users(username),
        changed_at TEXT NOT NULL,
        action     TEXT NOT NULL,
        diff       JSON
    );
    """)

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    if 'is_admin' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    conn.commit()
    conn.close()
