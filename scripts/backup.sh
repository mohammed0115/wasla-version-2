#!/bin/bash

###############################################################################
# Wasla Platform - Database & Media Backup Script
#
# Purpose: Automate daily database and media backups with retention policy
# 
# Usage:
#   ./backup.sh              # Run full backup (db + media)
#   ./backup.sh --db-only    # Database only
#   ./backup.sh --media-only # Media only
#   ./backup.sh --restore <backup_file.sql.gz>  # Restore from backup
#
# Setup:
#   1. Place script in /opt/wasla/scripts/
#   2. chmod +x backup.sh
#   3. Add to crontab: 0 2 * * * /opt/wasla/scripts/backup.sh > /var/log/wasla/backup.log 2>&1
#   4. Create backup directory: mkdir -p /mnt/backups/wasla
#   5. Create log directory: mkdir -p /var/log/wasla
###############################################################################

set -euo pipefail

# ==========================================
# CONFIGURATION
# ==========================================

# Database connection
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-wasla_prod}"
DB_USER="${DB_USER:-wasla_user}"
DB_PASSWORD="${DB_PASSWORD:-/run/secrets/db_password}"

# Paths
BACKUP_DIR="${BACKUP_DIR:-/mnt/backups/wasla}"
LOG_DIR="${LOG_DIR:-/var/log/wasla}"
MEDIA_DIR="${MEDIA_DIR:-/opt/wasla/media}"
BACKUP_RETENTION_DAYS=30  # Keep backups for 30 days

# Timestamps
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DATE=$(date +%Y-%m-%d)

# Log file
LOG_FILE="${LOG_DIR}/backup_${BACKUP_DATE}.log"

# ==========================================
# FUNCTIONS
# ==========================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[ERROR] $*" | tee -a "$LOG_FILE"
    exit 1
}

backup_database() {
    log "Starting database backup..."
    
    DB_BACKUP_FILE="${BACKUP_DIR}/wasla_db_${TIMESTAMP}.sql.gz"
    
    # Export password for pg_dump
    export PGPASSWORD="$(cat "$DB_PASSWORD")"
    
    # Dump database with compression
    # --verbose: Show progress
    # --format=plain: SQL format (not binary)
    # --no-privileges: Exclude privilege statements
    # --no-owner: Exclude owner statements
    pg_dump \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        --database="$DB_NAME" \
        --verbose \
        --format=plain \
        --no-privileges \
        --no-owner \
        | gzip > "$DB_BACKUP_FILE"
    
    unset PGPASSWORD
    
    # Verify backup
    if [ ! -f "$DB_BACKUP_FILE" ]; then
        error "Database backup file not created: $DB_BACKUP_FILE"
    fi
    
    DB_SIZE=$(du -sh "$DB_BACKUP_FILE" | cut -f1)
    log "Database backup completed: $DB_BACKUP_FILE ($DB_SIZE)"
}

backup_media() {
    log "Starting media backup..."
    
    MEDIA_BACKUP_FILE="${BACKUP_DIR}/wasla_media_${TIMESTAMP}.tar.gz"
    
    # Check if media directory exists
    if [ ! -d "$MEDIA_DIR" ]; then
        log "Media directory not found: $MEDIA_DIR (skipping)"
        return
    fi
    
    # Tar and compress media files
    tar --gzip \
        --create \
        --file="$MEDIA_BACKUP_FILE" \
        --directory="$(dirname "$MEDIA_DIR")" \
        "$(basename "$MEDIA_DIR")" \
        2>/dev/null || true
    
    if [ ! -f "$MEDIA_BACKUP_FILE" ]; then
        error "Media backup file not created: $MEDIA_BACKUP_FILE"
    fi
    
    MEDIA_SIZE=$(du -sh "$MEDIA_BACKUP_FILE" | cut -f1)
    log "Media backup completed: $MEDIA_BACKUP_FILE ($MEDIA_SIZE)"
}

