#!/bin/bash
# Backup Script for Rudran AI
# Backs up the SQLite databases and uploaded files.

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="rudran_backup_$TIMESTAMP.tar.gz"

mkdir -p $BACKUP_DIR

echo "Starting Rudran AI backup..."

# We use tar to package the state. In production, we might want to pause the backend to avoid SQLite locking issues.
tar -czvf $BACKUP_DIR/$ARCHIVE_NAME \
    ./backend/agent.db \
    ./backend/agent.db-shm \
    ./backend/agent.db-wal \
    ./backend/memory.db \
    ./backend/memory.db-shm \
    ./backend/memory.db-wal \
    ./backend/uploads \
    ./backend/tools/plugins \
    ./backend/models 2>/dev/null

echo "Backup completed successfully: $BACKUP_DIR/$ARCHIVE_NAME"
