#!/bin/bash

# AI Executive Assistant - Restore Script
# Restores from backup directory

set -e

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_directory>"
    echo "Available backups:"
    ls -d ./backups/*/ 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_DIR=$1

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo "Restoring from: $BACKUP_DIR"

# Verify checksums
if [ -f "$BACKUP_DIR/checksums.txt" ]; then
    echo "Verifying checksums..."
    cd "$BACKUP_DIR"
    sha256sum -c checksums.txt || {
        echo "Checksum verification failed!"
        exit 1
    }
    cd - > /dev/null
fi

read -p "This will overwrite current data. Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Restore PostgreSQL
if [ -f "$BACKUP_DIR/postgres_backup.sql" ]; then
    echo "Restoring PostgreSQL..."
    docker-compose exec -T postgres psql -U n8n -d n8n -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    cat "$BACKUP_DIR/postgres_backup.sql" | docker-compose exec -T postgres psql -U n8n n8n
fi

# Restore Qdrant
if [ -f "$BACKUP_DIR/qdrant_backup.tar.gz" ]; then
    echo "Restoring Qdrant..."
    docker-compose stop qdrant
    docker-compose run --rm -v qdrant_storage:/qdrant/storage --entrypoint /bin/sh qdrant -c "rm -rf /qdrant/storage/*"
    cat "$BACKUP_DIR/qdrant_backup.tar.gz" | docker-compose run --rm -T -v qdrant_storage:/restore qdrant tar -xzf - -C /
    docker-compose start qdrant
fi

# Restore N8N
if [ -f "$BACKUP_DIR/n8n_backup.tar.gz" ]; then
    echo "Restoring N8N..."
    docker-compose stop n8n
    docker-compose run --rm -v n8n_data:/home/node/.n8n --entrypoint /bin/sh n8n -c "rm -rf /home/node/.n8n/*"
    cat "$BACKUP_DIR/n8n_backup.tar.gz" | docker-compose run --rm -T -v n8n_data:/restore n8n tar -xzf - -C /
    docker-compose start n8n
fi

echo "Restore completed!"
echo "Restarting services..."
docker-compose restart

echo "Done!"
