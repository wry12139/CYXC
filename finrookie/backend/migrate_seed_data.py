"""Migrate seed data from JSON files to SQLite database."""
import json
import os
from content import create_content


def migrate_seed_data(conn, finrookie_dir='.'):
    """Load seed data from JSON files and insert into database if not already present."""

    # Check if seed data already migrated
    row = conn.execute("SELECT COUNT(*) FROM content_items WHERE created_by='seed' AND deleted_at IS NULL").fetchone()
    if row and row[0] > 0:
        print("Seed data already migrated, skipping")
        return

    # Ensure 'seed' user exists (for foreign key reference)
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, created_at, is_admin) VALUES (?, ?, ?, datetime('now'), 0)",
            ('seed', 'seed_hash', 'seed_salt')
        )
        conn.commit()
    except:
        pass  # User may already exist

    # Support both repo root and data subdirectory
    data_dir = os.path.join(finrookie_dir, 'data')
    if not os.path.exists(data_dir):
        data_dir = finrookie_dir  # Fall back to passed directory if no data/ subdirectory

    # Load knowledge cards
    cards_path = os.path.join(data_dir, 'knowledge-cards.json')
    if os.path.exists(cards_path):
        with open(cards_path, 'r', encoding='utf-8') as f:
            cards = json.load(f)
        for card in cards:
            try:
                # Preserve original card ID
                card_id = card.get('id')
                create_content(conn, 'knowledge_card', card, 'seed', content_id=card_id)
                title = card.get('title', 'N/A')
                print(f"  [OK] Card: {title[:40]}")
            except Exception as e:
                print(f"  [ERR] Card error: {str(e)[:60]}")

    # Load quizzes
    quiz_path = os.path.join(data_dir, 'quiz.json')
    if os.path.exists(quiz_path):
        with open(quiz_path, 'r', encoding='utf-8') as f:
            quizzes = json.load(f)
        for quiz in quizzes:
            try:
                create_content(conn, 'quiz', quiz, 'seed')
                print(f"  [OK] Quiz: {quiz.get('id', 'N/A')[:40]}")
            except Exception as e:
                print(f"  [ERR] Quiz error: {str(e)[:60]}")

    # Load glossary terms
    glossary_path = os.path.join(data_dir, 'glossary.json')
    if os.path.exists(glossary_path):
        with open(glossary_path, 'r', encoding='utf-8') as f:
            glossary = json.load(f)
        term_count = 0
        for term_name, term_def in glossary.items():
            try:
                create_content(conn, 'term', {
                    'name': term_name,
                    'definition': term_def
                }, 'seed')
                term_count += 1
            except Exception as e:
                pass
        print(f"  [OK] Terms: {term_count} migrated")

    # Load articles
    articles_path = os.path.join(data_dir, 'articles.json')
    if os.path.exists(articles_path):
        with open(articles_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)
        for article in articles:
            try:
                create_content(conn, 'article', article, 'seed')
                title = article.get('title', 'N/A')
                print(f"  [OK] Article: {title[:40]}")
            except Exception as e:
                print(f"  [ERR] Article error: {str(e)[:60]}")

    print("\nSeed data migration complete!")

