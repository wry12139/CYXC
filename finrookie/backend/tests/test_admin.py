import os, tempfile, unittest
import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import auth, db

try:
    import admin
except ModuleNotFoundError:
    admin = None


class TestAdmin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        db.init_db(self.tmp)
        self.conn = db.get_conn(self.tmp)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_ensure_admin_exists_creates_default_admin(self):
        self.assertIsNotNone(admin, 'admin module should exist')

        admin.ensure_admin_exists(self.conn)

        row = self.conn.execute(
            "SELECT username, password_hash, salt, is_admin FROM users WHERE username='admin'"
        ).fetchone()
        self.assertIsNotNone(row)
        username, password_hash, salt, is_admin_flag = row
        self.assertEqual(username, 'admin')
        self.assertTrue(password_hash)
        self.assertTrue(salt)
        self.assertEqual(is_admin_flag, 1)
        self.assertTrue(auth.verify_password('admin123', salt, password_hash))

    def test_ensure_admin_exists_is_idempotent(self):
        self.assertIsNotNone(admin, 'admin module should exist')

        admin.ensure_admin_exists(self.conn)
        admin.ensure_admin_exists(self.conn)

        count = self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE username='admin'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_is_admin_returns_true_only_for_admin_users(self):
        self.assertIsNotNone(admin, 'admin module should exist')

        self.conn.execute(
            "INSERT INTO users (username,password_hash,salt,created_at,is_admin) VALUES (?,?,?,?,?)",
            ('normal', 'h1', 's1', 't1', 0),
        )
        self.conn.execute(
            "INSERT INTO users (username,password_hash,salt,created_at,is_admin) VALUES (?,?,?,?,?)",
            ('boss', 'h2', 's2', 't2', 1),
        )
        self.conn.commit()

        normal_id = self.conn.execute(
            "SELECT id FROM users WHERE username='normal'"
        ).fetchone()[0]
        boss_id = self.conn.execute(
            "SELECT id FROM users WHERE username='boss'"
        ).fetchone()[0]

        self.assertFalse(admin.is_admin(self.conn, normal_id))
        self.assertTrue(admin.is_admin(self.conn, boss_id))
        self.assertFalse(admin.is_admin(self.conn, 999999))


if __name__ == '__main__':
    unittest.main()
