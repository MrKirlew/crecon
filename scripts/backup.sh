#!/bin/bash

# AI Executive Assistant - Backup Script
# Creates backups of PostgreSQL, Qdrant, and N8N configurations

set -e

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in: $BACKUP_DIR"

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
docker-compose exec -T postgres pg_dump -U n8n n8n > "$BACKUP_DIR/postgres_backup.sql"

# Backup Qdrant
echo "Backing up Qdrant..."
docker-compose exec -T qdrant tar -czf - /qdrant/storage > "$BACKUP_DIR/qdrant_backup.tar.gz"

# Backup N8N workflows and credentials
echo "Backing up N8N data..."
docker-compose exec -T n8n tar -czf - /home/node/.n8n > "$BACKUP_DIR/n8n_backup.tar.gz"

# Backup .env (without sensitive values)
echo "Backing up configuration..."
grep -v -E "PASSWORD|SECRET|KEY" .env > "$BACKUP_DIR/env_template.txt" || true

# Create checksum
cd "$BACKUP_DIR"
sha256sum * > checksums.txt

echo "Backup completed: $BACKUP_DIR"
echo "Files:"
ls -lh "$BACKUP_DIR"
