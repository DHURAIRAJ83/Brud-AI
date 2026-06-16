#!/bin/bash
# Backup Script for Rudran AI
# Backs up the SQLite databases and uploaded files.

# Support running inside or outside container
if [ -d "/app/data" ]; then
    DATA_DIR="/app/data"
    UPLOADS_DIR="/app/uploads"
    PLUGINS_DIR="/app/tools/plugins"
    MODELS_DIR="/app/models"
    BACKUP_DIR="/app/backups"
else
    DATA_DIR="./backend"
    UPLOADS_DIR="./backend/uploads"
    PLUGINS_DIR="./backend/tools/plugins"
    MODELS_DIR="./backend/models"
    BACKUP_DIR="./backups"
fi

mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="rudran_backup_$TIMESTAMP.tar.gz"

echo "Starting Rudran AI backup at $TIMESTAMP..."

# Safely backup SQLite databases using native backup command if sqlite3 is available
TMP_DB_DIR=$(mktemp -d)

if command -v sqlite3 &> /dev/null; then
    echo "Using native sqlite3 backup..."
    [ -f "$DATA_DIR/agent.db" ] && sqlite3 "$DATA_DIR/agent.db" ".backup '$TMP_DB_DIR/agent.db'"
    [ -f "$DATA_DIR/memory.db" ] && sqlite3 "$DATA_DIR/memory.db" ".backup '$TMP_DB_DIR/memory.db'"
else
    echo "sqlite3 not found, copying raw database files (may be inconsistent)..."
    cp -r "$DATA_DIR"/*.db* "$TMP_DB_DIR/" 2>/dev/null || true
fi

# Package state
tar -czvf $BACKUP_DIR/$ARCHIVE_NAME \
    -C $TMP_DB_DIR . \
    -C $(dirname $UPLOADS_DIR) $(basename $UPLOADS_DIR) \
    -C $(dirname $PLUGINS_DIR) $(basename $PLUGINS_DIR) \
    -C $(dirname $MODELS_DIR) $(basename $MODELS_DIR) 2>/dev/null

rm -rf $TMP_DB_DIR

echo "Backup completed successfully: $BACKUP_DIR/$ARCHIVE_NAME"

# Prune backups older than 7 days
echo "Pruning backups older than 7 days..."
find $BACKUP_DIR -name "rudran_backup_*.tar.gz" -type f -mtime +7 -exec rm {} \;

echo "Backup and pruning complete."
