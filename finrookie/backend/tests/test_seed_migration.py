import os, sys, tempfile, shutil, json, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import db, content

try:
    import migrate_seed_data
except ModuleNotFoundError:
    migrate_seed_data = None


class TestSeedMigration(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.mktemp(suffix='.db')
        self.tmp_dir = tempfile.mkdtemp()
        db.init_db(self.tmp_db)
        self.conn = db.get_conn(self.tmp_db)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.tmp_db):
            os.remove(self.tmp_db)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_json(self, filename, data):
        path = os.path.join(self.tmp_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def test_create_content_accepts_explicit_content_id(self):
        self.conn.execute(
            "INSERT INTO users (username,password_hash,salt,created_at,is_admin) VALUES (?,?,?,?,?)",
            ('seed', 'h', 's', 't', 0),
        )
        self.conn.commit()

        content_id = content.create_content(
            self.conn,
            'knowledge_card',
            {'title': '基金是什么'},
            'seed',
            content_id='c001',
        )

        self.assertEqual(content_id, 'c001')
        item = content.get_content(self.conn, 'c001')
        self.assertIsNotNone(item)
        self.assertEqual(item['id'], 'c001')
        self.assertEqual(item['created_by'], 'seed')

    def test_migrate_seed_data_imports_seed_files_and_is_idempotent(self):
        self.assertIsNotNone(migrate_seed_data, 'migrate_seed_data module should exist')

        self._write_json('knowledge-cards.json', [{'id': 'c001', 'title': '基金', 'body': 'x'}])
        self._write_json('quiz.json', [{'id': 'q001', 'stem': '题目'}])
        self._write_json('glossary.json', {'ETF': '交易型开放式指数基金'})
        self._write_json('articles.json', [{'id': 'a001', 'title': '文章', 'body': 'y'}])

        migrate_seed_data.migrate_seed_data(self.conn, self.tmp_dir)

        seed_user = self.conn.execute(
            "SELECT username FROM users WHERE username='seed'"
        ).fetchone()
        self.assertIsNotNone(seed_user)

        items = content.list_content(self.conn)
        self.assertEqual({item['id'] for item in items}, {'c001', 'q001', 'ETF', 'a001'})
        self.assertEqual({item['type'] for item in items}, {'knowledge_card', 'quiz', 'term', 'article'})
        self.assertTrue(all(item['created_by'] == 'seed' for item in items))
        self.assertEqual(content.get_content(self.conn, 'ETF')['data'], {'term': 'ETF', 'definition': '交易型开放式指数基金'})

        versions_before = self.conn.execute('SELECT COUNT(*) FROM content_versions').fetchone()[0]
        migrate_seed_data.migrate_seed_data(self.conn, self.tmp_dir)
        items_after = self.conn.execute('SELECT COUNT(*) FROM content_items').fetchone()[0]
        versions_after = self.conn.execute('SELECT COUNT(*) FROM content_versions').fetchone()[0]

        self.assertEqual(items_after, 4)
        self.assertEqual(versions_after, versions_before)


if __name__ == '__main__':
    unittest.main()
