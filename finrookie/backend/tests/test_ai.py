import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compliance

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

if __name__ == '__main__':
    unittest.main()
