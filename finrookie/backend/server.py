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

    return Handler


def run(db_path=db_module.DEFAULT_DB_PATH, host='0.0.0.0', port=8091):
    db_module.init_db(db_path)
    httpd = HTTPServer((host, port), make_handler(db_path))
    print(f'[finrookie-backend] listening on {host}:{port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run()
