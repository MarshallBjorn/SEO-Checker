#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DUMP_FILE="/tmp/seoauditor-${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting backup"

PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-acl \
    | gzip > "$DUMP_FILE"

DUMP_SIZE=$(stat -c%s "$DUMP_FILE")
echo "[$(date)] Dump created: $DUMP_FILE ($DUMP_SIZE bytes)"

restic snapshots >/dev/null 2>&1 || restic init

restic backup "$DUMP_FILE" --tag daily --host seoauditor

restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 3 --prune

rm -f "$DUMP_FILE"

echo "[$(date)] Backup complete"
