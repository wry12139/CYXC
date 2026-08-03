import os, sys, unittest
import sqlite3
import json
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
        question = "什么是ETF"
        with mock.patch('urllib.request.urlopen', return_value=fake) as mock_urlopen:
            out = ai_client.ask(question, cfg)
        self.assertEqual(out, "ETF是一种基金")
        req = mock_urlopen.call_args.args[0]
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 20)
        self.assertIn("context", mock_urlopen.call_args.kwargs)
        self.assertIsNotNone(mock_urlopen.call_args.kwargs["context"])
        self.assertTrue(req.full_url.endswith("/v1/chat/completions"))
        self.assertEqual(req.get_header("Authorization"), "Bearer k")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][0]["content"], ai_client.SYSTEM_PROMPT)
        self.assertEqual(payload["messages"][1]["content"], question)

    def test_system_prompt_forbids_recommendation(self):
        self.assertIn("不", ai_client.SYSTEM_PROMPT)
        self.assertTrue("推荐" in ai_client.SYSTEM_PROMPT or "买卖" in ai_client.SYSTEM_PROMPT)


import threading, tempfile
import json as _json
import urllib.request as _req
from http.server import HTTPServer
import auth
import ai_server


class TestAiServer(unittest.TestCase):
    def _fresh_db(self):
        f = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        f.close()
        db_module.init_db(f.name)
        conn = db_module.get_conn(f.name)
        ai_cache.ensure_table(conn)
        conn.close()
        return f.name

    def _make_user(self, db_path, username='u'):
        conn = db_module.get_conn(db_path)
        conn.execute(
            "INSERT INTO users (username,password_hash,salt,created_at) VALUES (?,?,?,?)",
            (username, 'h', 's', 't'))
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0]
        token = auth.create_session(conn, uid)
        conn.close()
        return token

    def _start(self, db_path, cfg):
        handler = ai_server.make_handler(db_path, cfg)
        httpd = HTTPServer(('127.0.0.1', 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return httpd, port

    def _post(self, port, payload, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = _req.Request(f'http://127.0.0.1:{port}/api/ask',
                           data=_json.dumps(payload).encode('utf-8'),
                           headers=headers)
        return _req.urlopen(req)

    _CFG = {"FR_AI_KEY": "k", "FR_AI_BASE": "https://x", "FR_AI_MODEL": "m"}

    def test_missing_token_returns_401(self):
        db_path = self._fresh_db()
        httpd, port = self._start(db_path, self._CFG)
        try:
            self._post(port, {"question": "什么是ETF"})
            self.fail("should 401")
        except _req.HTTPError as e:
            self.assertEqual(e.code, 401)
        finally:
            httpd.shutdown()

    def test_bad_question_returns_400(self):
        db_path = self._fresh_db()
        token = self._make_user(db_path)
        httpd, port = self._start(db_path, self._CFG)
        try:
            self._post(port, {"question": "   "}, token=token)
            self.fail("should 400")
        except _req.HTTPError as e:
            self.assertEqual(e.code, 400)
        finally:
            httpd.shutdown()

    def test_non_utf8_body_returns_400_not_crash(self):
        db_path = self._fresh_db()
        token = self._make_user(db_path)
        httpd, port = self._start(db_path, self._CFG)
        try:
            # 模拟客户端误发 GBK 编码的中文 body(非法 UTF-8),不应让服务崩溃
            raw = '{"question":"什么是ETF"}'.encode('gbk')
            req = _req.Request(f'http://127.0.0.1:{port}/api/ask', data=raw,
                               headers={'Content-Type': 'application/json',
                                        'Authorization': 'Bearer ' + token})
            _req.urlopen(req)
            self.fail("should 400")
        except _req.HTTPError as e:
            self.assertEqual(e.code, 400)
        finally:
            httpd.shutdown()

    def _post_raw(self, port, raw_bytes, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = _req.Request(f'http://127.0.0.1:{port}/api/ask',
                           data=raw_bytes, headers=headers)
        return _req.urlopen(req)

    def test_non_object_json_returns_400_not_crash(self):
        # 合法 JSON 但非对象(数组/字符串)不应让 data.get 抛 AttributeError → 500
        db_path = self._fresh_db()
        token = self._make_user(db_path)
        httpd, port = self._start(db_path, self._CFG)
        try:
            for raw in (b'[]', b'"hi"', b'123', b'null'):
                try:
                    self._post_raw(port, raw, token=token)
                    self.fail("should 400 for %r" % raw)
                except _req.HTTPError as e:
                    self.assertEqual(e.code, 400, "body %r" % raw)
        finally:
            httpd.shutdown()

    def test_expired_token_returns_401(self):
        db_path = self._fresh_db()
        conn = db_module.get_conn(db_path)
        conn.execute(
            "INSERT INTO users (username,password_hash,salt,created_at) VALUES (?,?,?,?)",
            ('exp', 'h', 's', 't'))
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE username='exp'").fetchone()[0]
        # 直接插一条已过期会话(过期时间在过去)
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        conn.execute(
            "INSERT INTO sessions (token,user_id,created_at,expires_at) VALUES (?,?,?,?)",
            ('expiredtok', uid, past, past))
        conn.commit()
        conn.close()
        httpd, port = self._start(db_path, self._CFG)
        try:
            self._post(port, {"question": "什么是ETF"}, token='expiredtok')
            self.fail("should 401")
        except _req.HTTPError as e:
            self.assertEqual(e.code, 401)
        finally:
            httpd.shutdown()

    def test_input_blocked_returns_fallback_without_calling_ai(self):
        db_path = self._fresh_db()
        token = self._make_user(db_path)
        httpd, port = self._start(db_path, self._CFG)
        try:
            with mock.patch('ai_client.ask') as m:
                body = _json.loads(self._post(
                    port, {"question": "我该不该买贵州茅台"}, token=token).read())
            self.assertEqual(body['answer'], compliance.SAFE_FALLBACK)
            self.assertTrue(body['blocked'])
            m.assert_not_called()
        finally:
            httpd.shutdown()

    def test_valid_token_cache_miss_calls_ai_and_caches(self):
        db_path = self._fresh_db()
        token = self._make_user(db_path)
        httpd, port = self._start(db_path, self._CFG)
        try:
            with mock.patch('ai_client.ask', return_value="ETF是一种基金") as m:
                body = _json.loads(self._post(
                    port, {"question": "什么是ETF"}, token=token).read())
                self.assertEqual(body['answer'], "ETF是一种基金")
                self.assertFalse(body['cached'])
                body2 = _json.loads(self._post(
                    port, {"question": "什么是 ETF"}, token=token).read())
                self.assertTrue(body2['cached'])
                self.assertEqual(m.call_count, 1)
        finally:
            httpd.shutdown()

    def test_ai_failure_returns_502(self):
        db_path = self._fresh_db()
        token = self._make_user(db_path)
        httpd, port = self._start(db_path, self._CFG)
        try:
            with mock.patch('ai_client.ask', side_effect=RuntimeError("boom")):
                self._post(port, {"question": "什么是量化交易"}, token=token)
                self.fail("should 502")
        except _req.HTTPError as e:
            self.assertEqual(e.code, 502)
        finally:
            httpd.shutdown()

    def test_banned_answer_replaced_with_fallback_not_cached(self):
        db_path = self._fresh_db()
        token = self._make_user(db_path)
        httpd, port = self._start(db_path, self._CFG)
        try:
            with mock.patch('ai_client.ask', return_value="这只票必涨,建议买入") as m:
                body = _json.loads(self._post(
                    port, {"question": "帮我看看行情"}, token=token).read())
                self.assertEqual(body['answer'], compliance.SAFE_FALLBACK)
                self.assertFalse(body['cached'])
                # 违规答案不入缓存:再问仍会调 AI
                self._post(port, {"question": "帮我看看行情"}, token=token).read()
                self.assertEqual(m.call_count, 2)
        finally:
            httpd.shutdown()


if __name__ == '__main__':
    unittest.main()
