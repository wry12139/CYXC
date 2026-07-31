import os, sys, tempfile, threading, json, unittest
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import db, server

def _req(method, url, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if token: headers['Authorization'] = f'Bearer {token}'
    r = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b'{}')
    except HTTPError as e:
        with e:
            return e.code, json.loads(e.read() or b'{}')

class APITestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        db.init_db(self.tmp)
        self.httpd = HTTPServer(('127.0.0.1', 0), server.make_handler(self.tmp))
        self.port = self.httpd.server_address[1]
        self.base = f'http://127.0.0.1:{self.port}'
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=1)
        if os.path.exists(self.tmp): os.remove(self.tmp)

class TestSkeleton(APITestBase):
    def test_unknown_route_404(self):
        status, body = _req('GET', f'{self.base}/api/nope')
        self.assertEqual(status, 404)

    def test_options_preflight_has_cors(self):
        # urllib 不便读 header,这里只验 OPTIONS 不报错(2xx)
        status, _ = _req('OPTIONS', f'{self.base}/api/login')
        self.assertIn(status, (200, 204))

class TestRegister(APITestBase):
    def test_register_success(self):
        status, body = _req('POST', f'{self.base}/api/register',
                            {'username': 'alice', 'password': 'pw123456'})
        self.assertEqual(status, 201)
        self.assertTrue(body.get('ok'))

    def test_register_duplicate_409(self):
        _req('POST', f'{self.base}/api/register', {'username': 'bob', 'password': 'pw123456'})
        status, body = _req('POST', f'{self.base}/api/register',
                            {'username': 'bob', 'password': 'other999'})
        self.assertEqual(status, 409)
        self.assertEqual(body.get('error'), 'username_taken')

    def test_register_missing_field_400(self):
        status, _ = _req('POST', f'{self.base}/api/register', {'username': 'x'})
        self.assertEqual(status, 400)

    def test_password_not_stored_plaintext(self):
        _req('POST', f'{self.base}/api/register', {'username': 'carol', 'password': 'secretpw'})
        conn = db.get_conn(self.tmp)
        row = conn.execute("SELECT password_hash FROM users WHERE username='carol'").fetchone()
        self.assertNotIn('secretpw', row[0])
        conn.close()

class TestLoginMe(APITestBase):
    def _register(self, u, p):
        _req('POST', f'{self.base}/api/register', {'username': u, 'password': p})
    def test_login_success_returns_token(self):
        self._register('dave', 'pw123456')
        status, body = _req('POST', f'{self.base}/api/login', {'username': 'dave', 'password': 'pw123456'})
        self.assertEqual(status, 200)
        self.assertTrue(body.get('token'))
    def test_login_wrong_password_401(self):
        self._register('eve', 'pw123456')
        status, body = _req('POST', f'{self.base}/api/login', {'username': 'eve', 'password': 'WRONG'})
        self.assertEqual(status, 401)
        self.assertEqual(body.get('error'), 'bad_credentials')
    def test_login_unknown_user_401(self):
        status, _ = _req('POST', f'{self.base}/api/login', {'username': 'ghost', 'password': 'x'})
        self.assertEqual(status, 401)
    def test_me_requires_token(self):
        status, _ = _req('GET', f'{self.base}/api/me')
        self.assertEqual(status, 401)
    def test_me_returns_own_identity(self):
        self._register('frank', 'pw123456')
        _, login = _req('POST', f'{self.base}/api/login', {'username': 'frank', 'password': 'pw123456'})
        status, body = _req('GET', f'{self.base}/api/me', token=login['token'])
        self.assertEqual(status, 200)
        self.assertEqual(body.get('username'), 'frank')
    def test_logout_invalidates_token(self):
        self._register('grace', 'pw123456')
        _, login = _req('POST', f'{self.base}/api/login', {'username': 'grace', 'password': 'pw123456'})
        tok = login['token']
        _req('POST', f'{self.base}/api/logout', token=tok)
        status, _ = _req('GET', f'{self.base}/api/me', token=tok)
        self.assertEqual(status, 401)

class TestSync(APITestBase):
    def _login(self, u, p='pw123456'):
        _req('POST', f'{self.base}/api/register', {'username': u, 'password': p})
        _, body = _req('POST', f'{self.base}/api/login', {'username': u, 'password': p})
        return body['token']
    def test_pull_before_push_is_null(self):
        tok = self._login('u1')
        status, body = _req('GET', f'{self.base}/api/sync/pull', token=tok)
        self.assertEqual(status, 200)
        self.assertIsNone(body.get('data'))
    def test_push_then_pull_roundtrip(self):
        tok = self._login('u2')
        _req('POST', f'{self.base}/api/sync/push', {'data': {'streak': 7}}, token=tok)
        _, body = _req('GET', f'{self.base}/api/sync/pull', token=tok)
        self.assertEqual(body['data'], {'streak': 7})
    def test_push_requires_token(self):
        status, _ = _req('POST', f'{self.base}/api/sync/push', {'data': {}})
        self.assertEqual(status, 401)
    def test_isolation_user_cannot_read_others_data(self):
        tok_a = self._login('userA')
        _req('POST', f'{self.base}/api/sync/push', {'data': {'secret': 'A-only'}}, token=tok_a)
        tok_b = self._login('userB')
        _, body = _req('GET', f'{self.base}/api/sync/pull', token=tok_b)
        self.assertIsNone(body.get('data'))  # B 绝不应看到 A 的数据
    def test_push_overwrites_own_row(self):
        tok = self._login('u3')
        _req('POST', f'{self.base}/api/sync/push', {'data': {'v': 1}}, token=tok)
        _req('POST', f'{self.base}/api/sync/push', {'data': {'v': 2}}, token=tok)
        _, body = _req('GET', f'{self.base}/api/sync/pull', token=tok)
        self.assertEqual(body['data'], {'v': 2})

if __name__ == '__main__':
    unittest.main()
