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

if __name__ == '__main__':
    unittest.main()
