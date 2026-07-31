# 财小白用户系统与后端 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为财小白加一个可选登录的用户系统,把学习数据从纯本地 localStorage 增量同步到内网服务器,为后续 AI 问答与后台分层推送打好数据地基。

**Architecture:** 本地优先——未登录时行为与现在完全一致(纯 localStorage);登录后数据镜像到后端(Python 标准库 `http.server` + `sqlite3`,建在现有服务器 `10.159.3.80:8091`)。写数据本地即时 + 防抖上云,登录时智能合并两份数据。前端改造集中在新增 `auth.js`/`sync.js` 与 store 层的一个 push 钩子,app.js 业务逻辑几乎不动。

**Tech Stack:** 后端 Python 3 标准库(`http.server`、`sqlite3`、`hashlib.pbkdf2_hmac`、`secrets`、`unittest`),零 pip 依赖;前端原生 ES module + Alpine(现状),纯函数用 node 断言验证。

## Global Constraints

- 后端**只用 Python 标准库**,不装任何 pip 包(延续服务器零依赖哲学)。
- 后端从**不信任前端传来的 user_id**;身份唯一来源是 `Authorization: Bearer <token>` 反查出的 user_id。
- 所有涉及用户数据的 SQL 查询**必须带 `WHERE user_id=<当前登录用户>`**;不存在任何"列出/查他人"接口。
- 密码**只存 `pbkdf2_hmac('sha256', pw, salt, 200000)` 加盐哈希**,永不存明文;比对用 `secrets.compare_digest`。
- token 用 `secrets.token_urlsafe(32)` 生成。
- 后端所有响应带 CORS 头允许前端(`8090`)跨源调用。
- 登录失败统一提示"用户名或密码错误",不区分是用户名还是密码错。
- 未登录 / 后端不可达 / token 失效时,前端一律回退到纯本地模式,**不白屏、不丢本地数据**。
- 后端服务器路径:`~/finrookie-app/backend/`,数据库 `~/finrookie-app/backend/finrookie.db`,端口 `8091`。
- 本地开发路径:`C:\Users\86184\finrookie\backend\`;本机与服务器均 Python 3.14。

---

## 文件结构

**后端(新增 `backend/` 子目录):**
- `backend/db.py` — SQLite 连接 + 建表(schema 唯一来源)
- `backend/auth.py` — 密码哈希/校验、会话 token 创建/查找/删除(纯逻辑,依赖 conn)
- `backend/server.py` — HTTP 请求处理:路由、CORS、JSON 读写、鉴权、6 个接口
- `backend/run.sh` — 启动脚本(建库 + 起服务)
- `backend/tests/test_auth.py` — auth 单元测试
- `backend/tests/test_api.py` — 接口集成测试(重点验隔离)

**前端(新增 2 文件 + 改 3 文件):**
- `js/merge.js` — 纯函数 `mergeState(local, remote)`(合并规则唯一来源)
- `js/auth.js` — register/login/logout + token 管理 + 登录态查询
- `js/sync.js` — pull(登录拉云端并合并)/ push(防抖上云)
- `js/store.js` — 【改】写操作后若已登录触发防抖 push
- `js/app.js` — 【改】init 若有 token 则 pull;"我的"页暴露登录态与动作
- `index.html` — 【改】"我的"页加登录/注册 UI + 登录状态显示
- `js/merge.test.mjs` — mergeState 的 node 断言

---

### Task 1: 数据库层(schema + 连接)

**Files:**
- Create: `backend/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces:
  - `DEFAULT_DB_PATH: str` — 默认库路径(相对 backend/)
  - `get_conn(db_path: str) -> sqlite3.Connection` — 返回开启外键的连接
  - `init_db(db_path: str) -> None` — 幂等建 3 张表

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_db.py
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
        self.assertTrue({'users', 'sessions', 'user_data'}.issubset(names))

    def test_init_is_idempotent(self):
        db.init_db(self.tmp)
        db.init_db(self.tmp)  # 第二次不应报错
        conn = db.get_conn(self.tmp)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_username_is_unique(self):
        db.init_db(self.tmp)
        conn = db.get_conn(self.tmp)
        conn.execute("INSERT INTO users (username,password_hash,salt,created_at) VALUES ('a','h','s','t')")
        conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO users (username,password_hash,salt,created_at) VALUES ('a','h2','s2','t2')")
            conn.commit()

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_db.py -v` 或 `python tests/test_db.py`
Expected: FAIL(`ModuleNotFoundError: No module named 'db'` 或 AttributeError)

- [ ] **Step 3: 写最小实现**

```python
# backend/db.py
import os, sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), 'finrookie.db')

def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path):
    conn = get_conn(db_path)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt          TEXT NOT NULL,
        created_at    TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token      TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS user_data (
        user_id    INTEGER PRIMARY KEY REFERENCES users(id),
        data_json  TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python tests/test_db.py`
Expected: PASS(3 tests OK)

- [ ] **Step 5: 提交**

```bash
git add backend/db.py backend/tests/test_db.py
git commit -m "feat(backend): add SQLite schema and connection layer"
```

---

### Task 2: 密码哈希与校验

**Files:**
- Create: `backend/auth.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Produces:
  - `hash_password(password: str, salt: str = None) -> tuple[str, str]` — 返回 `(hash_hex, salt_hex)`;不传 salt 则随机生成
  - `verify_password(password: str, salt: str, expected_hash: str) -> bool`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_auth.py
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python tests/test_auth.py`
Expected: FAIL(`module 'auth' has no attribute 'hash_password'`)

- [ ] **Step 3: 写最小实现**

```python
# backend/auth.py
import hashlib, secrets

_ITERATIONS = 200_000

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                             bytes.fromhex(salt), _ITERATIONS)
    return dk.hex(), salt

