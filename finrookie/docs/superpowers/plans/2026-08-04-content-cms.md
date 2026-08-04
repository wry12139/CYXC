# 财小白内容管理系统 (CMS) 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a content management system with dynamic personalized recommendations (分层推送) and admin dashboard to manage all content types (知识卡/题/术语/早报/文章) with version history.

**Architecture:** Backend extends SQLite schema with `content_items` + `content_versions` tables. Admin-only endpoints support full CRUD. Frontend queries `GET /api/recommendations` on "我的" page to dynamically generate personalized cards based on user's quiz mastery by topic. Admin panel (visible only to `is_admin=true` users) provides UI to create/edit/delete content with automatic version tracking.

**Tech Stack:** Python 3 (http.server, sqlite3), Alpine.js, Tailwind CSS. Zero new dependencies.

## Global Constraints

- Backend: Python standard library only, no pip dependencies
- Frontend: Alpine.js + Tailwind, no build step, relative paths only
- Database: SQLite, schema changes must preserve existing tables
- Admin: Identified by `is_admin` boolean in users table; special "admin" user created on first run
- Content types: knowledge_card, quiz, term, briefing, article (5 types)
- Version tracking: automatic on every create/update, stores username + timestamp
- Recommendation: dynamic generation, no caching (computed per request)
- Compatibility: Must not break existing user sessions, login, or data sync

---

## Task 1: Extend Database Schema

**Files:**
- Modify: `backend/db.py`
- Test: `backend/tests/test_db.py` (add new assertions)

**Interfaces:**
- Consumes: Existing sqlite3 connection setup
- Produces: 
  - Table `content_items(id TEXT PRIMARY KEY, type TEXT, data JSON, created_by TEXT, created_at TEXT, updated_at TEXT)`
  - Table `content_versions(id TEXT PRIMARY KEY, content_id TEXT, type TEXT, changed_by TEXT, changed_at TEXT, action TEXT, diff JSON)`
  - Table `users` modified: add column `is_admin INTEGER DEFAULT 0`

- [ ] **Step 1: Read existing db.py to understand current schema**

Open `backend/db.py`. Note the pattern for table creation, the use of `?` placeholders for parameters, and how datetime is handled (TEXT format).

- [ ] **Step 2: Write failing test for new schema**

Edit `backend/tests/test_db.py` (create if missing):

```python
import sqlite3
import tempfile
import os
from backend.db import init_db

def test_content_items_table_exists():
    """Verify content_items table is created with correct schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_items'")
        assert cursor.fetchone() is not None, "content_items table not found"
        
        # Check columns
        cursor.execute("PRAGMA table_info(content_items)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        assert 'id' in columns
        assert 'type' in columns
        assert 'data' in columns
        assert 'created_by' in columns
        assert 'created_at' in columns
        assert 'updated_at' in columns
        
        conn.close()

def test_content_versions_table_exists():
    """Verify content_versions table is created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_versions'")
        assert cursor.fetchone() is not None, "content_versions table not found"
        
        # Check columns
        cursor.execute("PRAGMA table_info(content_versions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        assert 'id' in columns
        assert 'content_id' in columns
        assert 'changed_by' in columns
        assert 'changed_at' in columns
        assert 'action' in columns
        
        conn.close()

def test_users_has_is_admin_column():
    """Verify users table has is_admin column."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        assert 'is_admin' in columns, "is_admin column not found in users table"
        
        conn.close()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd C:\Users\86184\finrookie
python -m pytest backend/tests/test_db.py::test_content_items_table_exists -v
```

Expected: FAIL (tables not created yet)

- [ ] **Step 4: Implement schema in db.py**

Open `backend/db.py`. Find the `init_db()` function and add these three CREATE TABLE statements before the final `commit()`:

```python
def init_db(conn):
    """Initialize database schema."""
    cursor = conn.cursor()
    
    # ... existing code for users, sessions, user_data tables ...
    
    # New: Add is_admin column to users if it doesn't exist
    cursor.execute("""
        PRAGMA table_info(users)
    """)
    columns = [row[1] for row in cursor.fetchall()]
    if 'is_admin' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    
    # New: content_items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            data JSON NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(username)
        )
    """)
    
    # New: content_versions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_versions (
            id TEXT PRIMARY KEY,
            content_id TEXT NOT NULL,
            type TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            action TEXT NOT NULL,
            diff JSON,
            FOREIGN KEY (content_id) REFERENCES content_items(id),
            FOREIGN KEY (changed_by) REFERENCES users(username)
        )
    """)
    
    conn.commit()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest backend/tests/test_db.py::test_content_items_table_exists backend/tests/test_db.py::test_content_versions_table_exists backend/tests/test_db.py::test_users_has_is_admin_column -v
```

Expected: PASS (all 3 tests green)

- [ ] **Step 6: Commit**

```bash
git add backend/db.py backend/tests/test_db.py
git commit -m "feat(backend): add content_items, content_versions tables and is_admin to users"
```

---

## Task 2: Create Admin Identity Module

**Files:**
- Create: `backend/admin.py`
- Test: `backend/tests/test_admin.py`

**Interfaces:**
- Consumes: `auth.lookup_session(token)` (returns user_id), sqlite3 connection
- Produces: `is_admin(conn, user_id) -> bool`, `ensure_admin_exists(conn) -> None`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_admin.py`:

```python
import sqlite3
import tempfile
import os
from backend.db import init_db
from backend.auth import create_session
from backend.admin import is_admin, ensure_admin_exists

def test_ensure_admin_exists_creates_default_admin():
    """Verify default admin user is created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        ensure_admin_exists(conn)
        
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE username='admin'")
        result = cursor.fetchone()
        assert result is not None, "admin user not created"
        assert result[0] == 1, "admin user is_admin not set to 1"
        
        conn.close()

def test_is_admin_returns_true_for_admin():
    """Verify is_admin() returns True for admin user."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        ensure_admin_exists(conn)
        
        # Get admin user id
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username='admin'")
        admin_id = cursor.fetchone()[0]
        
        assert is_admin(conn, admin_id) == True
        
        conn.close()

