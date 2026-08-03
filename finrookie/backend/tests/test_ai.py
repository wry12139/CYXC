import os, sys, unittest
import sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compliance
import db as db_module
import ai_cache

class TestCompliance(unittest.TestCase):
    def test_has_banned_detects_violation(self):
        self.assertTrue(compliance.has_banned("这只股票必涨"))
    def test_has_banned_clean_text(self):
        self.assertEqual(compliance.has_banned("ETF 是一种基金"), [])
    def test_input_blocked_on_buy_intent(self):
        self.assertTrue(compliance.input_blocked("我该不该买入贵州茅台"))
    def test_input_allowed_concept(self):
        self.assertFalse(compliance.input_blocked("什么是ETF"))
    def test_safe_fallback_exists(self):
        self.assertIn("概念", compliance.SAFE_FALLBACK)

class TestAiCache(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        ai_cache.ensure_table(self.conn)
    def tearDown(self):
        self.conn.close()
    def test_normalize_ignores_space_and_case(self):
        self.assertEqual(ai_cache.normalize("什么是 ETF"), ai_cache.normalize("什么是etf"))
    def test_cache_miss_returns_none(self):
        self.assertIsNone(ai_cache.get_cached(self.conn, "什么是可转债"))
    def test_put_then_get_hits(self):
        ai_cache.put_cached(self.conn, "什么是ETF", "ETF是一种基金")
        self.assertEqual(ai_cache.get_cached(self.conn, "什么是 ETF"), "ETF是一种基金")
    def test_table_has_no_user_id_column(self):
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(ai_cache)").fetchall()]
        self.assertNotIn("user_id", cols)

if __name__ == '__main__':
    unittest.main()
