import hashlib, secrets
from datetime import datetime, timedelta, timezone

_ITERATIONS = 200_000

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                             bytes.fromhex(salt), _ITERATIONS)
    return dk.hex(), salt

def verify_password(password, salt, expected_hash):
    calc, _ = hash_password(password, salt)
    return secrets.compare_digest(calc, expected_hash)

def create_session(conn, user_id, ttl_days=30):
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=ttl_days)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, now.isoformat(), expires.isoformat()))
    conn.commit()
    return token

def lookup_session(conn, token):
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token=?", (token,)).fetchone()
    if not row:
        return None
    user_id, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        return None
    return user_id

def delete_session(conn, token):
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