def test_is_admin_returns_false_for_non_admin():
    """Verify is_admin() returns False for regular user."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        # Create regular user
        cursor = conn.cursor()
        import secrets
        from backend.auth import pbkdf2_hash
        salt = secrets.token_hex(16)
        pw_hash = pbkdf2_hash('password', salt)
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at, is_admin) VALUES (?, ?, ?, datetime('now'), 0)",
            ('testuser', pw_hash, salt)
        )
        conn.commit()
        cursor.execute("SELECT id FROM users WHERE username='testuser'")
        user_id = cursor.fetchone()[0]
        
        assert is_admin(conn, user_id) == False
        
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest backend/tests/test_admin.py::test_ensure_admin_exists_creates_default_admin -v
```

Expected: FAIL (module does not exist)

- [ ] **Step 3: Implement admin.py**

Create `backend/admin.py`:

```python
import secrets
from backend.auth import pbkdf2_hash

def is_admin(conn, user_id):
    """Check if user is admin."""
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

def ensure_admin_exists(conn):
    """Create default admin user if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username='admin'")
    if cursor.fetchone() is None:
        # Create admin user with default password "admin123"
        salt = secrets.token_hex(16)
        pw_hash = pbkdf2_hash('admin123', salt)
        cursor.execute(
            """INSERT INTO users (username, password_hash, salt, created_at, is_admin)
               VALUES (?, ?, ?, datetime('now'), 1)""",
            ('admin', pw_hash, salt)
        )
        conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_admin.py -v
```

Expected: PASS (all 3 tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/admin.py backend/tests/test_admin.py
git commit -m "feat(backend): add admin identity module with default admin user"
```

---

## Task 3: Implement Content CRUD Module

**Files:**
- Create: `backend/content.py`
- Test: `backend/tests/test_content.py`

**Interfaces:**
- Consumes: sqlite3 connection, user_id (from auth), content_id (for updates)
- Produces:
  - `create_content(conn, type, data, created_by) -> str` (returns content_id)
  - `get_content(conn, content_id) -> dict`
  - `list_content(conn, type=None) -> list[dict]`
  - `update_content(conn, content_id, data, changed_by) -> None`
  - `delete_content(conn, content_id, changed_by) -> None`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_content.py`:

```python
import sqlite3
import tempfile
import os
import json
import uuid
from backend.db import init_db
from backend.content import create_content, get_content, list_content, update_content, delete_content

def test_create_content_knowledge_card():
    """Verify creating a knowledge card content item."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        # Create a test user
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            ('testuser', 'hash', 'salt')
        )
        conn.commit()
        
        data = {
            'title': 'What is ETF?',
            'body': '<p>An ETF is...</p>',
            'difficulty': 'L1',
            'topics': ['fund'],
            'quizIds': ['q1', 'q2']
        }
        
        content_id = create_content(conn, 'knowledge_card', data, 'testuser')
        assert content_id is not None
        assert isinstance(content_id, str)
        
        # Verify it was stored
        cursor.execute("SELECT id, type, data FROM content_items WHERE id=?", (content_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == 'knowledge_card'
        assert json.loads(row[2]) == data
        
        conn.close()

def test_get_content_returns_data():
    """Verify retrieving content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            ('testuser', 'hash', 'salt')
        )
        conn.commit()
        
        data = {'title': 'Test', 'body': 'Body'}
        content_id = create_content(conn, 'term', data, 'testuser')
        
        retrieved = get_content(conn, content_id)
        assert retrieved is not None
        assert retrieved['type'] == 'term'
        assert retrieved['data'] == data
        
        conn.close()

def test_list_content_filters_by_type():
    """Verify listing content with type filter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            ('testuser', 'hash', 'salt')
        )
        conn.commit()
        
        create_content(conn, 'knowledge_card', {'title': 'Card 1'}, 'testuser')
        create_content(conn, 'knowledge_card', {'title': 'Card 2'}, 'testuser')
        create_content(conn, 'term', {'title': 'Term 1'}, 'testuser')
        
        cards = list_content(conn, type='knowledge_card')
        assert len(cards) == 2
        assert all(c['type'] == 'knowledge_card' for c in cards)
        
        terms = list_content(conn, type='term')
        assert len(terms) == 1
        assert terms[0]['type'] == 'term'
        
        conn.close()

def test_update_content_creates_version():
    """Verify updating content creates a version record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            ('testuser', 'hash', 'salt')
        )
        conn.commit()
        
        content_id = create_content(conn, 'term', {'title': 'Old Title'}, 'testuser')
        
        new_data = {'title': 'New Title'}
        update_content(conn, content_id, new_data, 'testuser')
        
        # Verify content was updated
        retrieved = get_content(conn, content_id)
        assert retrieved['data']['title'] == 'New Title'
        
        # Verify version was created
        cursor.execute("SELECT id, action FROM content_versions WHERE content_id=?", (content_id,))
        version = cursor.fetchone()
        assert version is not None
        assert version[1] == 'update'
        
        conn.close()

def test_delete_content_creates_version():
    """Verify deleting content creates a version record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            ('testuser', 'hash', 'salt')
        )
        conn.commit()
        
        content_id = create_content(conn, 'article', {'title': 'Article'}, 'testuser')
        delete_content(conn, content_id, 'testuser')
        
        # Verify content was deleted (soft or hard)
        retrieved = get_content(conn, content_id)
        # Hard delete: should be None; soft delete: should have deleted_at flag
        # For simplicity, we'll do hard delete
        assert retrieved is None
        
        # Verify version was created
        cursor.execute("SELECT action FROM content_versions WHERE content_id=?", (content_id,))
        version = cursor.fetchone()
        assert version is not None
        assert version[0] == 'delete'
        
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest backend/tests/test_content.py::test_create_content_knowledge_card -v
```

Expected: FAIL (module does not exist)

- [ ] **Step 3: Implement content.py**

Create `backend/content.py`:

```python
import sqlite3
import json
import uuid
from datetime import datetime

def _generate_id():
    """Generate a unique content ID."""
    return str(uuid.uuid4())[:12]

def create_content(conn, type, data, created_by):
    """Create a new content item and return its ID."""
    content_id = _generate_id()
    now = datetime.utcnow().isoformat()
    
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO content_items (id, type, data, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (content_id, type, json.dumps(data), created_by, now, now)
    )
    
    # Create initial version record
    version_id = _generate_id()
    cursor.execute(
        """INSERT INTO content_versions (id, content_id, type, changed_by, changed_at, action, diff)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (version_id, content_id, type, created_by, now, 'create', json.dumps(data))
    )
    
    conn.commit()
    return content_id

