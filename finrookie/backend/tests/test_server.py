import os, sys, tempfile, threading, json, unittest
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import db, server, admin


def _req(method, url, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b'{}')
    except HTTPError as e:
        with e:
            raw = e.read() or b''
            return e.code, json.loads(raw or b'{}')


class ServerEndpointTestBase(unittest.TestCase):
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
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def _register(self, username, password='pw123456'):
        return _req('POST', f'{self.base}/api/register', {'username': username, 'password': password})

    def _login(self, username, password='pw123456'):
        self._register(username, password)
        _, body = _req('POST', f'{self.base}/api/login', {'username': username, 'password': password})
        return body['token']

    def _make_admin(self, username):
        conn = db.get_conn(self.tmp)
        try:
            conn.execute('UPDATE users SET is_admin=1 WHERE username=?', (username,))
            conn.commit()
        finally:
            conn.close()

    def _admin_token(self, username='admin_user'):
        token = self._login(username)
        self._make_admin(username)
        return token


class TestRecommendationsEndpoint(ServerEndpointTestBase):
    def test_recommendations_requires_auth(self):
        status, body = _req('GET', f'{self.base}/api/recommendations?num=3')
        self.assertEqual(status, 401)
        self.assertEqual(body.get('error'), 'unauthorized')

    def test_recommendations_returns_list_for_authed_user(self):
        token = self._login('learner')
        status, body = _req('GET', f'{self.base}/api/recommendations?num=2', token=token)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)


class TestAdminContentEndpoints(ServerEndpointTestBase):
    def test_admin_contents_list_requires_admin(self):
        token = self._login('normal_user')
        status, body = _req('GET', f'{self.base}/api/admin/contents', token=token)
        self.assertEqual(status, 403)
        self.assertEqual(body.get('error'), 'forbidden')

    def test_admin_can_crud_content_and_view_versions(self):
        token = self._admin_token()

        status, created = _req(
            'POST',
            f'{self.base}/api/admin/contents',
            {'type': 'knowledge_card', 'data': {'title': 'ETF 入门', 'topics': ['fund'], 'difficulty': 'L1'}},
            token=token,
        )
        self.assertEqual(status, 201)
        content_id = created.get('id')
        self.assertTrue(content_id)

        status, items = _req('GET', f'{self.base}/api/admin/contents?type=knowledge_card', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], content_id)
        self.assertEqual(items[0]['data']['title'], 'ETF 入门')

        status, updated = _req(
            'PUT',
            f'{self.base}/api/admin/contents/{content_id}',
            {'data': {'title': 'ETF 进阶', 'topics': ['fund'], 'difficulty': 'L2'}},
            token=token,
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated.get('id'), content_id)

        status, versions = _req('GET', f'{self.base}/api/admin/contents/{content_id}/versions', token=token)
        self.assertEqual(status, 200)
        self.assertEqual([item['action'] for item in versions], ['update', 'create'])

        status, deleted = _req('DELETE', f'{self.base}/api/admin/contents/{content_id}', token=token)
        self.assertEqual(status, 200)
        self.assertTrue(deleted.get('ok'))

        status, versions = _req('GET', f'{self.base}/api/admin/contents/{content_id}/versions', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(versions, [])

        status, items = _req('GET', f'{self.base}/api/admin/contents?type=knowledge_card', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(items, [])


if __name__ == '__main__':
    unittest.main()
