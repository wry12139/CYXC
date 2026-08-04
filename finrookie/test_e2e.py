#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'backend')

from db import init_db, get_conn, DEFAULT_DB_PATH
from admin import ensure_admin_exists, is_admin
from content import create_content, get_content, list_content, update_content, delete_content, get_versions

# Initialize
init_db(DEFAULT_DB_PATH)
conn = get_conn(DEFAULT_DB_PATH)

try:
    # Test 1: Admin
    ensure_admin_exists(conn)
    row = conn.execute('SELECT id FROM users WHERE username="admin"').fetchone()
    admin_uid = row[0]
    assert is_admin(conn, admin_uid)
    print('PASS: Admin user created')

    # Test 2: Create content
    cid = create_content(conn, 'knowledge_card', {'title': 'ETF', 'topics': ['fund']}, 'admin')
    print(f'PASS: Content created {cid}')

    # Test 3: Read
    item = get_content(conn, cid)
    assert item['data']['title'] == 'ETF'
    print('PASS: Read content')

    # Test 4: List
    items = list_content(conn, 'knowledge_card')
    assert len(items) > 0
    print(f'PASS: List query {len(items)} items')

    # Test 5: Update
    update_content(conn, cid, {'title': 'ETF Detailed', 'topics': ['fund']}, 'admin')
    updated = get_content(conn, cid)
    assert updated['data']['title'] == 'ETF Detailed'
    print('PASS: Update content')

    # Test 6: Versions
    versions = get_versions(conn, cid)
    assert len(versions) >= 2
    print(f'PASS: Version history {len(versions)} records')

    # Test 7: Delete
    delete_content(conn, cid, 'admin')
    deleted = get_content(conn, cid)
    assert deleted is None
    print('PASS: Delete content')

    print('\n=== ALL TESTS PASSED ===')

except Exception as e:
    print(f'FAIL: {e}')
    import traceback
    traceback.print_exc()

finally:
    conn.close()