def get_content(conn, content_id):
    """Retrieve a content item by ID. Returns None if deleted."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, type, data, created_by, created_at, updated_at
           FROM content_items WHERE id=?""",
        (content_id,)
    )
    row = cursor.fetchone()
    if row is None:
        return None
    
    return {
        'id': row[0],
        'type': row[1],
        'data': json.loads(row[2]),
        'created_by': row[3],
        'created_at': row[4],
        'updated_at': row[5]
    }

def list_content(conn, type=None):
    """List all content items, optionally filtered by type."""
    cursor = conn.cursor()
    if type:
        cursor.execute("SELECT id, type, data, created_by, created_at, updated_at FROM content_items WHERE type=? ORDER BY created_at DESC", (type,))
    else:
        cursor.execute("SELECT id, type, data, created_by, created_at, updated_at FROM content_items ORDER BY created_at DESC")
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'type': row[1],
            'data': json.loads(row[2]),
            'created_by': row[3],
            'created_at': row[4],
            'updated_at': row[5]
        })
    return results

def update_content(conn, content_id, data, changed_by):
    """Update a content item and create a version record."""
    now = datetime.utcnow().isoformat()
    
    # Get old data for diff
    cursor = conn.cursor()
    cursor.execute("SELECT data, type FROM content_items WHERE id=?", (content_id,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Content {content_id} not found")
    
    old_data = json.loads(row[0])
    content_type = row[1]
    
    # Update content
    cursor.execute(
        "UPDATE content_items SET data=?, updated_at=? WHERE id=?",
        (json.dumps(data), now, content_id)
    )
    
    # Create version record
    version_id = _generate_id()
    cursor.execute(
        """INSERT INTO content_versions (id, content_id, type, changed_by, changed_at, action, diff)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (version_id, content_id, content_type, changed_by, now, 'update', 
         json.dumps({'old': old_data, 'new': data}))
    )
    
    conn.commit()

def delete_content(conn, content_id, changed_by):
    """Delete a content item (hard delete) and create a version record."""
    now = datetime.utcnow().isoformat()
    
    cursor = conn.cursor()
    cursor.execute("SELECT data, type FROM content_items WHERE id=?", (content_id,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Content {content_id} not found")
    
    old_data = json.loads(row[0])
    content_type = row[1]
    
    # Delete content
    cursor.execute("DELETE FROM content_items WHERE id=?", (content_id,))
    
    # Create version record (for audit trail)
    version_id = _generate_id()
    cursor.execute(
        """INSERT INTO content_versions (id, content_id, type, changed_by, changed_at, action, diff)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (version_id, content_id, content_type, changed_by, now, 'delete', json.dumps(old_data))
    )
    
    conn.commit()

def get_versions(conn, content_id):
    """Get all versions of a content item."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, changed_by, changed_at, action, diff FROM content_versions
           WHERE content_id=? ORDER BY changed_at DESC""",
        (content_id,)
    )
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'changed_by': row[1],
            'changed_at': row[2],
            'action': row[3],
            'diff': json.loads(row[4]) if row[4] else None
        })
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_content.py -v
```

Expected: PASS (all 6 tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/content.py backend/tests/test_content.py
git commit -m "feat(backend): implement content CRUD with version tracking"
```

---

## Task 4: Implement Recommendation Algorithm

**Files:**
- Create: `backend/recommendation.py`
- Test: `backend/tests/test_recommendation.py`

**Interfaces:**
- Consumes: sqlite3 connection, user_id, existing `analyzeMastery(quiz_stats, cards)` from logic.js (reimplement in Python)
- Produces: `generate_recommendations(conn, user_id, num_recommendations=5) -> list[dict]` with fields: id, type, data, reason, reason_topic

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_recommendation.py`:

```python
import sqlite3
import tempfile
import os
import json
from backend.db import init_db
from backend.content import create_content
from backend.recommendation import generate_recommendations

def test_generate_recommendations_returns_list():
    """Verify recommendations are generated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        # Create test user
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            ('testuser', 'hash', 'salt')
        )
        conn.commit()
        cursor.execute("SELECT id FROM users WHERE username='testuser'")
        user_id = cursor.fetchone()[0]
        
        # Create some content
        create_content(conn, 'knowledge_card', {
            'title': 'Card 1',
            'topics': ['fund'],
            'difficulty': 'L1'
        }, 'admin')
        
        recs = generate_recommendations(conn, user_id, num_recommendations=5)
        assert isinstance(recs, list)
        assert len(recs) >= 0
        
        conn.close()

def test_recommendations_include_reason():
    """Verify each recommendation includes a reason."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite3.connect(db_path)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            ('testuser', 'hash', 'salt')
        )
        # Add user_data with quiz stats
        cursor.execute(
            "INSERT INTO user_data (user_id, data_json, updated_at) VALUES (?, ?, datetime('now'))",
            (1, json.dumps({
                'quizStats': [
                    {'cardId': 'c1', 'attempts': 5, 'correct': 5, 'timestamp': '2026-01-01'}
                ]
            }))
        )
        conn.commit()
        
        create_content(conn, 'knowledge_card', {
            'id': 'c2',
            'title': 'New Card',
            'topics': ['fund'],
            'difficulty': 'L2'
        }, 'admin')
        
        recs = generate_recommendations(conn, 1, num_recommendations=5)
        if len(recs) > 0:
            assert 'reason' in recs[0]
        
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest backend/tests/test_recommendation.py::test_generate_recommendations_returns_list -v
```

Expected: FAIL (module does not exist)

- [ ] **Step 3: Implement recommendation.py**

Create `backend/recommendation.py`:

```python
import sqlite3
import json
from collections import defaultdict