def verify_password(password, salt, expected_hash):
    calc, _ = hash_password(password, salt)
    return secrets.compare_digest(calc, expected_hash)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python tests/test_auth.py`
Expected: PASS(4 tests OK)

- [ ] **Step 5: 提交**

```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "feat(backend): add pbkdf2 password hashing and verification"
```

---

### Task 3: 会话 token(创建/查找/删除)

**Files:**
- Modify: `backend/auth.py`(追加 session 函数)
- Test: `backend/tests/test_auth.py`(追加 session 测试)

**Interfaces:**
- Consumes: `db.get_conn`, `db.init_db`(Task 1)
- Produces:
  - `create_session(conn, user_id: int, ttl_days: int = 30) -> str` — 返回 token 并写库
  - `lookup_session(conn, token: str) -> int | None` — 有效返回 user_id,失效/过期/不存在返回 None
  - `delete_session(conn, token: str) -> None`

- [ ] **Step 1: 写失败测试(追加到 test_auth.py)**

```python
# 追加到 backend/tests/test_auth.py 末尾(import 段加 tempfile, db)
import tempfile, db
from datetime import datetime, timedelta, timezone

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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python tests/test_auth.py`
Expected: FAIL(`module 'auth' has no attribute 'create_session'`)

- [ ] **Step 3: 写最小实现(追加到 auth.py)**

```python
# 追加到 backend/auth.py(顶部 import 增加 datetime)
from datetime import datetime, timedelta, timezone

def create_session(conn, user_id, ttl_days=30):
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=ttl_days)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, now.isoformat(), expires.isoformat()))
    conn.commit()
    return token

def lookup_session(conn, token):
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token=?", (token,)).fetchone()
    if not row:
        return None
    user_id, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        return None
    return user_id

def delete_session(conn, token):
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python tests/test_auth.py`
Expected: PASS(8 tests OK)

- [ ] **Step 5: 提交**

```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "feat(backend): add session token create/lookup/delete"
```

---

### Task 4: HTTP 服务骨架(路由 + CORS + JSON 助手)

**Files:**
- Create: `backend/server.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `db`, `auth`(Task 1-3)
- Produces:
  - `make_handler(db_path)` — 返回绑定该 db 的 `BaseHTTPRequestHandler` 子类(便于测试用临时库)
  - `run(db_path, host, port)` — 启动服务
  - 处理器内部助手:`_send_json(status, obj)`、`_read_json()`、`_cors()`、`_authed_uid()`(返回 user_id 或 None)
  - 全局路由:`OPTIONS *` 返回 204 + CORS;未知路径返回 404 JSON

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_api.py
import os, sys, tempfile, threading, json, unittest
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import db, server

def _req(method, url, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if token: headers['Authorization'] = f'Bearer {token}'
    r = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b'{}')
    except HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')

class APITestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        db.init_db(self.tmp)
        self.httpd = HTTPServer(('127.0.0.1', 0), server.make_handler(self.tmp))
        self.port = self.httpd.server_address[1]
        self.base = f'http://127.0.0.1:{self.port}'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
    def tearDown(self):
        self.httpd.shutdown()
        if os.path.exists(self.tmp): os.remove(self.tmp)

class TestSkeleton(APITestBase):
    def test_unknown_route_404(self):
        status, body = _req('GET', f'{self.base}/api/nope')
        self.assertEqual(status, 404)

    def test_options_preflight_has_cors(self):
        # urllib 不便读 header,这里只验 OPTIONS 不报错(2xx)
        status, _ = _req('OPTIONS', f'{self.base}/api/login')
        self.assertIn(status, (200, 204))

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python tests/test_api.py`
Expected: FAIL(`module 'server' has no attribute 'make_handler'`)

- [ ] **Step 3: 写最小实现**

```python
# backend/server.py
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import db as db_module
import auth

def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # 静默默认日志
            pass

        # ---- 助手 ----
        def _cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

        def _send_json(self, status, obj):
            payload = json.dumps(obj).encode('utf-8')
            self.send_response(status)
            self._cors()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _read_json(self):
            length = int(self.headers.get('Content-Length') or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length) or b'{}')
            except json.JSONDecodeError:
                return None  # 调用方据此返回 400

        def _authed_uid(self):
            hdr = self.headers.get('Authorization') or ''
            if not hdr.startswith('Bearer '):
                return None
            token = hdr[len('Bearer '):]
            conn = db_module.get_conn(db_path)
            try:
                return auth.lookup_session(conn, token)
            finally:
                conn.close()

        # ---- 路由 ----
        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            self._route('GET')

        def do_POST(self):
            self._route('POST')

        def _route(self, method):
            path = self.path.split('?')[0]
            # 后续 Task 5-7 在此登记路由;当前默认 404
            self._send_json(404, {'error': 'not_found'})

    return Handler

