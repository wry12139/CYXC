import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import db as db_module
import auth


def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # 静默默认日志
            pass

        def _cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

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
            try:
                return json.loads(self.rfile.read(length) or b'{}')
            except json.JSONDecodeError:
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

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            self._route('GET')

        def do_POST(self):
            self._route('POST')

        def _route(self, method):
            path = self.path.split('?')[0]
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
                row = conn.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
                return self._send_json(200, {'user_id': uid, 'username': row[0]})
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

    return Handler


def run(db_path=db_module.DEFAULT_DB_PATH, host='0.0.0.0', port=8091):
    db_module.init_db(db_path)
    httpd = HTTPServer((host, port), make_handler(db_path))
    print(f'[finrookie-backend] listening on {host}:{port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run()