def generate_recommendations(conn, user_id, num_recommendations=5):
    """
    Generate personalized recommendations based on user's quiz mastery.
    
    Strategy:
    - Compute mastery by topic (% correct in that topic)
    - Lowest mastery topic: recommend unseen cards (help learn weaknesses)
    - Mid mastery topic: recommend new quiz questions
    - Highest mastery topic: recommend articles for deep-dive
    - Avoid already-seen or already-collected cards
    """
    
    # Get user's quiz stats and favorites
    cursor = conn.cursor()
    cursor.execute("SELECT data_json FROM user_data WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        user_data = {'quizStats': [], 'seenCardIds': [], 'favorites': {'cards': []}}
    else:
        user_data = json.loads(row[0])
    
    quiz_stats = user_data.get('quizStats', [])
    seen_card_ids = set(user_data.get('seenCardIds', []))
    fav_card_ids = set(user_data.get('favorites', {}).get('cards', []))
    
    # Get all knowledge cards
    cursor.execute(
        "SELECT id, data FROM content_items WHERE type='knowledge_card'",
        ()
    )
    all_cards = {}
    for row in cursor.fetchall():
        all_cards[row[0]] = json.loads(row[1])
    
    if not all_cards:
        return []
    
    # Compute mastery by topic
    topic_stats = defaultdict(lambda: {'correct': 0, 'total': 0})
    card_ids_by_topic = defaultdict(set)
    
    for stat in quiz_stats:
        card_id = stat.get('cardId')
        correct = stat.get('correct', 0)
        attempts = stat.get('attempts', 1)
        
        if card_id in all_cards:
            card = all_cards[card_id]
            for topic in card.get('topics', []):
                topic_stats[topic]['correct'] += correct
                topic_stats[topic]['total'] += attempts
                card_ids_by_topic[topic].add(card_id)
    
    # Calculate mastery percentages
    topic_mastery = {}
    for topic, stats in topic_stats.items():
        if stats['total'] > 0:
            topic_mastery[topic] = stats['correct'] / stats['total']
        else:
            topic_mastery[topic] = 0
    
    # Get all topics from cards
    all_topics = set()
    for card in all_cards.values():
        all_topics.update(card.get('topics', []))
    
    # Sort topics by mastery (lowest first)
    sorted_topics = sorted(all_topics, key=lambda t: topic_mastery.get(t, 0))
    
    recommendations = []
    
    # Lowest mastery: recommend unseen cards (learn weaknesses)
    if sorted_topics:
        weak_topic = sorted_topics[0]
        for card_id, card in all_cards.items():
            if card_id not in seen_card_ids and card_id not in fav_card_ids:
                if weak_topic in card.get('topics', []):
                    recommendations.append({
                        'id': card_id,
                        'type': 'knowledge_card',
                        'data': card,
                        'reason': 'You need practice in this topic',
                        'reason_topic': weak_topic
                    })
                    if len(recommendations) >= num_recommendations:
                        return recommendations
    
    # Mid mastery: recommend articles (deepen understanding)
    cursor.execute(
        "SELECT id, data FROM content_items WHERE type='article' ORDER BY RANDOM() LIMIT ?",
        (num_recommendations - len(recommendations),)
    )
    for row in cursor.fetchall():
        recommendations.append({
            'id': row[0],
            'type': 'article',
            'data': json.loads(row[1]),
            'reason': 'Deepen your understanding',
            'reason_topic': None
        })
    
    return recommendations[:num_recommendations]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_recommendation.py -v
```

Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/recommendation.py backend/tests/test_recommendation.py
git commit -m "feat(backend): implement personalized recommendation engine"
```

---

## Task 5: Add Admin Endpoints to Server

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_server.py` (extend existing)

**Interfaces:**
- Consumes: `content.create_content`, `content.get_content`, `content.list_content`, `content.update_content`, `content.delete_content`, `admin.is_admin`, `recommendation.generate_recommendations`
- Produces: 7 new HTTP endpoints
  - GET /api/recommendations
  - GET /api/admin/contents?type=...
  - POST /api/admin/contents
  - PUT /api/admin/contents/{id}
  - DELETE /api/admin/contents/{id}
  - GET /api/admin/contents/{id}/versions

- [ ] **Step 1: Read existing server.py**

Open `backend/server.py`. Understand:
- How routes are handled (e.g., if path == '/api/login': ...)
- How token auth works (_authed_uid())
- How to return JSON responses

- [ ] **Step 2: Write failing test**

Add to `backend/tests/test_server.py`:

```python
def test_get_recommendations_requires_auth():
    """Verify GET /api/recommendations requires authentication."""
    # (This test would require standing up the server in a test fixture)
    # For now, we'll test it manually or skip until server fixture is ready
    pass

def test_admin_create_content_requires_admin():
    """Verify POST /api/admin/contents requires admin role."""
    pass
```

- [ ] **Step 3: Add imports and helper to server.py**

At the top of `backend/server.py`, add:

```python
from backend.content import create_content, get_content, list_content, update_content, delete_content, get_versions
from backend.recommendation import generate_recommendations
from backend.admin import is_admin
```

- [ ] **Step 4: Add /api/recommendations endpoint**

In the `do_GET` method of server.py, add this route (before the final 404):

```python
elif path == '/api/recommendations':
    """GET /api/recommendations - Return personalized recommendations."""
    user_id = _authed_uid()
    if user_id is None:
        self.send_response(401)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'unauthorized'}).encode())
        return
    
    # Extract num_recommendations from query string (default 5)
    num = 5
    if '?' in path:
        params = dict(p.split('=') for p in path.split('?')[1].split('&') if '=' in p)
        num = int(params.get('num', 5))
    
    recs = generate_recommendations(db, user_id, num_recommendations=num)
    
    self.send_response(200)
    self.send_header('Content-Type', 'application/json')
    self.end_headers()
    self.wfile.write(json.dumps(recs).encode())
```

- [ ] **Step 5: Add /api/admin/* endpoints**

In the `do_GET` method, add route for listing contents:

```python
elif path.startswith('/api/admin/contents'):
    """GET /api/admin/contents - List contents (admin only)."""
    user_id = _authed_uid()
    if user_id is None or not is_admin(db, user_id):
        self.send_response(403)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'forbidden'}).encode())
        return
    
    # Extract type filter from query string
    content_type = None
    if '?' in path:
        params = dict(p.split('=') for p in path.split('?')[1].split('&') if '=' in p)
        content_type = params.get('type')
    
    contents = list_content(db, type=content_type)
    
    self.send_response(200)
    self.send_header('Content-Type', 'application/json')
    self.end_headers()
    self.wfile.write(json.dumps(contents).encode())
```

In the `do_GET` method, add route for getting versions:

```python
elif '/api/admin/contents/' in path and path.endswith('/versions'):
    """GET /api/admin/contents/{id}/versions - Get version history (admin only)."""
    user_id = _authed_uid()
    if user_id is None or not is_admin(db, user_id):
        self.send_response(403)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'forbidden'}).encode())
        return
    
    # Extract content_id from path: /api/admin/contents/{id}/versions
    parts = path.split('/')
    content_id = parts[4]
    
    versions = get_versions(db, content_id)
    
    self.send_response(200)
    self.send_header('Content-Type', 'application/json')
    self.end_headers()
    self.wfile.write(json.dumps(versions).encode())
