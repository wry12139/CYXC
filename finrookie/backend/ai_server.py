import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import db as db_module
import auth, compliance, ai_cache, ai_client

# 8091(用户后端)与本服务共享同一 finrookie.db;设 busy_timeout 让写锁竞争时
# 等待而非立刻抛 "database is locked"(db.py 不改,故在本服务开的连接上设)
_BUSY_TIMEOUT_MS = 5000


def _open_db(db_path):
    conn = db_module.get_conn(db_path)
    conn.execute("PRAGMA busy_timeout = %d" % _BUSY_TIMEOUT_MS)
    return conn


def make_handler(db_path, cfg):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')

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
                data = json.loads(self.rfile.read(length) or b'{}')
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return data if isinstance(data, dict) else None

        def _authed_uid(self):
            hdr = self.headers.get('Authorization') or ''
            if not hdr.startswith('Bearer '):
                return None
            conn = _open_db(db_path)
            try:
                return auth.lookup_session(conn, hdr[len('Bearer '):])
            finally:
                conn.close()

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self):
            if self.path.split('?')[0] != '/api/ask':
                return self._send_json(404, {'error': 'not_found'})
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            data = self._read_json()
            if data is None:
                return self._send_json(400, {'error': 'bad_json'})
            question = (data.get('question') or '').strip()
            if not question or len(question) > 200:
                return self._send_json(400, {'error': 'bad_question'})
            if compliance.input_blocked(question):
                return self._send_json(200, {'answer': compliance.SAFE_FALLBACK,
                                             'cached': False, 'blocked': True})
            conn = _open_db(db_path)
            try:
                hit = ai_cache.get_cached(conn, question)
                if hit is not None:
                    return self._send_json(200, {'answer': hit, 'cached': True})
                try:
                    answer = ai_client.ask(question, cfg)
                except Exception:
                    return self._send_json(502, {'error': 'ai_unavailable'})
                if compliance.has_banned(answer):
                    return self._send_json(200, {'answer': compliance.SAFE_FALLBACK,
                                                 'cached': False})
                ai_cache.put_cached(conn, question, answer)
                return self._send_json(200, {'answer': answer, 'cached': False})
            finally:
                conn.close()

    return Handler


def run(db_path=db_module.DEFAULT_DB_PATH, host='0.0.0.0', port=8092):
    db_module.init_db(db_path)
    conn = db_module.get_conn(db_path)
    ai_cache.ensure_table(conn)
    conn.close()
    cfg = ai_client.load_cfg()
    httpd = HTTPServer((host, port), make_handler(db_path, cfg))
    print(f'[finrookie-ai] listening on {host}:{port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run()
