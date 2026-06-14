#!/bin/bash
# Rollback Script for Rudran AI
# Restores the SQLite databases and uploaded files from a backup archive.

if [ -z "$1" ]; then
    echo "Usage: ./scripts/rollback.sh <path_to_backup.tar.gz>"
    exit 1
fi

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file $BACKUP_FILE not found."
    exit 1
fi

echo "Warning: This will overwrite current production data."
read -p "Are you sure you want to rollback using $BACKUP_FILE? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled."
    exit 1
fi

echo "Stopping services..."
docker-compose down

echo "Restoring from $BACKUP_FILE..."
tar -xzvf $BACKUP_FILE

echo "Restarting services..."
docker-compose up -d

echo "Rollback completed successfully."