def run(db_path=db_module.DEFAULT_DB_PATH, host='0.0.0.0', port=8091):
    db_module.init_db(db_path)
    httpd = HTTPServer((host, port), make_handler(db_path))
    print(f'[finrookie-backend] listening on {host}:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python tests/test_api.py`
Expected: PASS(2 tests OK)

- [ ] **Step 5: 提交**

```bash
git add backend/server.py backend/tests/test_api.py
git commit -m "feat(backend): add HTTP server skeleton with routing and CORS"
```

---

### Task 5: 注册接口 `/api/register`

**Files:**
- Modify: `backend/server.py`(`_route` 内加 register 分支 + `_handle_register`)
- Test: `backend/tests/test_api.py`(追加 TestRegister)

**Interfaces:**
- Consumes: `auth.hash_password`, `db.get_conn`, `_read_json`, `_send_json`
- Produces: `POST /api/register {username, password}` → 201 `{ok:true}`;重复用户名 → 409 `{error:'username_taken'}`;缺字段/坏 JSON → 400

- [ ] **Step 1: 写失败测试(追加)**

```python
class TestRegister(APITestBase):
    def test_register_success(self):
        status, body = _req('POST', f'{self.base}/api/register',
                            {'username': 'alice', 'password': 'pw123456'})
        self.assertEqual(status, 201)
        self.assertTrue(body.get('ok'))

    def test_register_duplicate_409(self):
        _req('POST', f'{self.base}/api/register', {'username': 'bob', 'password': 'pw123456'})
        status, body = _req('POST', f'{self.base}/api/register',
                            {'username': 'bob', 'password': 'other999'})
        self.assertEqual(status, 409)
        self.assertEqual(body.get('error'), 'username_taken')

    def test_register_missing_field_400(self):
        status, _ = _req('POST', f'{self.base}/api/register', {'username': 'x'})
        self.assertEqual(status, 400)

    def test_password_not_stored_plaintext(self):
        _req('POST', f'{self.base}/api/register', {'username': 'carol', 'password': 'secretpw'})
        conn = db.get_conn(self.tmp)
        row = conn.execute("SELECT password_hash FROM users WHERE username='carol'").fetchone()
        self.assertNotIn('secretpw', row[0])
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python tests/test_api.py`
Expected: FAIL(register 返回 404)

- [ ] **Step 3: 写实现(修改 server.py)**

在 `_route` 的 404 之前加入分派;并添加处理方法:

```python
        def _route(self, method):
            path = self.path.split('?')[0]
            if method == 'POST' and path == '/api/register':
                return self._handle_register()
            self._send_json(404, {'error': 'not_found'})

        def _handle_register(self):
            from datetime import datetime, timezone
            data = self._read_json()
            if data is None:
                return self._send_json(400, {'error': 'bad_json'})
            username = (data.get('username') or '').strip()
            password = data.get('password') or ''
            if not username or not password:
                return self._send_json(400, {'error': 'missing_field'})
            h, salt = auth.hash_password(password)
            conn = db_module.get_conn(db_path)
            try:
                exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
                if exists:
                    return self._send_json(409, {'error': 'username_taken'})
                conn.execute(
                    "INSERT INTO users (username,password_hash,salt,created_at) VALUES (?,?,?,?)",
                    (username, h, salt, datetime.now(timezone.utc).isoformat()))
                conn.commit()
                return self._send_json(201, {'ok': True})
            finally:
                conn.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python tests/test_api.py`
Expected: PASS(TestRegister 4 tests + 之前的全通过)

- [ ] **Step 5: 提交**

```bash
git add backend/server.py backend/tests/test_api.py
git commit -m "feat(backend): add register endpoint"
```

---

### Task 6: 登录/登出/我的信息 `/api/login` `/api/logout` `/api/me`

**Files:**
- Modify: `backend/server.py`(`_route` 加 3 分支 + 3 处理方法)
- Test: `backend/tests/test_api.py`(追加 TestLoginMe)

**Interfaces:**
- Consumes: `auth.verify_password`, `auth.create_session`, `auth.delete_session`, `_authed_uid`
- Produces:
  - `POST /api/login {username, password}` → 200 `{token, username}`;错误 → 401 `{error:'bad_credentials'}`
  - `POST /api/logout`(带 token)→ 200 `{ok:true}`
  - `GET /api/me`(带 token)→ 200 `{user_id, username}`;无/失效 token → 401 `{error:'unauthorized'}`

- [ ] **Step 1: 写失败测试(追加)**

```python
class TestLoginMe(APITestBase):
    def _register(self, u, p):
        _req('POST', f'{self.base}/api/register', {'username': u, 'password': p})
    def test_login_success_returns_token(self):
        self._register('dave', 'pw123456')
        status, body = _req('POST', f'{self.base}/api/login', {'username': 'dave', 'password': 'pw123456'})
        self.assertEqual(status, 200)
        self.assertTrue(body.get('token'))
    def test_login_wrong_password_401(self):
        self._register('eve', 'pw123456')
        status, body = _req('POST', f'{self.base}/api/login', {'username': 'eve', 'password': 'WRONG'})
        self.assertEqual(status, 401)
        self.assertEqual(body.get('error'), 'bad_credentials')
    def test_login_unknown_user_401(self):
        status, _ = _req('POST', f'{self.base}/api/login', {'username': 'ghost', 'password': 'x'})
        self.assertEqual(status, 401)
    def test_me_requires_token(self):
        status, _ = _req('GET', f'{self.base}/api/me')
        self.assertEqual(status, 401)
    def test_me_returns_own_identity(self):
        self._register('frank', 'pw123456')
        _, login = _req('POST', f'{self.base}/api/login', {'username': 'frank', 'password': 'pw123456'})
        status, body = _req('GET', f'{self.base}/api/me', token=login['token'])
        self.assertEqual(status, 200)
        self.assertEqual(body.get('username'), 'frank')
    def test_logout_invalidates_token(self):
        self._register('grace', 'pw123456')
        _, login = _req('POST', f'{self.base}/api/login', {'username': 'grace', 'password': 'pw123456'})
        tok = login['token']
        _req('POST', f'{self.base}/api/logout', token=tok)
        status, _ = _req('GET', f'{self.base}/api/me', token=tok)
        self.assertEqual(status, 401)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python tests/test_api.py`
Expected: FAIL(login/me/logout 返回 404)

- [ ] **Step 3: 写实现(修改 server.py 的 `_route` 与新增方法)**

```python
        def _route(self, method):
            path = self.path.split('?')[0]
            if method == 'POST' and path == '/api/register':
                return self._handle_register()
            if method == 'POST' and path == '/api/login':
                return self._handle_login()
            if method == 'POST' and path == '/api/logout':
                return self._handle_logout()
            if method == 'GET' and path == '/api/me':
                return self._handle_me()
            self._send_json(404, {'error': 'not_found'})

        def _handle_login(self):
            data = self._read_json()
            if data is None:
                return self._send_json(400, {'error': 'bad_json'})
            username = (data.get('username') or '').strip()
            password = data.get('password') or ''
            conn = db_module.get_conn(db_path)
            try:
                row = conn.execute(
                    "SELECT id, password_hash, salt FROM users WHERE username=?",
                    (username,)).fetchone()
                if not row or not auth.verify_password(password, row[2], row[1]):
                    return self._send_json(401, {'error': 'bad_credentials'})
                token = auth.create_session(conn, row[0])
                return self._send_json(200, {'token': token, 'username': username})
            finally:
                conn.close()

        def _handle_logout(self):
            hdr = self.headers.get('Authorization') or ''
            token = hdr[len('Bearer '):] if hdr.startswith('Bearer ') else ''
            conn = db_module.get_conn(db_path)
            try:
                if token:
                    auth.delete_session(conn, token)
            finally:
                conn.close()
            return self._send_json(200, {'ok': True})

        def _handle_me(self):
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            conn = db_module.get_conn(db_path)
            try:
                row = conn.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
                return self._send_json(200, {'user_id': uid, 'username': row[0]})
            finally:
                conn.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python tests/test_api.py`
Expected: PASS(TestLoginMe 6 tests + 全部)

- [ ] **Step 5: 提交**

```bash
git add backend/server.py backend/tests/test_api.py
git commit -m "feat(backend): add login, logout, and me endpoints"
```

---

### Task 7: 数据同步 `/api/sync/pull` `/api/sync/push`(隔离验证核心)

**Files:**
- Modify: `backend/server.py`(`_route` 加 2 分支 + 2 处理方法)
- Test: `backend/tests/test_api.py`(追加 TestSync,含隔离用例)

**Interfaces:**
- Consumes: `_authed_uid`, `_read_json`, `db.get_conn`
- Produces:
  - `GET /api/sync/pull`(带 token)→ 200 `{data: <obj|null>, updated_at: <str|null>}`;无 token → 401
  - `POST /api/sync/push {data: <obj>}`(带 token)→ 200 `{ok:true, updated_at}`;无 token → 401;data 非对象 → 400
  - 隔离保证:push/pull 只读写 `WHERE user_id = _authed_uid()`

- [ ] **Step 1: 写失败测试(追加,隔离是重点)**

```python
class TestSync(APITestBase):
    def _login(self, u, p='pw123456'):
        _req('POST', f'{self.base}/api/register', {'username': u, 'password': p})
        _, body = _req('POST', f'{self.base}/api/login', {'username': u, 'password': p})
        return body['token']
    def test_pull_before_push_is_null(self):
        tok = self._login('u1')
        status, body = _req('GET', f'{self.base}/api/sync/pull', token=tok)
        self.assertEqual(status, 200)
        self.assertIsNone(body.get('data'))
    def test_push_then_pull_roundtrip(self):
        tok = self._login('u2')
        _req('POST', f'{self.base}/api/sync/push', {'data': {'streak': 7}}, token=tok)
        _, body = _req('GET', f'{self.base}/api/sync/pull', token=tok)
        self.assertEqual(body['data'], {'streak': 7})
    def test_push_requires_token(self):
        status, _ = _req('POST', f'{self.base}/api/sync/push', {'data': {}})
        self.assertEqual(status, 401)
    def test_isolation_user_cannot_read_others_data(self):
        tok_a = self._login('userA')
        _req('POST', f'{self.base}/api/sync/push', {'data': {'secret': 'A-only'}}, token=tok_a)
        tok_b = self._login('userB')
        _, body = _req('GET', f'{self.base}/api/sync/pull', token=tok_b)
        self.assertIsNone(body.get('data'))  # B 绝不应看到 A 的数据
    def test_push_overwrites_own_row(self):
        tok = self._login('u3')
        _req('POST', f'{self.base}/api/sync/push', {'data': {'v': 1}}, token=tok)
        _req('POST', f'{self.base}/api/sync/push', {'data': {'v': 2}}, token=tok)
        _, body = _req('GET', f'{self.base}/api/sync/pull', token=tok)
        self.assertEqual(body['data'], {'v': 2})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python tests/test_api.py`
Expected: FAIL(sync 返回 404)

- [ ] **Step 3: 写实现(修改 server.py)**

```python
        def _route(self, method):
            path = self.path.split('?')[0]
            if method == 'POST' and path == '/api/register':
                return self._handle_register()
            if method == 'POST' and path == '/api/login':
                return self._handle_login()
            if method == 'POST' and path == '/api/logout':
                return self._handle_logout()
            if method == 'GET' and path == '/api/me':
                return self._handle_me()
            if method == 'GET' and path == '/api/sync/pull':
                return self._handle_pull()
            if method == 'POST' and path == '/api/sync/push':
                return self._handle_push()
            self._send_json(404, {'error': 'not_found'})

        def _handle_pull(self):
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            conn = db_module.get_conn(db_path)
            try:
                row = conn.execute(
                    "SELECT data_json, updated_at FROM user_data WHERE user_id=?", (uid,)).fetchone()
                if not row:
                    return self._send_json(200, {'data': None, 'updated_at': None})
                return self._send_json(200, {'data': json.loads(row[0]), 'updated_at': row[1]})
            finally:
                conn.close()

        def _handle_push(self):
            uid = self._authed_uid()
            if uid is None:
                return self._send_json(401, {'error': 'unauthorized'})
            payload = self._read_json()
            if payload is None or not isinstance(payload.get('data'), dict):
                return self._send_json(400, {'error': 'bad_data'})
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            data_json = json.dumps(payload['data'])
            conn = db_module.get_conn(db_path)
            try:
                conn.execute(
                    "INSERT INTO user_data (user_id, data_json, updated_at) VALUES (?,?,?) "
                    "ON CONFLICT(user_id) DO UPDATE SET data_json=excluded.data_json, updated_at=excluded.updated_at",
                    (uid, data_json, now))
                conn.commit()
                return self._send_json(200, {'ok': True, 'updated_at': now})
            finally:
                conn.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python tests/test_api.py`
Expected: PASS(TestSync 5 tests + 全部;隔离用例通过)

- [ ] **Step 5: 提交**

```bash
git add backend/server.py backend/tests/test_api.py
git commit -m "feat(backend): add sync pull/push with strict user isolation"
```

---

### Task 8: 启动脚本 + 全量后端自测

**Files:**
- Create: `backend/run.sh`
- Modify: `.gitignore`(忽略 `backend/finrookie.db` 与测试临时库)

**Interfaces:**
- Produces: `bash backend/run.sh` 建库并在 8091 起服务

- [ ] **Step 1: 写启动脚本**

```bash
# backend/run.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -c "import db; db.init_db(db.DEFAULT_DB_PATH); print('db ready')"
exec python3 server.py
```

- [ ] **Step 2: 追加 .gitignore**

在 `finrookie/.gitignore` 末尾追加:

```
# 后端运行时数据库(不入 git)
backend/finrookie.db
backend/**/*.db
```

- [ ] **Step 3: 跑全部后端测试**

Run: `cd backend && python tests/test_db.py && python tests/test_auth.py && python tests/test_api.py`
Expected: 三个文件全部 OK,零 fail

- [ ] **Step 4: 手动冒烟(可选,本机)**

Run: `cd backend && bash run.sh`(另开终端 curl 注册/登录/push/pull),确认后 Ctrl+C
Expected: `listening on 0.0.0.0:8091`,curl 往返正常

- [ ] **Step 5: 提交**

```bash
git add backend/run.sh .gitignore
git commit -m "feat(backend): add run script and ignore runtime db"
```

---

### Task 9: 前端合并纯函数 `mergeState`

**Files:**
- Create: `js/merge.js`
- Test: `js/merge.test.mjs`

**Interfaces:**
- Produces: `mergeState(local: object, remote: object) -> object` — 按 §9 规则合并两棵状态树,不改入参,返回新对象
- 规则:streak 取大;seenCardIds/favorites.cards/favorites.terms 并集;review 按 quizId 并集(cleared 取 OR);quizStats.attempts/correct 累加;difficulty.current 取高档(L1<L2<L3);user.tags 与 onboardedAt 取 remote,若 remote 未 onboarded 则取 local

- [ ] **Step 1: 写失败测试**

```javascript
// js/merge.test.mjs
import assert from 'node:assert';
import { mergeState } from './merge.js';

// streak 取较大
assert.equal(mergeState({progress:{streak:3}}, {progress:{streak:7}}).progress.streak, 7);

// seenCardIds 并集去重
assert.deepEqual(
  mergeState({progress:{seenCardIds:['c1','c2']}}, {progress:{seenCardIds:['c2','c3']}}).progress.seenCardIds.sort(),
  ['c1','c2','c3']);

// favorites 并集
assert.deepEqual(
  mergeState({favorites:{cards:['a'],terms:['t1']}}, {favorites:{cards:['b'],terms:['t1','t2']}}).favorites.cards.sort(),
  ['a','b']);

// quizStats 累加
{
  const m = mergeState({progress:{quizStats:{attempts:4,correct:3}}}, {progress:{quizStats:{attempts:10,correct:6}}});
  assert.equal(m.progress.quizStats.attempts, 14);
  assert.equal(m.progress.quizStats.correct, 9);
}

// difficulty 取高档
assert.equal(mergeState({difficulty:{current:'L1'}}, {difficulty:{current:'L3'}}).difficulty.current, 'L3');
assert.equal(mergeState({difficulty:{current:'L2'}}, {difficulty:{current:'L1'}}).difficulty.current, 'L2');

// review 并集 + cleared OR
{
  const m = mergeState(
    {review:[{quizId:'q1',cleared:false},{quizId:'q2',cleared:false}]},
    {review:[{quizId:'q1',cleared:true},{quizId:'q3',cleared:false}]});
  const q1 = m.review.find(r=>r.quizId==='q1');
  assert.equal(q1.cleared, true);              // OR
  assert.equal(m.review.length, 3);            // q1,q2,q3
}

// user.tags 取 remote(remote 已 onboarded)
{
  const m = mergeState(
    {user:{tags:{level:'L1'},onboardedAt:null}},
    {user:{tags:{level:'L3'},onboardedAt:'2026-01-01'}});
  assert.equal(m.user.tags.level, 'L3');
}
// remote 未 onboarded 则取 local
{
  const m = mergeState(
    {user:{tags:{level:'L2'},onboardedAt:'2026-02-02'}},
    {user:{tags:{level:'L1'},onboardedAt:null}});
  assert.equal(m.user.tags.level, 'L2');
}

// 不改入参
{
  const local = {progress:{streak:1}};
  mergeState(local, {progress:{streak:9}});
  assert.equal(local.progress.streak, 1);
}

console.log('mergeState: all assertions passed');
```

- [ ] **Step 2: 运行确认失败**

Run: `node js/merge.test.mjs`
Expected: FAIL(`Cannot find module './merge.js'` 或断言错误)

- [ ] **Step 3: 写实现**

```javascript
// js/merge.js
const LEVEL_RANK = { L1: 1, L2: 2, L3: 3 };
const uniq = (arr) => [...new Set(arr || [])];

export function mergeState(local, remote) {
  const L = local || {};
  const R = remote || {};
  const lp = L.progress || {}, rp = R.progress || {};
  const lqs = lp.quizStats || {}, rqs = rp.quizStats || {};
  const lf = L.favorites || {}, rf = R.favorites || {};

  // review 并集:按 quizId 合并,cleared 取 OR,其余字段以先出现者为准
  const reviewMap = new Map();
  for (const r of [...(L.review || []), ...(R.review || [])]) {
    if (!r || !r.quizId) continue;
    const prev = reviewMap.get(r.quizId);
    if (prev) prev.cleared = prev.cleared || !!r.cleared;
    else reviewMap.set(r.quizId, { ...r, cleared: !!r.cleared });
  }

  // 身份/标签:remote 已 onboarded 用 remote,否则用 local
  const remoteOnboarded = !!(R.user && R.user.onboardedAt);
  const userBlock = remoteOnboarded ? (R.user || {}) : (L.user || R.user || {});

  const merged = {
    ...L, ...R,
    user: { ...(L.user || {}), ...(R.user || {}), ...userBlock },
    progress: {
      ...lp, ...rp,
      streak: Math.max(lp.streak || 0, rp.streak || 0),
      seenCardIds: uniq([...(lp.seenCardIds || []), ...(rp.seenCardIds || [])]),
      quizStats: {
        attempts: (lqs.attempts || 0) + (rqs.attempts || 0),
        correct: (lqs.correct || 0) + (rqs.correct || 0),
      },
    },
    favorites: {
      cards: uniq([...(lf.cards || []), ...(rf.cards || [])]),
      terms: uniq([...(lf.terms || []), ...(rf.terms || [])]),
    },
    review: [...reviewMap.values()],
    difficulty: {
      ...(L.difficulty || {}), ...(R.difficulty || {}),
      current: (LEVEL_RANK[(R.difficulty || {}).current] || 0) >= (LEVEL_RANK[(L.difficulty || {}).current] || 0)
        ? (R.difficulty || {}).current || (L.difficulty || {}).current
        : (L.difficulty || {}).current,
    },
  };
  return merged;
}
```

- [ ] **Step 4: 运行确认通过**

Run: `node js/merge.test.mjs`
Expected: PASS(`mergeState: all assertions passed`)

- [ ] **Step 5: 提交**

```bash
git add js/merge.js js/merge.test.mjs
git commit -m "feat(frontend): add mergeState pure function with node assertions"
```

---

### Task 10: 前端认证模块 `auth.js`

**Files:**
- Create: `js/auth.js`

**Interfaces:**
- Consumes: 后端 `/api/register` `/api/login` `/api/logout` `/api/me`(Task 5-6)
- Produces(全部 async,除标注):
  - `API_BASE: string`(常量,`http://10.159.3.80:8091`,本地开发可改)
  - `getToken() -> string|null`(同步,读 localStorage `finrookie:token`)
  - `getUsername() -> string|null`(同步)
  - `isLoggedIn() -> boolean`(同步)
  - `register(username, password) -> {ok:true} | {error}`
  - `login(username, password) -> {ok:true, username} | {error}`(成功时存 token+username 到 localStorage)
  - `logout() -> void`(调后端作废 + 清本地 token/username)

- [ ] **Step 1: 写实现**

```javascript
// js/auth.js
// 后端地址:局域网服务器。本地联调时可临时改为 http://127.0.0.1:8091
export const API_BASE = 'http://10.159.3.80:8091';

const TOKEN_KEY = 'finrookie:token';
const NAME_KEY = 'finrookie:username';

export function getToken() { return localStorage.getItem(TOKEN_KEY); }
export function getUsername() { return localStorage.getItem(NAME_KEY); }
export function isLoggedIn() { return !!getToken(); }

async function postJSON(path, body, withAuth = false) {
  const headers = { 'Content-Type': 'application/json' };
  if (withAuth) {
    const t = getToken();
    if (t) headers['Authorization'] = `Bearer ${t}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST', headers, body: JSON.stringify(body || {}),
  });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  return { status: res.status, data };
}

