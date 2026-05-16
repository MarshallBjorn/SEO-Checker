#!/bin/bash
# Usage: ./restore.sh [snapshot_id]   (default: latest)
# Restores into ${DB_NAME}_restore database — never touches production DB.
set -euo pipefail

SNAPSHOT="${1:-latest}"
TARGET_DB="${DB_NAME}_restore"

echo "Restoring snapshot: $SNAPSHOT -> $TARGET_DB"

rm -rf /tmp/restore && mkdir -p /tmp/restore
restic restore "$SNAPSHOT" --target /tmp/restore

DUMP=$(find /tmp/restore -name "seoauditor-*.sql.gz" | head -1)
[ -z "$DUMP" ] && { echo "No dump in snapshot"; exit 1; }
echo "Found dump: $DUMP"

PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS ${TARGET_DB};"
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres \
    -c "CREATE DATABASE ${TARGET_DB};"

gunzip -c "$DUMP" | PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" -U "$DB_USER" -d "${TARGET_DB}"

echo "Restored into ${TARGET_DB}. Swap manually if all good:"
echo "  ALTER DATABASE ${DB_NAME} RENAME TO ${DB_NAME}_old;"
echo "  ALTER DATABASE ${TARGET_DB} RENAME TO ${DB_NAME};"
