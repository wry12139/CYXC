import hashlib
from datetime import datetime, timezone


def ensure_table(conn):
    conn.execute(
        """
    CREATE TABLE IF NOT EXISTS ai_cache (
        question_hash TEXT PRIMARY KEY,
        question      TEXT NOT NULL,
        answer        TEXT NOT NULL,
        created_at    TEXT NOT NULL
    )"""
    )
    conn.commit()


def normalize(question):
    return "".join(question.split()).lower()


def cache_key(question):
    return hashlib.sha256(normalize(question).encode("utf-8")).hexdigest()


def get_cached(conn, question):
    row = conn.execute(
        "SELECT answer FROM ai_cache WHERE question_hash=?",
        (cache_key(question),),
    ).fetchone()
    return row[0] if row else None


def put_cached(conn, question, answer):
    conn.execute(
        "INSERT OR REPLACE INTO ai_cache (question_hash, question, answer, created_at) "
        "VALUES (?,?,?,?)",
        (cache_key(question), question, answer, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