export async function register(username, password) {
  const { status, data } = await postJSON('/api/register', { username, password });
  if (status === 201) return { ok: true };
  return { error: data.error || 'register_failed' };
}

export async function login(username, password) {
  const { status, data } = await postJSON('/api/login', { username, password });
  if (status === 200 && data.token) {
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(NAME_KEY, data.username || username);
    return { ok: true, username: data.username || username };
  }
  return { error: data.error || 'login_failed' };
}

export async function logout() {
  try { await postJSON('/api/logout', {}, true); } catch (_) {}
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(NAME_KEY);
}
```

- [ ] **Step 2: 语法自检**

Run: `node --input-type=module -e "await import('./js/auth.js'); console.log('auth.js loads ok')"`
Expected: 打印 `auth.js loads ok`(localStorage 在 node 下未定义但仅在函数体内引用,import 阶段不报错)

> 若 import 阶段因顶层无 localStorage 访问而通过即可;实际 DOM 行为在真机验证。

- [ ] **Step 3: 提交**

```bash
git add js/auth.js
git commit -m "feat(frontend): add auth module for register/login/logout"
```

---

### Task 11: 前端同步模块 `sync.js`

**Files:**
- Create: `js/sync.js`

**Interfaces:**
- Consumes: `auth.API_BASE`, `auth.getToken`, `auth.logout`(Task 10);`mergeState`(Task 9);`store`(现有 `js/store.js`,`store.getState()` / `store.update(mutator)`)
- Produces(async):
  - `pullAndMerge() -> {ok, merged?} | {error}` — 拉云端;有数据则 `mergeState(本地, 云端)` 写回本地并回推;无数据则把本地当前状态 push 上去;401 时调 `auth.logout()`
  - `pushNow() -> {ok} | {error}` — 立刻把本地整棵状态 push 到云端(401 → logout)
  - `schedulePush() -> void`(同步)— 防抖 2s 后调 `pushNow`;未登录则不做

- [ ] **Step 1: 写实现**

```javascript
// js/sync.js
import { API_BASE, getToken, logout } from './auth.js';
import { mergeState } from './merge.js';
import { store } from './store.js';

