import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import db as db_module
import auth
import admin
import content
import recommendation
from admin import ensure_admin_exists
from migrate_seed_data import migrate_seed_data


def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # 静默默认日志
            pass

        def _cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')

        def _send_json(self, status, obj):
            payload = json.dumps(obj).encode('utf-8')
            self.send_response(status)
            self._cors()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _read_json(self):
            length = int(self.headers.get('Content-Length') or 0)
            if not length:
                return {}
            raw = self.rfile.read(length) or b'{}'
            try:
                return json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None

        def _authed_uid(self):
            hdr = self.headers.get('Authorization') or ''
            if not hdr.startswith('Bearer '):
                return None
            token = hdr[len('Bearer '):]
            conn = db_module.get_conn(db_path)
            try:
                return auth.lookup_session(conn, token)
            finally:
                conn.close()

        def _parse_url(self):
            return urlparse(self.path)

        def _require_admin(self):
            uid = self._authed_uid()
            if uid is None:
                self._send_json(401, {'error': 'unauthorized'})
                return None
            conn = db_module.get_conn(db_path)
            try:
                if not admin.is_admin(conn, uid):
                    self._send_json(403, {'error': 'forbidden'})
                    return None
            finally:
                conn.close()
            return uid

        def _username_for_uid(self, uid):
            conn = db_module.get_conn(db_path)
            try:
                row = conn.execute('SELECT username FROM users WHERE id=?', (uid,)).fetchone()
                return row[0] if row else None
            finally:
                conn.close()

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            self._route('GET')

        def do_POST(self):
            self._route('POST')

        def do_PUT(self):
            self._route('PUT')

        def do_DELETE(self):
            self._route('DELETE')

        def _route(self, method):
            parsed = self._parse_url()
            path = parsed.path
            if method == 'POST' and path == '/api/register':
                return self._handle_register()
            if method == 'POST' and path == '/api/login':
                return self._handle_login()
            if method == 'POST' and path == '/api/logout':
                return self._handle_logout()
            if method == 'GET' and path == '/api/me':
                return self._handle_me()
            if method == 'GET' and path == '/api/sync/pull':
                return self._handle_pull()
            if method == 'POST' and path == '/api/sync/push':
                return self._handle_push()
            if method == 'GET' and path == '/api/recommendations':
                return self._handle_recommendations(parsed)
            if method == 'GET' and path == '/api/admin/contents':
                return self._handle_admin_list_contents(parsed)
            if method == 'POST' and path == '/api/admin/contents':
                return self._handle_admin_create_content()
            if method == 'GET' and path.startswith('/api/admin/contents/') and path.endswith('/versions'):
                return self._handle_admin_versions(path)
            if method == 'PUT' and path.startswith('/api/admin/contents/') and '/versions' not in path:
                return self._handle_admin_update_content(path)
            if method == 'DELETE' and path.startswith('/api/admin/contents/') and '/versions' not in path:
                return self._handle_admin_delete_content(path)
            self._send_json(404, {'error': 'not_found'})

        def _handle_register(self):
            data = self._read_json()
            if data is None:
                return self._send_json(400, {'error': 'bad_json'})
            username = (data.get('username') or '').strip()
            password = data.get('password') or ''
            if not username or not password:
                return self._send_json(400, {'error': 'missing_field'})
            password_hash, salt = auth.hash_password(password)
            conn = db_module.get_conn(db_path)
            try:
                exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
                if exists:
                    return self._send_json(409, {'error': 'username_taken'})
                try:
                    conn.execute(
                        "INSERT INTO users (username,password_hash,salt,created_at) VALUES (?,?,?,?)",
                        (username, password_hash, salt, datetime.now(timezone.utc).isoformat()))
                    conn.commit()
                except sqlite3.IntegrityError:
                    return self._send_json(409, {'error': 'username_taken'})
                return self._send_json(201, {'ok': True})
            finally:
                conn.close()

        def _handle_login(self):
            data = self._read_json()
            if data is None:
                return self._send_json(400, {'error': 'bad_json'})
            username = (data.get('username') or '').strip()
            password = data.get('password') or ''
            conn = db_module.get_conn(db_path)
            try:
                row = conn.execute(
                    "SELECT id, password_hash, salt FROM users WHERE username=?",
                    (username,)).fetchone()
                if not row or not auth.verify_password(password, row[2], row[1]):
                    return self._send_json(401, {'error': 'bad_credentials'})
                token = auth.create_session(conn, row[0])
                return self._send_json(200, {'token': token, 'username': username})
            finally:
                conn.close()

        def _handle_logout(self):
            hdr = self.headers.get('Authorization') or ''
            token = hdr[len('Bearer '):] if hdr.startswith('Bearer ') else ''
            conn = db_module.get_conn(db_path)
            try:
                if token:
                    auth.delete_session(conn, token)
            finally:
                conn.close()
            return self._send_json(200, {'ok': True})

        def _handle_me(self):
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            conn = db_module.get_conn(db_path)
            try:
                row = conn.execute("SELECT username, is_admin FROM users WHERE id=?", (uid,)).fetchone()
                return self._send_json(200, {'username': row[0], 'is_admin': bool(row[1])})
            finally:
                conn.close()

        def _handle_pull(self):
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            conn = db_module.get_conn(db_path)
            try:
                row = conn.execute(
                    "SELECT data_json, updated_at FROM user_data WHERE user_id=?", (uid,)).fetchone()
                if not row:
                    return self._send_json(200, {'data': None, 'updated_at': None})
                return self._send_json(200, {'data': json.loads(row[0]), 'updated_at': row[1]})
            finally:
                conn.close()

        def _handle_push(self):
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            payload = self._read_json()
            if payload is None or not isinstance(payload.get('data'), dict):
                return self._send_json(400, {'error': 'bad_data'})
            now = datetime.now(timezone.utc).isoformat()
            data_json = json.dumps(payload['data'])
            conn = db_module.get_conn(db_path)
            try:
                conn.execute(
                    "INSERT INTO user_data (user_id, data_json, updated_at) VALUES (?,?,?) "
                    "ON CONFLICT(user_id) DO UPDATE SET data_json=excluded.data_json, updated_at=excluded.updated_at",
                    (uid, data_json, now))
                conn.commit()
                return self._send_json(200, {'ok': True, 'updated_at': now})
            finally:
                conn.close()

        def _handle_recommendations(self, parsed):
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            query = parse_qs(parsed.query)
            try:
                num = int((query.get('num') or ['5'])[0])
            except ValueError:
                return self._send_json(400, {'error': 'bad_num'})
            conn = db_module.get_conn(db_path)
            try:
                recs = recommendation.generate_recommendations(conn, uid, num_recommendations=max(0, num))
                return self._send_json(200, recs)
            finally:
                conn.close()

        def _handle_admin_list_contents(self, parsed):
            uid = self._require_admin()
            if uid is None:
                return
            query = parse_qs(parsed.query)
            content_type = (query.get('type') or [None])[0]
            conn = db_module.get_conn(db_path)
            try:
                items = content.list_content(conn, content_type=content_type)
                return self._send_json(200, items)
            finally:
                conn.close()

        def _handle_admin_create_content(self):
            uid = self._require_admin()
            if uid is None:
                return
            payload = self._read_json()
            if payload is None:
                return self._send_json(400, {'error': 'bad_json'})
            content_type = (payload.get('type') or '').strip()
            data = payload.get('data')
            if not content_type or not isinstance(data, dict):
                return self._send_json(400, {'error': 'missing_field'})
            username = self._username_for_uid(uid)
            conn = db_module.get_conn(db_path)
            try:
                content_id = content.create_content(conn, content_type, data, username)
                item = content.get_content(conn, content_id)
                return self._send_json(201, item)
            finally:
                conn.close()

        def _handle_admin_versions(self, path):
            uid = self._require_admin()
            if uid is None:
                return
            parts = path.split('/')
            if len(parts) != 6 or not parts[4]:
                return self._send_json(404, {'error': 'not_found'})
            content_id = parts[4]
            conn = db_module.get_conn(db_path)
            try:
                versions = content.get_versions(conn, content_id)
                return self._send_json(200, versions)
            finally:
                conn.close()

        def _handle_admin_update_content(self, path):
            uid = self._require_admin()
            if uid is None:
                return
            parts = path.split('/')
            if len(parts) != 5 or not parts[4]:
                return self._send_json(404, {'error': 'not_found'})
            payload = self._read_json()
            if payload is None or not isinstance(payload.get('data'), dict):
                return self._send_json(400, {'error': 'missing_field'})
            username = self._username_for_uid(uid)
            conn = db_module.get_conn(db_path)
            try:
                try:
                    content.update_content(conn, parts[4], payload['data'], username)
                except ValueError:
                    return self._send_json(404, {'error': 'not_found'})
                item = content.get_content(conn, parts[4])
                return self._send_json(200, item)
            finally:
                conn.close()

        def _handle_admin_delete_content(self, path):
            uid = self._require_admin()
            if uid is None:
                return
            parts = path.split('/')
            if len(parts) != 5 or not parts[4]:
                return self._send_json(404, {'error': 'not_found'})
            username = self._username_for_uid(uid)
            conn = db_module.get_conn(db_path)
            try:
                try:
                    content.delete_content(conn, parts[4], username)
                except ValueError:
                    return self._send_json(404, {'error': 'not_found'})
                return self._send_json(200, {'ok': True})
            finally:
                conn.close()

    return Handler


def run(db_path=db_module.DEFAULT_DB_PATH, host='0.0.0.0', port=8091):
    db_module.init_db(db_path)
    conn = db_module.get_conn(db_path)
    try:
        ensure_admin_exists(conn)
        migrate_seed_data(conn, finrookie_dir='.')
    finally:
        conn.close()
    httpd = HTTPServer((host, port), make_handler(db_path))
    print(f'[finrookie-backend] listening on {host}:{port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run()
