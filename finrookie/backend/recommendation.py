import json
from collections import defaultdict


def _load_user_data(conn, user_id):
    row = conn.execute(
        "SELECT data_json FROM user_data WHERE user_id=?",
        (user_id,),
    ).fetchone()
    if not row:
        return {'quizStats': [], 'seenCardIds': [], 'favorites': {'cards': []}}
    data = json.loads(row[0])
    if not isinstance(data, dict):
        return {'quizStats': [], 'seenCardIds': [], 'favorites': {'cards': []}}
    return data


def _load_content_items(conn):
    cards = {}
    articles = []
    try:
        rows = conn.execute(
            "SELECT id, type, data FROM content_items"
        ).fetchall()
    except Exception:
        return cards, articles

    for item_id, item_type, data_json in rows:
        data = json.loads(data_json)
        if item_type == 'knowledge_card':
            cards[item_id] = data
        elif item_type == 'article':
            articles.append((item_id, data))
    return cards, articles


def _topic_mastery(quiz_stats, cards):
    stats_by_topic = defaultdict(lambda: {'correct': 0, 'attempts': 0})
    for stat in quiz_stats:
        card_id = stat.get('cardId')
        if card_id not in cards:
            continue
        attempts = stat.get('attempts', 0) or 0
        correct = stat.get('correct', 0) or 0
        for topic in cards[card_id].get('topics', []):
            stats_by_topic[topic]['attempts'] += attempts
            stats_by_topic[topic]['correct'] += correct

    mastery = {}
    for topic, totals in stats_by_topic.items():
        if totals['attempts'] > 0:
            mastery[topic] = totals['correct'] / totals['attempts']
        else:
            mastery[topic] = 0
    return mastery


def generate_recommendations(conn, user_id, num_recommendations=5):
    user_data = _load_user_data(conn, user_id)
    quiz_stats = user_data.get('quizStats', [])
    seen_ids = set(user_data.get('seenCardIds', []))
    favorite_cards = user_data.get('favorites', {}).get('cards', [])
    blocked_ids = seen_ids | set(favorite_cards)

    cards, articles = _load_content_items(conn)
    if not cards and not articles:
        return []

    all_topics = []
    seen_topics = set()
    for card in cards.values():
        for topic in card.get('topics', []):
            if topic not in seen_topics:
                seen_topics.add(topic)
                all_topics.append(topic)

    mastery = _topic_mastery(quiz_stats, cards)
    ranked_topics = sorted(all_topics, key=lambda topic: (mastery.get(topic, 0), topic))

    recommendations = []
    used_ids = set()

    def add_recommendation(item_id, item_type, data, reason, reason_topic):
        if item_id in used_ids or item_id in blocked_ids:
            return False
        recommendations.append({
            'id': item_id,
            'type': item_type,
            'data': data,
            'reason': reason,
            'reason_topic': reason_topic,
        })
        used_ids.add(item_id)
        return len(recommendations) >= num_recommendations

    if ranked_topics:
        weak_topic = ranked_topics[0]
        for item_id, card in cards.items():
            if weak_topic in card.get('topics', []):
                if add_recommendation(
                    item_id,
                    'knowledge_card',
                    card,
                    'You need practice in this topic',
                    weak_topic,
                ):
                    return recommendations

    if len(ranked_topics) >= 2:
        strong_topic = ranked_topics[-1]
    elif ranked_topics:
        strong_topic = ranked_topics[0]
    else:
        strong_topic = None

    for item_id, article in articles:
        article_topics = article.get('topics', [])
        if strong_topic is None or strong_topic in article_topics:
            if add_recommendation(
                item_id,
                'article',
                article,
                'Deepen your understanding',
                strong_topic,
            ):
                return recommendations

    for item_id, card in cards.items():
        if add_recommendation(
            item_id,
            'knowledge_card',
            card,
            'Continue building your knowledge',
            (card.get('topics') or [None])[0],
        ):
            return recommendations

    return recommendations