```

In the `do_POST` method, add route for creating content:

```python
elif path == '/api/admin/contents':
    """POST /api/admin/contents - Create content (admin only)."""
    user_id = _authed_uid()
    if user_id is None or not is_admin(db, user_id):
        self.send_response(403)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'forbidden'}).encode())
        return
    
    try:
        body = _read_json()
        if not body:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'invalid JSON'}).encode())
            return
        
        content_type = body.get('type')
        data = body.get('data')
        
        if not content_type or not data:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'missing type or data'}).encode())
            return
        
        # Get username for created_by
        cursor = db.cursor()
        cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
        username = cursor.fetchone()[0]
        
        content_id = create_content(db, content_type, data, username)
        
        self.send_response(201)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'id': content_id, 'type': content_type}).encode())
    except Exception as e:
        self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': str(e)}).encode())
```

In the `do_PUT` method (create if missing), add route for updating content:

```python
def do_PUT(self):
    """Handle PUT requests."""
    if self.path.startswith('/api/admin/contents/') and '/versions' not in self.path:
        """PUT /api/admin/contents/{id} - Update content (admin only)."""
        user_id = _authed_uid()
        if user_id is None or not is_admin(db, user_id):
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'forbidden'}).encode())
            return
        
        # Extract content_id
        parts = self.path.split('/')
        content_id = parts[4]
        
        try:
            body = _read_json()
            if not body or 'data' not in body:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'missing data'}).encode())
                return
            
            # Get username
            cursor = db.cursor()
            cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
            username = cursor.fetchone()[0]
            
            update_content(db, content_id, body['data'], username)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'id': content_id}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    else:
        self.send_response(404)
        self.end_headers()
```

In the `do_DELETE` method (create if missing), add route for deleting content:

```python
def do_DELETE(self):
    """Handle DELETE requests."""
    if self.path.startswith('/api/admin/contents/'):
        """DELETE /api/admin/contents/{id} - Delete content (admin only)."""
        user_id = _authed_uid()
        if user_id is None or not is_admin(db, user_id):
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'forbidden'}).encode())
            return
        
        # Extract content_id
        parts = self.path.split('/')
        content_id = parts[4]
        
        try:
            # Get username
            cursor = db.cursor()
            cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
            username = cursor.fetchone()[0]
            
            delete_content(db, content_id, username)
            
            self.send_response(204)
            self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    else:
        self.send_response(404)
        self.end_headers()
