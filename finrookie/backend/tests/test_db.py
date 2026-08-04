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

    def test_init_creates_content_items_table(self):
        db.init_db(self.tmp)
        conn = db.get_conn(self.tmp)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='content_items'"
        ).fetchone()
        columns = {
            column[1]: column[2]
            for column in conn.execute("PRAGMA table_info(content_items)").fetchall()
        }
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(columns['id'], 'TEXT')
        self.assertEqual(columns['type'], 'TEXT')
        self.assertEqual(columns['data'], 'JSON')
        self.assertEqual(columns['created_by'], 'TEXT')
        self.assertEqual(columns['created_at'], 'TEXT')
        self.assertEqual(columns['updated_at'], 'TEXT')

    def test_init_creates_content_versions_table(self):
        db.init_db(self.tmp)
        conn = db.get_conn(self.tmp)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='content_versions'"
        ).fetchone()
        columns = {
            column[1]: column[2]
            for column in conn.execute("PRAGMA table_info(content_versions)").fetchall()
        }
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(columns['id'], 'TEXT')
        self.assertEqual(columns['content_id'], 'TEXT')
        self.assertEqual(columns['type'], 'TEXT')
        self.assertEqual(columns['changed_by'], 'TEXT')
        self.assertEqual(columns['changed_at'], 'TEXT')
        self.assertEqual(columns['action'], 'TEXT')
        self.assertEqual(columns['diff'], 'JSON')

    def test_init_adds_is_admin_column_to_users(self):
        db.init_db(self.tmp)
        conn = db.get_conn(self.tmp)
        columns = {
            column[1]: column[2]
            for column in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        conn.close()

        self.assertIn('is_admin', columns)
        self.assertEqual(columns['is_admin'], 'INTEGER')

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
