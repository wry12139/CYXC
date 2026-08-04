from datetime import datetime, timezone

from auth import hash_password


DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'


def is_admin(conn, user_id):
    row = conn.execute(
        "SELECT is_admin FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    return bool(row and row[0])


def ensure_admin_exists(conn):
    row = conn.execute(
        "SELECT id FROM users WHERE username=?",
        (DEFAULT_ADMIN_USERNAME,),
    ).fetchone()
    if row:
        return

    password_hash, salt = hash_password(DEFAULT_ADMIN_PASSWORD)
    conn.execute(
        "INSERT INTO users (username,password_hash,salt,created_at,is_admin) VALUES (?,?,?,?,?)",
        (
            DEFAULT_ADMIN_USERNAME,
            password_hash,
            salt,
            datetime.now(timezone.utc).isoformat(),
            1,
        ),
    )
    conn.commit()
