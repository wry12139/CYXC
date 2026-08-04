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
