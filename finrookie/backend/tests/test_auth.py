import os, unittest
import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import auth

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

if __name__ == '__main__':
    unittest.main()
