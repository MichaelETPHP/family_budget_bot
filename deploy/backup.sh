#!/usr/bin/env bash
# Safe, consistent backup of the bot's data (SQLite online backup + voice notes).
# Usage:  ./deploy/backup.sh            (keeps the newest 14 backups in ./backups)
# Cron:   0 3 * * * cd /opt/family-budget-bot && ./deploy/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="backups/$STAMP"
mkdir -p "$OUT"

# Online SQLite backup inside the running container (safe while the bot is writing),
# streamed out so no extra files are left in the volume.
docker compose exec -T bot python - > "$OUT/expenses.db" <<'PY'
import sqlite3, sys, tempfile, os
src = sqlite3.connect("/app/data/expenses.db")
fd, tmp = tempfile.mkstemp(dir="/tmp"); os.close(fd)
dst = sqlite3.connect(tmp); src.backup(dst); dst.close(); src.close()
sys.stdout.buffer.write(open(tmp, "rb").read()); os.remove(tmp)
PY

docker compose exec -T bot sh -c 'cd /app/data && [ -d voice_notes ] && tar -cz voice_notes || true' \
  > "$OUT/voice_notes.tar.gz"

ls -1dt backups/*/ 2>/dev/null | tail -n +15 | xargs -r rm -rf
echo "✅ Backup saved to $OUT ($(du -sh "$OUT" | cut -f1))"
