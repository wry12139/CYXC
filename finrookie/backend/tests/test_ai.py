import os, sys, unittest
import sqlite3
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compliance
import db as db_module
import ai_cache
import ai_client

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

class TestAiClient(unittest.TestCase):
    def test_ask_parses_answer(self):
        fake = mock.Mock()
        fake.read.return_value = ('{"choices":[{"message":{"content":"ETF是一种基金"}}]}').encode('utf-8')
        cfg = {"FR_AI_KEY": "k", "FR_AI_BASE": "https://x", "FR_AI_MODEL": "claude-haiku-4-5-20251001"}
        with mock.patch('urllib.request.urlopen', return_value=fake):
            out = ai_client.ask("什么是ETF", cfg)
        self.assertEqual(out, "ETF是一种基金")

    def test_system_prompt_forbids_recommendation(self):
        self.assertIn("不", ai_client.SYSTEM_PROMPT)
        self.assertTrue("推荐" in ai_client.SYSTEM_PROMPT or "买卖" in ai_client.SYSTEM_PROMPT)

if __name__ == '__main__':
    unittest.main()
