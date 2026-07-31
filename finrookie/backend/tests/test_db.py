import os, tempfile, sqlite3, unittest
import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import db

class TestDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
    def tearDown(self):
        if os.path.exists(self.tmp): os.remove(self.tmp)

    def test_init_creates_three_tables(self):
        db.init_db(self.tmp)
        conn = db.get_conn(self.tmp)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        self.assertTrue({'users', 'sessions', 'user_data'}.issubset(names))

    def test_init_is_idempotent(self):
        db.init_db(self.tmp)
        db.init_db(self.tmp)  # 第二次不应报错
        conn = db.get_conn(self.tmp)
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_username_is_unique(self):
        db.init_db(self.tmp)
        conn = db.get_conn(self.tmp)
        conn.execute("INSERT INTO users (username,password_hash,salt,created_at) VALUES ('a','h','s','t')")
        conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO users (username,password_hash,salt,created_at) VALUES ('a','h2','s2','t2')")
            conn.commit()
        conn.close()

if __name__ == '__main__':
    unittest.main()