async function authedFetch(path, options = {}) {
  const token = getToken();
  if (!token) return { status: 401, data: {} };
  const headers = { ...(options.headers || {}), 'Authorization': `Bearer ${token}` };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  return { status: res.status, data };
}

export async function pushNow() {
  if (!getToken()) return { error: 'not_logged_in' };
  const state = store.getState();
  const { status } = await authedFetch('/api/sync/push', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: state }),
  });
  if (status === 401) { await logout(); return { error: 'unauthorized' }; }
  if (status === 200) return { ok: true };
  return { error: 'push_failed' };
}

export async function pullAndMerge() {
  if (!getToken()) return { error: 'not_logged_in' };
  const { status, data } = await authedFetch('/api/sync/pull', { method: 'GET' });
  if (status === 401) { await logout(); return { error: 'unauthorized' }; }
  if (status !== 200) return { error: 'pull_failed' };
  if (data.data) {
    const local = store.getState();
    const merged = mergeState(local, data.data);
    store.update((root) => { Object.assign(root, merged); });
    await pushNow(); // 把合并结果回推,使云端与本地一致
    return { ok: true, merged };
  }
  // 云端还没有该用户数据:把本地现状推上去
  await pushNow();
  return { ok: true };
}

let _pushTimer = null;
export function schedulePush() {
  if (!getToken()) return;
  clearTimeout(_pushTimer);
  _pushTimer = setTimeout(() => { pushNow().catch(() => {}); }, 2000);
}
```

- [ ] **Step 2: 语法自检**

Run: `node --input-type=module -e "import('./js/sync.js').then(()=>console.log('sync.js loads ok')).catch(e=>{console.error(e);process.exit(1)})"`
Expected: 打印 `sync.js loads ok`(store.js 顶层不触碰 localStorage 才通过;若报错,确认 store.js import 阶段无副作用)

> 若因 store.js 在 import 阶段访问 localStorage 而失败,属预期的环境限制,可跳过此自检,改由真机验证并在提交说明标注。

- [ ] **Step 3: 提交**

```bash
git add js/sync.js
git commit -m "feat(frontend): add sync module (pull+merge / debounced push)"
```

---

### Task 12: store 写钩子 + app.js 登录态与拉取

**Files:**
- Modify: `js/store.js`(`set` / `update` / `track` 写成功后触发 `schedulePush`)
- Modify: `js/app.js`(init 若已登录则 `pullAndMerge`;"我的"页新增登录态状态与 `doLogin/doRegister/doLogout`)

**Interfaces:**
- Consumes: `sync.schedulePush`, `sync.pullAndMerge`(Task 11);`auth.*`(Task 10)
- Produces(app.js Alpine 组件新增):
  - 状态 `authUser: string|null`、`authOpen: bool`、`authMode: 'login'|'register'`、`authForm:{username,password}`、`authError: string`
  - 方法 `doLogin()`、`doRegister()`、`doLogout()`、`get isAuthed()`

> 注意循环依赖:store.js 需调用 sync.schedulePush,而 sync.js import 了 store。用**动态 import**在写操作时懒加载 sync,避免模块循环。

- [ ] **Step 1: 改 store.js —— 写成功后触发同步(动态 import 防循环)**

在 `js/store.js` 顶部加一个懒加载触发器,并在 `set`/`update`/`track` 写成功后调用:

```javascript
// 在 store.js 顶部(STORAGE_KEY 定义之后)加入:
let _syncHook = null;
function triggerSync() {
  // 懒加载 sync,避免与 store 的模块循环;未登录时 schedulePush 内部自会跳过
  if (_syncHook) { _syncHook(); return; }
  import('./sync.js').then((m) => { _syncHook = m.schedulePush; _syncHook(); }).catch(() => {});
}
```

然后在 `set` 的 `return writeRoot(root);` 前、`update` 的 `return writeRoot(root);` 前各加一行 `triggerSync();`(track 可不加,避免埋点频繁触发;仅在真正学习数据变更的 set/update 触发)。修改后:

```javascript
  set(path, value) {
    const root = readRoot();
    setByPath(root, path, value);
    const ok = writeRoot(root);
    if (ok) triggerSync();
    return ok;
  },
  update(mutator) {
    const root = readRoot();
    mutator(root);
    const ok = writeRoot(root);
    if (ok) triggerSync();
    return ok;
  },