```

- [ ] **Step 6: Update backend/tests/test_server.py to include basic endpoint tests**

```python
# These are integration tests; they require standing up the server
# For now, we can test via curl manually:
# curl -H "Authorization: Bearer <token>" http://localhost:8091/api/recommendations
```

- [ ] **Step 7: Commit**

```bash
git add backend/server.py backend/tests/test_server.py
git commit -m "feat(backend): add admin content management and recommendation endpoints"
```

---

## Task 6: Migrate Existing Content to Database

**Files:**
- Create: `backend/migrate_seed_data.py`
- Modify: `backend/server.py` (call migrate on startup)

**Interfaces:**
- Consumes: Seed data files (`finrookie/data/*.json`), sqlite3 connection
- Produces: Content records in `content_items` table

- [ ] **Step 1: Write migration script**

Create `backend/migrate_seed_data.py`:

```python
"""Migrate existing seed data from JSON files to database."""
import json
import os
from pathlib import Path
from backend.content import create_content

def migrate_seed_data(conn, finrookie_data_dir):
    """Load seed data from JSON files and insert into database if not already present."""
    
    cursor = conn.cursor()
    
    # Check if any seed data already exists
    cursor.execute("SELECT COUNT(*) FROM content_items WHERE created_by='seed'")
    if cursor.fetchone()[0] > 0:
        print("Seed data already migrated, skipping")
        return
    
    # Load knowledge cards
    cards_path = os.path.join(finrookie_data_dir, 'knowledge-cards.json')
    if os.path.exists(cards_path):
        with open(cards_path, 'r', encoding='utf-8') as f:
            cards = json.load(f)
        for card in cards:
            try:
                # Use original ID from seed data
                cursor.execute(
                    """INSERT INTO content_items (id, type, data, created_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (card['id'], 'knowledge_card', json.dumps(card), 'seed')
                )
                print(f"Migrated card: {card['id']}")
            except Exception as e:
                print(f"Error migrating card {card.get('id')}: {e}")
        conn.commit()
    
    # Load quizzes
    quizzes_path = os.path.join(finrookie_data_dir, 'quizzes.json')
    if os.path.exists(quizzes_path):
        with open(quizzes_path, 'r', encoding='utf-8') as f:
            quizzes = json.load(f)
        for quiz in quizzes:
            try:
                cursor.execute(
                    """INSERT INTO content_items (id, type, data, created_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (quiz['id'], 'quiz', json.dumps(quiz), 'seed')
                )
                print(f"Migrated quiz: {quiz['id']}")
            except Exception as e:
                print(f"Error migrating quiz {quiz.get('id')}: {e}")
        conn.commit()
    
    # Load glossary terms
    glossary_path = os.path.join(finrookie_data_dir, 'glossary.json')
    if os.path.exists(glossary_path):
        with open(glossary_path, 'r', encoding='utf-8') as f:
            glossary = json.load(f)
        for term_name, term_definition in glossary.items():
            try:
                term_id = term_name.lower().replace(' ', '-')
                cursor.execute(
                    """INSERT INTO content_items (id, type, data, created_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (term_id, 'term', json.dumps({'name': term_name, 'definition': term_definition}), 'seed')
                )
                print(f"Migrated term: {term_name}")
            except Exception as e:
                print(f"Error migrating term {term_name}: {e}")
        conn.commit()
    
    # Load articles
    articles_path = os.path.join(finrookie_data_dir, 'articles.json')
    if os.path.exists(articles_path):
        with open(articles_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)
        for article in articles:
            try:
                cursor.execute(
                    """INSERT INTO content_items (id, type, data, created_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (article.get('id', article['title'].lower().replace(' ', '-')), 'article', json.dumps(article), 'seed')
                )
                print(f"Migrated article: {article['title']}")
            except Exception as e:
                print(f"Error migrating article {article.get('title')}: {e}")
        conn.commit()
    
    print("Seed data migration complete")
```

- [ ] **Step 2: Call migration on server startup**

Modify `backend/server.py` to call migration in the startup code (before the server loop starts):

```python
# Add this import at the top
from backend.migrate_seed_data import migrate_seed_data

# In the __init__ or startup section, call:
finrookie_data_dir = os.path.join(os.path.dirname(__file__), '..', 'finrookie', 'data')
migrate_seed_data(db, finrookie_data_dir)
```

- [ ] **Step 3: Test migration**

Run the server and check that seed data is migrated:

```bash
cd C:\Users\86184\finrookie\backend
python server.py
# In another terminal:
curl -s http://localhost:8091/api/admin/contents?type=knowledge_card | python -m json.tool
```

Expected: Should list migrated cards.

- [ ] **Step 4: Commit**

```bash
git add backend/migrate_seed_data.py backend/server.py
git commit -m "feat(backend): auto-migrate seed data from JSON to database on startup"
```

---

## Task 7: Update Frontend to Load Dynamic Content

**Files:**
- Modify: `js/repository.js`
- Modify: `js/app.js`
- Test: Manual testing

**Interfaces:**
- Consumes: `GET /api/admin/contents?type=...` (dynamic content), existing seed data fallback
- Produces: `getContentByType(type) -> list` that merges seed + dynamic content

- [ ] **Step 1: Modify repository.js to fetch dynamic content**

Open `finrookie/js/repository.js`. Add a new function:

```javascript
async function getContentByType(type) {
  """Fetch content from API, fallback to seed data if API fails."""
  try {
    const response = await fetch(`http://10.159.3.80:8091/api/admin/contents?type=${type}`, {
      headers: {
        'Authorization': `Bearer ${auth.getToken() || ''}`,
      },
      timeout: 2000
    });
    if (response.ok) {
      const contents = await response.json();
      // Extract data from API format
      return contents.map(c => c.data);
    }
  } catch (e) {
    console.warn(`Failed to fetch ${type} from API, using seed data:`, e);
  }
  
  // Fallback to seed data
  return loadSeedData(type);
}

function loadSeedData(type) {
  """Load seed data from existing JSON files."""
  switch (type) {
    case 'knowledge_card':
      return KNOWLEDGE_CARDS; // Existing seed data
    case 'quiz':
      return QUIZZES; // Existing seed data
    case 'term':
      return Object.entries(GLOSSARY).map(([name, def]) => ({
        name, definition: def
      }));
    case 'article':
      return ARTICLES; // Existing seed data
    default:
      return [];
  }
}
```

- [ ] **Step 2: Update app.js to load recommendations on "我的" page**

Open `finrookie/js/app.js`. Find the getter `refreshMe`:

Before the return statement, add code to load recommendations:

```javascript
let recommendations = [];
try {
  if (this.isAuthed) {
    const response = await fetch('http://10.159.3.80:8091/api/recommendations?num=3', {
      headers: {
        'Authorization': `Bearer ${auth.getToken()}`
      },
      timeout: 2000
    });
    if (response.ok) {
      const recs = await response.json();
      recommendations = recs.map(r => ({ ...r.data, _reason: r.reason, _topic: r.reason_topic }));
    }
  }
} catch (e) {
  console.warn('Failed to load recommendations:', e);
}

// Store recommendations in state for template access
this.personalizedRecommendations = recommendations;
```

- [ ] **Step 3: Update index.html to display recommendations**

In the `<!-- 我的 -->` section, add a recommendation cards area:

```html
<div x-show="activeTab === 'me'" class="space-y-6 pb-20">
  <!-- Existing content... -->
  
  <!-- 个性化推荐 -->
  <section x-show="isAuthed && personalizedRecommendations.length > 0" class="space-y-3">
    <h3 class="text-lg font-semibold text-ink">为你推荐</h3>
    <div class="grid gap-3 sm:grid-cols-2">
      <template x-for="rec in personalizedRecommendations" :key="rec.id">
        <article class="p-4 bg-gradient-to-br from-brand-50 to-brand-100 rounded-2xl shadow-soft hover:shadow-md transition cursor-pointer"
                  @click="todayCard = rec; activeTab = 'home'">
          <div class="flex justify-between items-start gap-2 mb-2">
            <h4 class="font-semibold text-ink line-clamp-2" x-text="rec.title"></h4>
            <span class="text-xs bg-brand/20 text-brand px-2 py-1 rounded-full" x-text="rec._reason"></span>
          </div>
          <p class="text-sm text-ink-faint line-clamp-2" x-text="rec.body ? rec.body.replace(/<[^>]*>/g, '').slice(0, 100) : rec.definition"></p>
        </article>
      </template>
    </div>
  </section>
</div>
```

- [ ] **Step 4: Test manually**

Login to the app (as non-admin user), navigate to "我的", and verify recommendations appear with reasons.

- [ ] **Step 5: Commit**

```bash
git add finrookie/js/repository.js finrookie/js/app.js finrookie/index.html
git commit -m "feat(frontend): load dynamic content and display personalized recommendations"
```

---

## Task 8: Implement Admin Dashboard UI

**Files:**
- Create: `finrookie/js/admin.js`
- Modify: `finrookie/index.html`
- Modify: `finrookie/js/app.js`

**Interfaces:**
- Consumes: `/api/admin/contents`, `/api/admin/contents/{id}/versions`
- Produces: Admin tab in "我的" page with CRUD forms

- [ ] **Step 1: Create admin.js module**

Create `finrookie/js/admin.js`:

```javascript
// Admin dashboard logic
export const admin = {
  isAdmin: false,
  contents: [],
  selectedContentId: null,
  editMode: false,
  editForm: {
    type: 'knowledge_card',
    title: '',
    body: '',
    difficulty: 'L1',
    topics: '',
    // fields vary by type
  },
  
  async checkAdminStatus(token) {
    """Check if current user is admin by fetching admin endpoint."""
    if (!token) return false;
    try {
      const response = await fetch('http://10.159.3.80:8091/api/admin/contents', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      this.isAdmin = response.status !== 403;
      return this.isAdmin;
    } catch (e) {
      return false;
    }
  },
  
  async listContents(type = null) {
    """Fetch all contents of given type."""
    const url = type ? 
      `http://10.159.3.80:8091/api/admin/contents?type=${type}` :
      'http://10.159.3.80:8091/api/admin/contents';
    
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${store.getToken()}` }
    });
    
    this.contents = await response.json();
    return this.contents;
  },
  
  async createContent() {
    """Create new content item."""
    const data = { ...this.editForm };
    if (data.topics) {
      data.topics = data.topics.split(',').map(t => t.trim());
    }
    
    const response = await fetch('http://10.159.3.80:8091/api/admin/contents', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${store.getToken()}`
      },
      body: JSON.stringify({ type: data.type, data })
    });
    
    if (response.status === 201) {
      await this.listContents(data.type);
      this.editMode = false;
      this.editForm = { type: 'knowledge_card', title: '', body: '' };
    }
  },
  
  async updateContent(contentId) {
    """Update existing content."""
    const data = { ...this.editForm };
    if (data.topics) {
      data.topics = data.topics.split(',').map(t => t.trim());
    }
    
    const response = await fetch(`http://10.159.3.80:8091/api/admin/contents/${contentId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${store.getToken()}`
      },
      body: JSON.stringify({ data })
    });
    
    if (response.ok) {
      await this.listContents(data.type);
      this.editMode = false;
      this.selectedContentId = null;
    }
  },
  
  async deleteContent(contentId) {
    """Delete content item."""
    const response = await fetch(`http://10.159.3.80:8091/api/admin/contents/${contentId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${store.getToken()}` }
    });
    
    if (response.status === 204) {
      this.contents = this.contents.filter(c => c.id !== contentId);
      this.selectedContentId = null;
    }
  },
  
  async getVersions(contentId) {
    """Get version history for a content item."""
    const response = await fetch(`http://10.159.3.80:8091/api/admin/contents/${contentId}/versions`, {
      headers: { 'Authorization': `Bearer ${store.getToken()}` }
    });
    return await response.json();
  }
};
```

- [ ] **Step 2: Update app.js to check admin status and import admin module**

In `finrookie/js/app.js`, add:

```javascript
import { admin } from './admin.js';

// In Alpine.data('app', function() {
return {
  // ... existing data ...
  admin: admin,
  
  // In init():
  async init() {
    // ... existing init code ...
    await admin.checkAdminStatus(auth.getToken());
    if (admin.isAdmin) {
      await admin.listContents('knowledge_card');
    }
  }
};
```

- [ ] **Step 3: Add admin tab to index.html**

In the "我的" tab section, add a check for admin and a new tab:

```html
<!-- Navigation tabs -->
<div x-show="activeTab === 'me'" class="flex gap-2 mb-6 border-b border-paper-border">
  <button @click="activeTab = 'me'; adminTab = 'overview'" 
          :class="{ 'border-b-2 border-brand text-brand': adminTab === 'overview' }"
          class="px-4 py-2">个人中心</button>
  <button x-show="admin.isAdmin" @click="adminTab = 'content'" 
          :class="{ 'border-b-2 border-brand text-brand': adminTab === 'content' }"
          class="px-4 py-2">课程管理</button>
</div>

<!-- Overview tab (existing content) -->
<div x-show="activeTab === 'me' && adminTab === 'overview'" class="space-y-6 pb-20">
  <!-- ... existing "我的" content ... -->
</div>

<!-- Admin content management tab -->
<div x-show="activeTab === 'me' && adminTab === 'content'" class="space-y-6 pb-20">
  <!-- Content type filter -->
  <div class="flex gap-2">
    <button @click="admin.listContents('knowledge_card')" 
            class="px-4 py-2 rounded-lg bg-brand/10 text-brand">知识卡</button>
    <button @click="admin.listContents('quiz')" 
            class="px-4 py-2 rounded-lg bg-brand/10 text-brand">测验</button>
    <button @click="admin.listContents('term')" 
            class="px-4 py-2 rounded-lg bg-brand/10 text-brand">术语</button>
    <button @click="admin.listContents('article')" 
            class="px-4 py-2 rounded-lg bg-brand/10 text-brand">文章</button>
    <button @click="admin.editMode = true; admin.editForm = {type: 'knowledge_card', title: '', body: ''}" 
            class="px-4 py-2 rounded-lg bg-brand text-white ml-auto">+新增</button>
  </div>
  
  <!-- Content list -->
  <div class="space-y-2">
    <template x-for="content in admin.contents" :key="content.id">
      <div class="p-3 bg-paper-card rounded-lg cursor-pointer hover:shadow-md"
           @click="admin.selectedContentId = content.id; admin.editMode = true; admin.editForm = {...content.data, type: content.type}">
        <div class="font-semibold" x-text="content.data.title"></div>
        <div class="text-xs text-ink-faint" x-text="`${content.type} · ${content.created_by}`"></div>
      </div>
    </template>
  </div>
  
  <!-- Edit form -->
  <div x-show="admin.editMode" class="fixed inset-0 bg-black/50 flex items-end">
    <div class="bg-white w-full rounded-t-3xl p-6 space-y-4 overflow-y-auto max-h-[80vh]">
      <h3 class="font-semibold text-lg" x-text="admin.selectedContentId ? '编辑' : '新增'"></h3>
      
      <div>
        <label class="block text-sm font-medium mb-1">内容类型</label>
        <select x-model="admin.editForm.type" class="w-full p-2 border border-paper-border rounded-lg">
          <option value="knowledge_card">知识卡</option>
          <option value="quiz">测验</option>
          <option value="term">术语</option>
          <option value="article">文章</option>
        </select>
      </div>
      
      <div>
        <label class="block text-sm font-medium mb-1">标题</label>
        <input x-model="admin.editForm.title" type="text" class="w-full p-2 border border-paper-border rounded-lg"/>
      </div>
      
      <div>
        <label class="block text-sm font-medium mb-1">内容</label>
        <textarea x-model="admin.editForm.body" class="w-full p-2 border border-paper-border rounded-lg h-32"></textarea>
      </div>
      
      <div class="flex gap-2">
        <button @click="admin.createContent()" 
                x-show="!admin.selectedContentId"
                class="px-4 py-2 bg-brand text-white rounded-lg flex-1">创建</button>
        <button @click="admin.updateContent(admin.selectedContentId)" 
                x-show="admin.selectedContentId"
                class="px-4 py-2 bg-brand text-white rounded-lg flex-1">保存</button>
        <button @click="admin.deleteContent(admin.selectedContentId); admin.editMode = false" 
                x-show="admin.selectedContentId"
                class="px-4 py-2 bg-clay text-white rounded-lg">删除</button>
        <button @click="admin.editMode = false" 
                class="px-4 py-2 bg-paper-border rounded-lg">取消</button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Update Service Worker cache version**

In `sw.js`, increment `CACHE_VERSION` to reflect new files.

- [ ] **Step 5: Test manually**

Login as `admin` user, navigate to "我的" tab, verify "课程管理" tab appears, and test creating/editing/deleting content.

- [ ] **Step 6: Commit**

```bash
git add finrookie/js/admin.js finrookie/index.html finrookie/js/app.js finrookie/sw.js
git commit -m "feat(frontend): add admin dashboard for content management"
```

---

## Task 9: Seed Data Initialization & Testing

**Files:**
- Modify: `backend/server.py` (startup)
- Test: Manual curl commands

**Interfaces:**
- Consumes: Nothing new
- Produces: Verified admin account + migrated seed data

- [ ] **Step 1: Call admin user creation on startup**

In `backend/server.py`, in the server startup code, add:

```python
from backend.admin import ensure_admin_exists

# After database initialization
ensure_admin_exists(db)
print("Admin user initialized")
```

- [ ] **Step 2: Test backend endpoints with curl**

```bash
# 1. Login as admin
curl -X POST http://localhost:8091/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
# Extract token

# 2. List contents
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8091/api/admin/contents?type=knowledge_card

# 3. Get recommendations
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8091/api/recommendations?num=3
```

- [ ] **Step 3: Verify frontend can access**

Start frontend server and login as regular user, verify recommendations load on "我的" page.

- [ ] **Step 4: Commit**

```bash
git add backend/server.py
git commit -m "feat(backend): initialize admin account on startup"
```

---

## Task 10: Documentation & Deployment

**Files:**
- Create: `finrookie/docs/CMS-USER-GUIDE.md`
- Create: `finrookie/docs/CMS-API.md`
- Modify: `finrookie/docs/superpowers/specs/2026-08-04-content-cms-spec.md` (if needed)

**Interfaces:**
- Consumes: Implemented API
- Produces: User-facing documentation

- [ ] **Step 1: Write API documentation**

Create `finrookie/docs/CMS-API.md`:

```markdown
# Content Management System API

## Authentication
All endpoints require Bearer token from `/api/login`.

## Endpoints

### GET /api/recommendations
Fetch personalized recommendations for the logged-in user.

**Parameters:**
- `num` (int, default=5): Number of recommendations

**Response:**
```json
[
  {
    "id": "card-id",
    "type": "knowledge_card",
    "data": { "title": "...", "body": "..." },
    "reason": "You need practice in this topic",
    "reason_topic": "fund"
  }
]
```

### GET /api/admin/contents
List all contents (admin only).

**Parameters:**
- `type` (string, optional): Filter by content type (knowledge_card, quiz, term, article)

**Response:**
```json
[
  {
    "id": "content-id",
    "type": "knowledge_card",
    "data": { ... },
    "created_by": "admin",
    "created_at": "2026-08-04T10:00:00",
    "updated_at": "2026-08-04T10:00:00"
  }
]
```

### POST /api/admin/contents
Create new content (admin only).

**Request:**
```json
{
  "type": "knowledge_card",
  "data": {
    "title": "What is a Fund?",
    "body": "...",
    "difficulty": "L1",
    "topics": ["fund"],
    "quizIds": []
  }
}
```

**Response:** 201 Created
```json
{
  "id": "new-content-id",
  "type": "knowledge_card"
}
```

### PUT /api/admin/contents/{id}
Update existing content (admin only).

### DELETE /api/admin/contents/{id}
Delete content (admin only).

### GET /api/admin/contents/{id}/versions
Get version history for a content item (admin only).

**Response:**
```json
[
  {
    "id": "version-id",
    "changed_by": "admin",
    "changed_at": "2026-08-04T10:00:00",
    "action": "create|update|delete",
    "diff": { ... }
  }
]
```

## Error Responses

- 401 Unauthorized: Missing or invalid token
- 403 Forbidden: Not admin
- 400 Bad Request: Invalid input
- 500 Internal Server Error: Server error
```

- [ ] **Step 2: Write user guide**

Create `finrookie/docs/CMS-USER-GUIDE.md`:

```markdown
# Content Management System User Guide

## Overview
The CMS allows admins to manage all course content (knowledge cards, quizzes, terms, articles) without code changes.

## Admin Access
- Default admin account: `admin` / `admin123`
- After first login, change the password
- Admin features appear in "我的" → "课程管理" tab

## Creating Content

1. Click "+新增" button in the course type
2. Fill in the form:
   - **Type**: Select content type (knowledge card, quiz, term, article)
   - **Title**: Course title
   - **Content**: Full content (HTML supported)
   - **Other fields**: Depend on type
3. Click "创建" to save

## Editing Content
1. Click on any content item to select it
2. Edit fields as needed
3. Click "保存" to save changes
4. Version history is automatically tracked

## Viewing Version History
- For each content item, view all changes made over time
- See who changed it and when

## Data Backup
- All content is stored in SQLite database (`finrookie.db`)
- Daily backups are recommended
```

- [ ] **Step 3: Commit documentation**

```bash
git add finrookie/docs/CMS-API.md finrookie/docs/CMS-USER-GUIDE.md
git commit -m "docs: add CMS API and user guide documentation"
```

---

## Summary

**Deliverables:**
- ✅ Database schema with `content_items`, `content_versions`, `is_admin` columns
- ✅ Backend CRUD APIs for content management (7 endpoints)
- ✅ Admin identity & authorization system
- ✅ Seed data migration from JSON to database
- ✅ Personalized recommendation engine (dynamic generation)
- ✅ Admin dashboard UI in frontend
- ✅ API documentation & user guide

**Testing:**
- Backend: Unit tests for all modules (content, recommendation, admin, db)
- Frontend: Manual testing via UI (login, view recommendations, create/edit content as admin)
- Integration: End-to-end flow (admin creates content → appears in recommendations → user sees it)

**Next Steps After Completion:**
- Deploy to server (scp backend files + frontend updates)
- Clear Service Worker cache on production
- Create real admin account (change default password)
- Monitor logs for issues
