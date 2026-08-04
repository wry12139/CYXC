import json
import uuid
from datetime import datetime, timezone


def _generate_id():
    return uuid.uuid4().hex[:12]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_content(conn, content_type, data, created_by):
    content_id = _generate_id()
    now = _now_iso()
    conn.execute(
        'INSERT INTO content_items (id, type, data, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?)',
        (content_id, content_type, json.dumps(data, ensure_ascii=False), created_by, now, now),
    )
    conn.execute(
        'INSERT INTO content_versions (id, content_id, type, changed_by, changed_at, action, diff) VALUES (?,?,?,?,?,?,?)',
        (_generate_id(), content_id, content_type, created_by, now, 'create', json.dumps(data, ensure_ascii=False)),
    )
    conn.commit()
    return content_id


def get_content(conn, content_id):
    row = conn.execute(
        'SELECT id, type, data, created_by, created_at, updated_at FROM content_items WHERE id=?',
        (content_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        'id': row[0],
        'type': row[1],
        'data': json.loads(row[2]),
        'created_by': row[3],
        'created_at': row[4],
        'updated_at': row[5],
    }


def list_content(conn, content_type=None):
    if content_type:
        rows = conn.execute(
            'SELECT id, type, data, created_by, created_at, updated_at FROM content_items WHERE type=? ORDER BY created_at DESC',
            (content_type,),
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT id, type, data, created_by, created_at, updated_at FROM content_items ORDER BY created_at DESC'
        ).fetchall()
    return [
        {
            'id': row[0],
            'type': row[1],
            'data': json.loads(row[2]),
            'created_by': row[3],
            'created_at': row[4],
            'updated_at': row[5],
        }
        for row in rows
    ]


def update_content(conn, content_id, data, changed_by):
    row = conn.execute('SELECT type, data FROM content_items WHERE id=?', (content_id,)).fetchone()
    if row is None:
        raise ValueError('content_not_found')
    content_type, old_data_json = row
    now = _now_iso()
    conn.execute(
        'UPDATE content_items SET data=?, updated_at=? WHERE id=?',
        (json.dumps(data, ensure_ascii=False), now, content_id),
    )
    conn.execute(
        'INSERT INTO content_versions (id, content_id, type, changed_by, changed_at, action, diff) VALUES (?,?,?,?,?,?,?)',
        (
            _generate_id(),
            content_id,
            content_type,
            changed_by,
            now,
            'update',
            json.dumps({'old': json.loads(old_data_json), 'new': data}, ensure_ascii=False),
        ),
    )
    conn.commit()


def delete_content(conn, content_id, changed_by):
    row = conn.execute('SELECT type, data FROM content_items WHERE id=?', (content_id,)).fetchone()
    if row is None:
        raise ValueError('content_not_found')
    content_type, old_data_json = row
    now = _now_iso()
    conn.execute(
        'INSERT INTO content_versions (id, content_id, type, changed_by, changed_at, action, diff) VALUES (?,?,?,?,?,?,?)',
        (_generate_id(), content_id, content_type, changed_by, now, 'delete', old_data_json),
    )
    # Must delete versions before items due to foreign key constraint
    conn.execute('DELETE FROM content_versions WHERE content_id=?', (content_id,))
    conn.execute('DELETE FROM content_items WHERE id=?', (content_id,))
    conn.commit()


def get_versions(conn, content_id):
    rows = conn.execute(
        'SELECT id, changed_by, changed_at, action, diff FROM content_versions WHERE content_id=? ORDER BY changed_at DESC',
        (content_id,),
    ).fetchall()
    return [
        {
            'id': row[0],
            'changed_by': row[1],
            'changed_at': row[2],
            'action': row[3],
            'diff': json.loads(row[4]) if row[4] else None,
        }
        for row in rows
    ]