```

- [ ] **Step 2: 改 app.js —— import 与登录态状态**

app.js 顶部 import 段之后加入:

```javascript
import * as authApi from './auth.js';
import { pullAndMerge } from './sync.js';
```

在 Alpine 组件返回对象里加入状态与方法(放在 `resetAll` 之前):

```javascript
    // ---- 账号/登录(阶段二)----
    authUser: null,           // 已登录用户名,未登录为 null
    authOpen: false,          // 登录/注册弹层开关
    authMode: 'login',        // 'login' | 'register'
    authForm: { username: '', password: '' },
    authError: '',
    authBusy: false,

    get isAuthed() { return !!this.authUser; },
    openAuth(mode) { this.authMode = mode || 'login'; this.authError = ''; this.authForm = { username: '', password: '' }; this.authOpen = true; },
    closeAuth() { this.authOpen = false; this.authError = ''; },
    switchAuthMode() { this.authMode = this.authMode === 'login' ? 'register' : 'login'; this.authError = ''; },

    async doLogin() {
      if (this.authBusy) return;
      this.authBusy = true; this.authError = '';
      const r = await authApi.login(this.authForm.username.trim(), this.authForm.password);
      this.authBusy = false;
      if (r.error) { this.authError = r.error === 'bad_credentials' ? '用户名或密码错误' : '登录失败,请稍后再试'; return; }
      this.authUser = r.username;
      this.authOpen = false;
      await pullAndMerge();      // 合并云端数据到本地
      this.tags = store.get('user.tags', DEFAULT_TAGS);
      this.streak = store.get('progress.streak', 0);
      if (this.route === 'me') this.refreshMe();
    },
    async doRegister() {
      if (this.authBusy) return;
      this.authBusy = true; this.authError = '';
      const u = this.authForm.username.trim();
      const r = await authApi.register(u, this.authForm.password);
      if (r.error) {
        this.authBusy = false;
        this.authError = r.error === 'username_taken' ? '该用户名已被使用' : '注册失败(用户名和密码不能为空)';
        return;
      }
      // 注册成功直接登录
      const lr = await authApi.login(u, this.authForm.password);
      this.authBusy = false;
      if (lr.error) { this.authMode = 'login'; this.authError = '注册成功,请登录'; return; }
      this.authUser = lr.username;
      this.authOpen = false;
      await pullAndMerge();
      if (this.route === 'me') this.refreshMe();
    },
    async doLogout() {
      await authApi.logout();
      this.authUser = null;
    },
