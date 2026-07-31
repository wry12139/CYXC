#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -c "import db; db.init_db(db.DEFAULT_DB_PATH); print('db ready')"
exec python3 server.py
