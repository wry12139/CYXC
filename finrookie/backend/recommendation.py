import json
from collections import defaultdict


def generate_recommendations(conn, user_id, num_recommendations=5):
    row = conn.execute('SELECT data_json FROM user_data WHERE user_id=?', (user_id,)).fetchone()
    if row:
        user_data = json.loads(row[0])
    else:
        user_data = {}

    quiz_stats = user_data.get('quizStats', []) or []
    seen_card_ids = set(user_data.get('seenCardIds', []) or [])
    favorite_ids = set((user_data.get('favorites') or {}).get('cards', []) or [])

    content_rows = conn.execute(
        'SELECT id, type, data FROM content_items ORDER BY created_at DESC'
    ).fetchall()
    cards = {}
    articles = []
    for content_id, content_type, data_json in content_rows:
        parsed = json.loads(data_json)
        if content_type == 'knowledge_card':
            cards[content_id] = parsed
        elif content_type == 'article':
            articles.append((content_id, parsed))

    if not cards and not articles:
        return []

    topic_scores = defaultdict(lambda: {'correct': 0, 'attempts': 0})
    for stat in quiz_stats:
        card = cards.get(stat.get('cardId'))
        if not card:
            continue
        for topic in card.get('topics', []):
            topic_scores[topic]['correct'] += stat.get('correct', 0)
            topic_scores[topic]['attempts'] += stat.get('attempts', 0)

    all_topics = set()
    for card in cards.values():
        all_topics.update(card.get('topics', []))

    weakest_topic = None
    if all_topics:
        def mastery(topic):
            stats = topic_scores[topic]
            if not stats['attempts']:
                return 0
            return stats['correct'] / stats['attempts']
        weakest_topic = min(all_topics, key=mastery)

    recommendations = []
    for content_id, card in cards.items():
        if len(recommendations) >= num_recommendations:
            break
        if content_id in seen_card_ids or content_id in favorite_ids:
            continue
        if weakest_topic and weakest_topic not in card.get('topics', []):
            continue
        recommendations.append({
            'id': content_id,
            'type': 'knowledge_card',
            'data': card,
            'reason': 'You need practice in this topic',
            'reason_topic': weakest_topic,
        })

    for content_id, article in articles:
        if len(recommendations) >= num_recommendations:
            break
        recommendations.append({
            'id': content_id,
            'type': 'article',
            'data': article,
            'reason': 'Deepen your understanding',
            'reason_topic': None,
        })

    return recommendations[:num_recommendations]