```

在 `init()` 里,`this.streak = store.get(...)` 之后、路由决策之前加入登录态恢复:

```javascript
      // 恢复登录态:有 token 则显示为已登录,并拉取合并云端数据
      this.authUser = authApi.getUsername();
      if (authApi.isLoggedIn()) {
        pullAndMerge().then(() => {
          this.tags = store.get('user.tags', DEFAULT_TAGS);
          this.streak = store.get('progress.streak', 0);
          if (this.route === 'me') this.refreshMe();
        }).catch(() => {});
      }
```

- [ ] **Step 3: 语法自检**

Run: `node --check js/store.js && node --input-type=module -e "console.log('app.js parse check via bundler skipped; use browser')"`
Expected: `node --check js/store.js` 无输出即通过;app.js 依赖 Alpine 运行时,语法由浏览器验证

> app.js 是 Alpine 组件,含浏览器 API,不能在 node 完整运行;仅做 `node --check js/store.js` 静态检查 + 真机验证。

- [ ] **Step 4: 提交**

```bash
git add js/store.js js/app.js
git commit -m "feat(frontend): wire sync hook into store and login state into app"
```

---

### Task 13: "我的"页登录 UI + SW 版本号

**Files:**
- Modify: `index.html`("我的"页加登录区 + 登录/注册弹层)
- Modify: `sw.js`(CACHE_VERSION 递增,并把新 JS 纳入壳缓存)

**Interfaces:**
- Consumes: app.js 的 `authUser/isAuthed/openAuth/closeAuth/doLogin/doRegister/doLogout/authMode/authForm/authError/switchAuthMode`(Task 12)

- [ ] **Step 1: 在"我的"页顶部加登录状态区**

在 `index.html` 的 `#me`(“我的”)section 顶部,收藏/复习区之前,加入:

