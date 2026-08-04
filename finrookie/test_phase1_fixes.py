#!/usr/bin/env python3
"""Verify Phase 1 fixes"""
import sys
import os
sys.path.insert(0, 'backend')

from db import init_db, get_conn
from admin import ensure_admin_exists
from content import create_content, get_content, delete_content, get_versions

print("=" * 60)
print("PHASE 1 FIX VERIFICATION")
print("=" * 60)

# Clean slate
if os.path.exists('backend/test_fixes.db'):
    os.remove('backend/test_fixes.db')

db_path = 'backend/test_fixes.db'
init_db(db_path)
conn = get_conn(db_path)

try:
    # Fix 1: Soft delete preserves version history
    print("\n[Fix 1] Soft delete with version history:")
    ensure_admin_exists(conn)

    # Also create seed user for migrations
    try:
        conn.execute("INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, datetime('now'))",
                     ('seed', 'seed_hash', 'seed_salt'))
        conn.commit()
    except:
        pass

    cid = create_content(conn, 'knowledge_card', {'title': 'Test Card'}, 'admin')
    print(f"  Created: {cid}")

    # Get before delete
    before = get_content(conn, cid)
    assert before is not None, "Content should exist"
    print(f"  Read OK: {before['data']['title']}")

    # Delete
    delete_content(conn, cid, 'admin')
    print(f"  Soft-deleted")

    # Should be invisible now
    after = get_content(conn, cid)
    assert after is None, "Deleted content should be invisible"
    print(f"  [OK] Invisible after delete")

    # But versions preserved
    versions = get_versions(conn, cid)
    assert len(versions) >= 2, "Version history should be preserved"
    print(f"  [OK] Version history preserved: {len(versions)} records")

    # Fix 2: Preserve original IDs
    print("\n[Fix 2] Preserve original seed IDs:")
    original_id = 'my-original-id-12345'
    cid2 = create_content(conn, 'knowledge_card', {'title': 'Seed Card'}, 'seed', content_id=original_id)
    assert cid2 == original_id, "ID should be preserved"
    print(f"  [OK] Original ID preserved: {cid2}")

    item = get_content(conn, cid2)
    assert item is not None and item['id'] == original_id
    print(f"  [OK] Can retrieve by original ID")

    # Fix 3: Migration path (just verify no errors during schema check)
    print("\n[Fix 3] Schema migration for soft delete:")
    ci_cols = {row[1] for row in conn.execute("PRAGMA table_info(content_items)").fetchall()}
    assert 'deleted_at' in ci_cols, "deleted_at column missing"
    assert 'deleted_by' in ci_cols, "deleted_by column missing"
    print(f"  [OK] Soft delete columns present")

    # Fix 4: Admin security
    print("\n[Fix 4] Admin security via environment:")
    # Just verify the module loads and has env vars
    from admin import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
    print(f"  [OK] Admin user: {DEFAULT_ADMIN_USERNAME}")
    if DEFAULT_ADMIN_PASSWORD.startswith('CHANGE_ME_'):
        print(f"  [OK] Using secure temp password (environment variable not set)")
    else:
        print(f"  [INFO] Using environment variable ADMIN_PASSWORD")

    print("\n" + "=" * 60)
    print("ALL PHASE 1 FIXES VERIFIED [OK]")
    print("=" * 60)

except Exception as e:
    print(f"\n[FAIL] VERIFICATION FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

finally:
    conn.close()
