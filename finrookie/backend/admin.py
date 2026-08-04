from datetime import datetime, timezone
import os
from auth import hash_password


DEFAULT_ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', None)

# If password not set, don't create default admin
if not DEFAULT_ADMIN_PASSWORD:
    DEFAULT_ADMIN_PASSWORD = 'CHANGE_ME_' + os.urandom(8).hex()  # Force change


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

    # Warn if using default password
    if DEFAULT_ADMIN_PASSWORD.startswith('CHANGE_ME_'):
        print(f"[WARNING] Admin account '{DEFAULT_ADMIN_USERNAME}' created with temporary password.")
        print(f"          Set ADMIN_PASSWORD environment variable for production use.")