```html
<!-- 账号区(阶段二)-->
<div class="mb-4 rounded-3xl bg-paper-card p-4 shadow-soft">
  <template x-if="isAuthed">
    <div class="flex items-center justify-between">
      <div>
        <div class="text-sm text-ink-faint">已登录</div>
        <div class="text-lg font-bold text-ink num" x-text="authUser"></div>
        <div class="text-xs text-ink-faint mt-0.5">学习数据已同步到云端</div>
      </div>
      <button @click="doLogout()" class="rounded-full border border-paper-line px-4 py-2 text-sm text-ink-soft">退出登录</button>
    </div>
  </template>
  <template x-if="!isAuthed">
    <div class="flex items-center justify-between">
      <div>
        <div class="text-lg font-bold text-ink">登录后跨设备同步</div>
        <div class="text-xs text-ink-faint mt-0.5">不登录也能正常使用,数据存在本机</div>
      </div>
      <div class="flex gap-2">
        <button @click="openAuth('login')" class="rounded-full bg-brand px-4 py-2 text-sm font-bold text-white">登录</button>
        <button @click="openAuth('register')" class="rounded-full border border-brand px-4 py-2 text-sm font-bold text-brand">注册</button>
      </div>
    </div>
  </template>
</div>
```

- [ ] **Step 2: 加登录/注册弹层**

在 `index.html` 底部(与其他浮层如术语弹层同级)加入:

```html
<!-- 登录/注册弹层 -->
<div x-show="authOpen" x-cloak class="fixed inset-0 z-50 flex items-end lg:items-center justify-center bg-ink/40" @click.self="closeAuth()">
  <div class="w-full lg:max-w-sm rounded-t-3xl lg:rounded-3xl bg-paper-card p-6 pb-safe-sheet shadow-soft">
    <div class="mb-4 text-center text-lg font-bold text-ink" x-text="authMode === 'login' ? '登录' : '注册'"></div>
    <input x-model="authForm.username" type="text" placeholder="用户名"
           class="mb-3 w-full rounded-2xl border border-paper-line bg-paper px-4 py-3 text-ink" autocomplete="off">
    <input x-model="authForm.password" type="password" placeholder="密码"
           class="mb-2 w-full rounded-2xl border border-paper-line bg-paper px-4 py-3 text-ink"
           @keydown.enter="authMode === 'login' ? doLogin() : doRegister()">
    <div x-show="authError" x-text="authError" class="mb-2 text-sm text-clay"></div>
    <button @click="authMode === 'login' ? doLogin() : doRegister()" :disabled="authBusy"
            class="mb-3 w-full rounded-2xl bg-brand py-3 font-bold text-white disabled:opacity-60"
            x-text="authBusy ? '请稍候…' : (authMode === 'login' ? '登录' : '注册并登录')"></button>
    <div class="text-center text-sm text-ink-faint">
      <span x-text="authMode === 'login' ? '还没有账号?' : '已有账号?'"></span>
      <button @click="switchAuthMode()" class="text-brand font-bold" x-text="authMode === 'login' ? '去注册' : '去登录'"></button>
    </div>
    <button @click="closeAuth()" class="mt-2 w-full py-2 text-sm text-ink-faint">取消</button>
  </div>
</div>
```

- [ ] **Step 3: 递增 SW 版本并纳入新 JS**

在 `sw.js` 把 `CACHE_VERSION` 从当前值(`finrookie-v8`)改为 `finrookie-v9`;在 `APP_SHELL` 数组补入新脚本:

```javascript
const CACHE_VERSION = 'finrookie-v9';
// APP_SHELL 中补入:
  './js/auth.js',
  './js/sync.js',
  './js/merge.js',
```

- [ ] **Step 4: 真机验证(用户执行)**

在服务器或本机起前端与后端,浏览器验证以下路径(记录到验证清单):
1. 未登录:所有原功能正常(出卡/答题/收藏/打卡),无报错
2. 注册新账号 → 自动登录 → "我的"页显示用户名
3. 答题/收藏 → 2s 后开发者工具 Network 看到 `/api/sync/push` 200
4. 换浏览器/清 localStorage → 登录同账号 → 数据回来了(streak/收藏在)
5. 双端数据合并:A 设备攒数据不登录,登录后与云端合并,无丢失
6. 后端关闭时登录/同步失败 → 前端仍可用本地,不白屏
7. 退出登录 → 回到未登录态,本地数据仍在

Expected: 7 项全绿;隔离已由后端 test_api 保证

- [ ] **Step 5: 提交**

```bash
git add index.html sw.js
git commit -m "feat(frontend): add login UI in profile page and bump SW cache"
```

---

## 部署到服务器(全部任务完成后)

1. 提交推送后,在服务器 `~/finrookie-app/` `git pull`(或 scp `backend/` 与改动文件)。
2. 起后端:`cd ~/finrookie-app/backend && setsid python3 server.py >~/fr-backend.log 2>&1 &`,确认 `listening on 0.0.0.0:8091`。
3. `@reboot` crontab 补一条后端自启(与前端 8090 自启并列)。
4. 确认防火墙放行 8091(局域网内)。
5. 前端 `js/auth.js` 的 `API_BASE` 确认为 `http://10.159.3.80:8091`。
6. 按 Task 13 Step 4 的 7 项在真机走一遍。

---

## 自审记录(spec 覆盖核对)

- §2 范围(用户系统+数据上云,不含 AI/后台推送)→ Task 1-13 覆盖,AI/推送明确排除 ✅
- §3 隐私铁律①user_id 隔离 → Task 7 隔离测试;②无越权接口 → 接口清单仅 6 个;③密码哈希 → Task 2;④后台只聚合 → 本次不做后台,数据结构预留;⑤账号与真人脱钩 → 用户名+密码,不采集真名 ✅
- §4 架构(8091 端口/CORS/纯标准库)→ Task 4 ✅
- §5 三张表 + JSON 整存 → Task 1 + Task 7 ✅
- §6 六接口 → Task 5(register)/6(login,logout,me)/7(pull,push)✅
- §7 token 鉴权 + 不信任前端 user_id → Task 4 `_authed_uid` + 各接口 ✅
- §8 前端改造集中 store 层 → Task 10-12 ✅
- §9 智能合并每字段规则 → Task 9 mergeState + 断言 ✅
- §10 错误处理(断网/401/重复/密码错)→ Task 5-6 状态码 + Task 10-11 前端回退 ✅
- §11 测试(纯函数 node 断言 + 接口 unittest 隔离)→ Task 9 + Task 1-7 ✅
- §12 已知限制(HTTP 非 HTTPS)→ 部署说明标注,后端已加 CORS,不改变限制性质 ✅
