#!/bin/bash

# Backup directory
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Backup database
pg_dump pickleball > $BACKUP_DIR/db_backup_$DATE.sql

# Backup uploaded files
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /home/ubuntu/pickleball/uploads

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete 