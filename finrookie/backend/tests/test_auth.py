import os, unittest
import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import auth
import tempfile, db
from datetime import datetime, timedelta, timezone

class TestPassword(unittest.TestCase):
    def test_hash_returns_hash_and_salt(self):
        h, s = auth.hash_password('secret123')
        self.assertTrue(h and s)
        self.assertNotEqual(h, 'secret123')  # 不是明文

    def test_same_password_same_salt_same_hash(self):
        h1, s = auth.hash_password('secret123')
        h2, _ = auth.hash_password('secret123', s)
        self.assertEqual(h1, h2)

    def test_different_salt_different_hash(self):
        h1, _ = auth.hash_password('secret123')
        h2, _ = auth.hash_password('secret123')
        self.assertNotEqual(h1, h2)  # 随机盐

    def test_verify_correct_and_wrong(self):
        h, s = auth.hash_password('secret123')
        self.assertTrue(auth.verify_password('secret123', s, h))
        self.assertFalse(auth.verify_password('wrongpw', s, h))

class TestSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        db.init_db(self.tmp)
        self.conn = db.get_conn(self.tmp)
        self.conn.execute("INSERT INTO users (username,password_hash,salt,created_at) VALUES ('u','h','s','t')")
        self.conn.commit()
        self.uid = self.conn.execute("SELECT id FROM users WHERE username='u'").fetchone()[0]
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.tmp): os.remove(self.tmp)

    def test_create_then_lookup(self):
        token = auth.create_session(self.conn, self.uid)
        self.assertEqual(auth.lookup_session(self.conn, token), self.uid)

    def test_lookup_unknown_returns_none(self):
        self.assertIsNone(auth.lookup_session(self.conn, 'nope'))

    def test_expired_returns_none(self):
        token = auth.create_session(self.conn, self.uid, ttl_days=-1)  # 已过期
        self.assertIsNone(auth.lookup_session(self.conn, token))

    def test_delete_invalidates(self):
        token = auth.create_session(self.conn, self.uid)
        auth.delete_session(self.conn, token)
        self.assertIsNone(auth.lookup_session(self.conn, token))

if __name__ == '__main__':
    unittest.main()
