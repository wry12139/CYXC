import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import content


class TestContent(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.maxDiff = None

    def tearDown(self):
        self.conn.close()

    def test_create_and_get_content(self):
        item_id = content.create_content(
            self.conn,
            'knowledge_card',
            {'title': 'ETF 入门', 'body': '一种基金'},
            'admin',
        )

        item = content.get_content(self.conn, item_id)

        self.assertEqual(item['id'], item_id)
        self.assertEqual(item['type'], 'knowledge_card')
        self.assertEqual(item['data']['title'], 'ETF 入门')
        self.assertEqual(item['version'], 1)
        self.assertEqual(item['created_by'], 'admin')
        self.assertEqual(item['updated_by'], 'admin')

    def test_list_content_can_filter_by_type(self):
        card_id = content.create_content(
            self.conn,
            'knowledge_card',
            {'title': '基金'},
            'admin',
        )
        article_id = content.create_content(
            self.conn,
            'article',
            {'title': '市场日报'},
            'editor',
        )

        all_items = content.list_content(self.conn)
        cards = content.list_content(self.conn, 'knowledge_card')

        self.assertEqual([item['id'] for item in all_items], [card_id, article_id])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['id'], card_id)
        self.assertEqual(cards[0]['type'], 'knowledge_card')

    def test_update_content_replaces_data_and_creates_version_record(self):
        item_id = content.create_content(
            self.conn,
            'quiz',
            {'question': '什么是ETF?', 'options': ['基金', '股票']},
            'teacher',
        )

        content.update_content(
            self.conn,
            item_id,
            {'question': '什么是ETF?', 'options': ['基金', '债券'], 'answer': '基金'},
            'reviewer',
        )

        item = content.get_content(self.conn, item_id)
        versions = content.get_versions(self.conn, item_id)

        self.assertEqual(item['version'], 2)
        self.assertEqual(item['updated_by'], 'reviewer')
        self.assertEqual(item['data']['options'], ['基金', '债券'])
        self.assertEqual(item['data']['answer'], '基金')
        self.assertEqual(len(versions), 2)
        self.assertEqual([entry['action'] for entry in versions], ['create', 'update'])
        self.assertEqual(versions[-1]['changed_by'], 'reviewer')
        self.assertEqual(versions[-1]['version'], 2)
        self.assertEqual(versions[-1]['data']['answer'], '基金')

    def test_delete_content_removes_row_and_keeps_delete_version(self):
        item_id = content.create_content(
            self.conn,
            'term',
            {'title': '波动率', 'definition': '价格波动程度'},
            'admin',
        )

        content.delete_content(self.conn, item_id, 'moderator')

        self.assertIsNone(content.get_content(self.conn, item_id))
        versions = content.get_versions(self.conn, item_id)
        self.assertEqual([entry['action'] for entry in versions], ['create', 'delete'])
        self.assertEqual(versions[-1]['changed_by'], 'moderator')
        self.assertEqual(versions[-1]['data']['definition'], '价格波动程度')

    def test_get_versions_returns_history_in_order(self):
        item_id = content.create_content(
            self.conn,
            'article',
            {'title': '日报 1'},
            'editor',
        )
        content.update_content(self.conn, item_id, {'title': '日报 2'}, 'editor')
        content.update_content(self.conn, item_id, {'title': '日报 3'}, 'chief-editor')

        versions = content.get_versions(self.conn, item_id)

        self.assertEqual([entry['version'] for entry in versions], [1, 2, 3])
        self.assertEqual([entry['data']['title'] for entry in versions], ['日报 1', '日报 2', '日报 3'])
        self.assertEqual([entry['changed_by'] for entry in versions], ['editor', 'editor', 'chief-editor'])

    def test_rejects_unsupported_content_type(self):
        with self.assertRaises(ValueError):
            content.create_content(self.conn, 'briefing', {'title': 'x'}, 'admin')


if __name__ == '__main__':
    unittest.main()
