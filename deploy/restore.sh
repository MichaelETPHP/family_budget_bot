#!/usr/bin/env bash
# Load a database into the running bot (e.g. your existing local expenses.db, or a backup).
# Usage:  ./deploy/restore.sh path/to/expenses.db
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:?Usage: ./deploy/restore.sh path/to/expenses.db}"

docker compose exec -T bot sh -c 'cat > /app/data/expenses.db.new' < "$SRC"
docker compose exec -T bot sh -c 'mv /app/data/expenses.db.new /app/data/expenses.db && rm -f /app/data/bot_state.pickle'
docker compose restart bot
echo "✅ Restored $SRC — bot restarted"