cleanup_old_backups() {
    log "Cleaning up backups older than ${BACKUP_RETENTION_DAYS} days..."
    
    find "$BACKUP_DIR" -type f -name "wasla_*" -mtime +"$BACKUP_RETENTION_DAYS" -delete
    
    log "Cleanup completed"
}

restore_database() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        error "Backup file not found: $backup_file"
    fi
    
    log "Starting database restore from: $backup_file"
    log "WARNING: This will drop and recreate the database!"
    read -p "Continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "Restore cancelled"
        exit 0
    fi
    
    export PGPASSWORD="$(cat "$DB_PASSWORD")"
    
    # Drop existing database
    log "Dropping existing database: $DB_NAME"
    dropdb \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        "$DB_NAME" || log "Database doesn't exist (ok)"
    
    # Create new database
    log "Creating new database: $DB_NAME"
    createdb \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        "$DB_NAME"
    
    # Restore dump
    log "Restoring database dump..."
    gunzip -c "$backup_file" | psql \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        --database="$DB_NAME"
    
    unset PGPASSWORD
    
    log "Database restore completed"
}

show_backup_list() {
    log "Backups in ${BACKUP_DIR}:"
    ls -lh "$BACKUP_DIR"/wasla_* | tail -20
}

generate_backup_summary() {
    log "======================================"
    log "Backup Summary"
    log "======================================"
    log "Backup Date: $(date)"
    log "Database Host: $DB_HOST"
    log "Database Name: $DB_NAME"
    log "Media Directory: $MEDIA_DIR"
    log "Backup Directory: $BACKUP_DIR"
    log "Retention Policy: $BACKUP_RETENTION_DAYS days"
    log ""
    show_backup_list
    log "======================================"
}

# ==========================================
# MAIN
# ==========================================

# Ensure directories exist
mkdir -p "$BACKUP_DIR" "$LOG_DIR"

log "======================================"
log "Wasla Backup Script Started"
log "======================================"

# Parse arguments
BACKUP_TYPE="full"
if [ $# -gt 0 ]; then
    case "$1" in
        --db-only)
            BACKUP_TYPE="db_only"
            ;;
        --media-only)
            BACKUP_TYPE="media_only"
            ;;
        --restore)
            if [ $# -lt 2 ]; then
                error "Usage: $0 --restore <backup_file.sql.gz>"
            fi
            restore_database "$2"
            exit 0
            ;;
        --list)
            show_backup_list
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
fi

# Execute backups based on type
case "$BACKUP_TYPE" in
    full)
        backup_database
        backup_media
        ;;
    db_only)
        backup_database
        ;;
    media_only)
        backup_media
        ;;
esac

# Cleanup old backups
cleanup_old_backups

# Generate summary
generate_backup_summary

log "Backup completed successfully"

# ==========================================
# RESTORATION PROCEDURE (MANUAL)
# ==========================================
# 
# 1. Restore database:
#    ./backup.sh --restore /mnt/backups/wasla/wasla_db_20260228_020000.sql.gz
#
# 2. Restore media:
#    tar --gzip --extract --file=/mnt/backups/wasla/wasla_media_20260228_020000.tar.gz -C /
#
# 3. Verify restore:
#    python manage.py migrate
#    python manage.py check
#
# 4. Start application:
#    docker-compose restart
#

# ==========================================
# DISASTER RECOVERY TARGETS
# ==========================================
#
# RTO (Recovery Time Objective): 1 hour
# - Database restoration: ~15 minutes (depending on size)
# - Media restoration: ~5 minutes
# - Application start: ~5 minutes
# - Testing: ~35 minutes
#
# RPO (Recovery Point Objective): 24 hours
# - Backups run daily at 2 AM
# - Maximum data loss: 24 hours of transactions
#
# To improve RPO:
# 1. Use AWS RDS automated backups (continuous)
# 2. Enable WAL archiving to S3
# 3. Set up streaming replication to standby

exit 0
