# PostgreSQL Installation & Configuration Guide

Complete guide for installing, configuring, and managing PostgreSQL for WASLA v2 application.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
   - [Ubuntu/Debian](#ubuntudebian)
   - [CentOS/RHEL](#centosrhel)
   - [macOS](#macos)
   - [Windows](#windows)
3. [Post-Installation Setup](#post-installation-setup)
4. [Configuration](#configuration)
5. [Connection Testing](#connection-testing)
6. [Troubleshooting](#troubleshooting)
7. [Security Best Practices](#security-best-practices)
8. [Backup & Recovery](#backup--recovery)
9. [Performance Tuning](#performance-tuning)

---

## Quick Start

### Automatic Installation (Recommended for Linux)

```bash
# Navigate to project root
cd /path/to/wasla-version-2

# Run deployment script with traditional deployment type
DB_SYSTEM=postgresql DEPLOY_TYPE=traditional bash wasla/deploy.sh
```

The script will automatically:
- ✅ Install PostgreSQL 15
- ✅ Create database `wasla`
- ✅ Create user `wasla_user`
- ✅ Set secure password
- ✅ Configure permissions
- ✅ Update `.env` file

---

## Installation

### Ubuntu/Debian

#### Step 1: Update Package Manager

```bash
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
```

#### Step 2: Install PostgreSQL

```bash
# Install PostgreSQL 15 (recommended)
sudo apt-get install -y postgresql postgresql-contrib postgresql-client

# Or install specific version
sudo apt-get install -y postgresql-15 postgresql-contrib-15 postgresql-client-15
```

**Supported Versions:**
- PostgreSQL 15 (Latest, Recommended)
- PostgreSQL 14 (Stable)
- PostgreSQL 13 (LTS)

#### Step 3: Verify Installation

```bash
psql --version
# Output: psql (PostgreSQL) 15.x (Ubuntu 15.x-1.pgdg...)

sudo systemctl status postgresql
# Output: ● postgresql.service - PostgreSQL RDBMS
#            Loaded: loaded (/lib/systemd/system/postgresql.service; enabled; vendor preset: enabled)
#            Active: active (running)
```

#### Step 4: Access PostgreSQL

```bash
# Connect as default postgres user
sudo -u postgres psql

# Inside psql prompt:
postgres=# \l
```

---

### CentOS/RHEL

#### Step 1: Add PostgreSQL Repository

```bash
# CentOS/RHEL 8+
sudo dnf install -y postgresql-server postgresql-contrib postgresql-devel

# CentOS/RHEL 7
sudo yum install -y postgresql-server postgresql-contrib postgresql-devel
```

#### Step 2: Initialize Database

```bash
# For CentOS/RHEL, initialize the database first
sudo postgresql-setup initdb

# Then start the service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Step 3: Verify Installation

```bash
sudo -u postgres psql --version
# Output: psql (PostgreSQL) 15.x, compiled by ...

sudo systemctl status postgresql
# Output: ● postgresql.service - PostgreSQL database server
#            Loaded: loaded (/usr/lib/systemd/system/postgresql.service; enabled; vendor preset: disabled)
#            Active: active (running)
```

---

### macOS

#### Using Homebrew (Recommended)

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install PostgreSQL
brew install postgresql@15

# Start PostgreSQL
brew services start postgresql@15

# Verify installation
psql --version

# Create default database and user
createdb
```

#### Using DMG Installer

1. Download from: https://www.postgresql.org/download/macosx/
2. Choose PostgreSQL 15
3. Download DMG installer (EnterpriseDB)
4. Run installer and follow prompts:
   - Choose installation directory
   - Set data directory
   - Set superuser password
   - Choose service port (default: 5432)
   - Setup Windows service (if on Windows)
5. Start PostgreSQL:
   ```bash
   sudo /Library/PostgreSQL/15/bin/pg_ctl -D /Library/PostgreSQL/15/data -l logfile start
   ```

---

### Windows

#### Using PostgreSQL Installer

1. Download from: https://www.postgresql.org/download/windows/
2. Choose PostgreSQL 15
3. Download EXE installer
4. Run installer as Administrator
5. Follow setup wizard:
   - Choose installation directory
   - Select components (PostgreSQL Server, pgAdmin, Command Line Tools)
   - Set data directory location
   - Set superuser (postgres) password
   - Choose port (default: 5432)
   - Choose locale (UTF-8 recommended)
   - Complete installation and launch Stack Builder (optional)

#### Using Chocolatey

```powershell
# Install Chocolatey if not already installed
# Then:

choco install postgresql15

# Start PostgreSQL
# PostgreSQL is installed as a Windows Service and should start automatically

# Verify
psql --version
```

---

## Post-Installation Setup

### Step 1: Connect as Superuser

```bash
# Ubuntu/Debian/macOS/CentOS/RHEL
sudo -u postgres psql

# Windows (using Windows password authentication)
# Use pgAdmin GUI or
psql -U postgres
```

### Step 2: Create WASLA Database

```sql
CREATE DATABASE wasla WITH ENCODING 'UTF8' LOCALE 'C.UTF-8';
```

### Step 3: Create Application User

```sql
-- Drop user if exists (first time setup)
DROP USER IF EXISTS wasla_user;

-- Create user with secure password
CREATE USER wasla_user WITH PASSWORD 'strong-random-password-here';

-- Grant connection privileges
ALTER ROLE wasla_user CREATEDB;
ALTER ROLE wasla_user WITH LOGIN;
```

### Step 4: Grant Database Privileges

```sql
-- Grant all privileges on wasla database
GRANT ALL PRIVILEGES ON DATABASE wasla TO wasla_user;

-- Connect to the database
\c wasla

-- Grant schema privileges
GRANT ALL PRIVILEGES ON SCHEMA public TO wasla_user;

-- Grant table privileges (for existing tables)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO wasla_user;

-- Grant sequence privileges (for auto-increment IDs)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO wasla_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO wasla_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO wasla_user;
```

### Step 5: Verify Setup

```sql
-- List all databases
\l

-- List all users/roles
\du

-- Connect to wasla database
\c wasla

-- List tables (should be empty initially)
\dt

-- Create test table
CREATE TABLE test (
  id SERIAL PRIMARY KEY,
  message VARCHAR(255)
);

-- Insert test data
INSERT INTO test (message) VALUES ('PostgreSQL is working!');

-- Select data
SELECT * FROM test;

-- Drop test table
DROP TABLE test;

-- Exit
\q
```

---

## Configuration

### PostgreSQL Configuration Files

**Location:**
- Ubuntu/Debian: `/etc/postgresql/15/main/`
- CentOS/RHEL: `/var/lib/pgsql/15/data/`
- macOS (Homebrew): `/usr/local/var/postgres/`
- macOS (DMG): `/Library/PostgreSQL/15/data/`
- Windows: `C:\Program Files\PostgreSQL\15\data\`

### Key Configuration Files

#### postgresql.conf
Controls PostgreSQL server behavior and performance:

```bash
# View current configuration
sudo -u postgres psql -c "SELECT name, setting FROM pg_settings WHERE name LIKE '%listen_address%';"

# Edit configuration
sudo nano /etc/postgresql/15/main/postgresql.conf
```

#### pg_hba.conf
Controls client authentication:

```bash
# Edit authentication method
sudo nano /etc/postgresql/15/main/pg_hba.conf
```

### Recommended Configuration for Django

#### postgresql.conf

```ini
# Connection Settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 10MB
maintenance_work_mem = 64MB

# WAL (Write-Ahead Logging) Settings
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB

# Checkpoint Settings
checkpoint_completion_target = 0.9
wal_level = replica
max_wal_senders = 3
wal_keep_size = 1GB

# Logging
log_destination = 'stderr'
log_min_messages = notice
log_min_duration_statement = 1000  # Log queries taking > 1 second
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '

# Locale
datestyle = 'iso, mdy'
timezone = 'UTC'
lc_messages = 'C.UTF-8'
lc_monetary = 'C.UTF-8'
lc_numeric = 'C.UTF-8'
lc_time = 'C.UTF-8'
```

#### pg_hba.conf

```ini
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# IPv4 local connections
host    all             all             127.0.0.1/32            md5
host    wasla           wasla_user      127.0.0.1/32            md5

# IPv6 local connections
host    all             all             ::1/128                 md5

# Unix socket connections
local   all             postgres                                peer
local   all             all                                     peer

# Remote connections (if needed)
host    all             all             0.0.0.0/0               md5
```

### Apply Configuration Changes

```bash
# Edit configuration
sudo nano /etc/postgresql/15/main/postgresql.conf

# Reload configuration without restart
sudo -u postgres psql -c "SELECT pg_reload_conf();"

# Or restart PostgreSQL
sudo systemctl restart postgresql

# Verify settings
sudo -u postgres psql -c "SELECT name, setting FROM pg_settings WHERE name = 'max_connections';"
```

---

## Connection Testing

### Django Connection

#### 1. Test via Django

```bash
# From project root
cd /path/to/wasla-version-2

# Activate virtual environment
source .venv/bin/activate

# Test database connection
python manage.py dbshell

# Inside PostgreSQL shell:
SELECT 1 as test;
\q
```

#### 2. Test via Python

```bash
python3 << 'EOF'
import psycopg2

try:
    connection = psycopg2.connect(
        host='localhost',
        user='wasla_user',
        password='your-password',
        database='wasla'
    )
    cursor = connection.cursor()
    cursor.execute("SELECT 1 as test")
    result = cursor.fetchone()
    print(f"✅ PostgreSQL Connection Test Passed: {result}")
    cursor.close()
    connection.close()
except psycopg2.Error as e:
    print(f"❌ PostgreSQL Connection Failed: {e}")
EOF
```

#### 3. Direct PostgreSQL Connection

```bash
# Using psql command-line
psql -h localhost -U wasla_user -d wasla

# When prompted, enter password:
# your-password

# Inside PostgreSQL:
SELECT version();
SELECT current_database();
\q
```

### Docker Connection

```bash
# If using Docker Compose
docker-compose exec db psql -U wasla_user -d wasla

# Inside PostgreSQL:
SELECT VERSION();
\q
```

---

## Troubleshooting

### PostgreSQL Service Won't Start

```bash
# Check service status
sudo systemctl status postgresql

# View error logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log

# Check for disk space issues
df -h

# Check for conflicting processes
sudo lsof -i :5432

# Restart service
sudo systemctl restart postgresql

# If still failing, check PostgreSQL logs
sudo -u postgres psql -c "SELECT * FROM pg_settings WHERE name = 'log_directory';"
```

### Connection Refused Error

```bash
# Verify PostgreSQL is running
sudo systemctl status postgresql

# Check if PostgreSQL is listening on port 5432
sudo netstat -tlnp | grep postgres
# Or use ss command (newer systems)
sudo ss -tlnp | grep postgres

# Check listen_address setting
sudo -u postgres psql -c "SHOW listen_addresses;"

# Should output: localhost,::1 (or 127.0.0.1)
# For remote connections, set to: '*'
```

### Authentication Failed

```bash
# Check pg_hba.conf for authentication method
sudo cat /etc/postgresql/15/main/pg_hba.conf

# Change authentication method
sudo nano /etc/postgresql/15/main/pg_hba.conf

# After changes, reload configuration
sudo -u postgres psql -c "SELECT pg_reload_conf();"

# Reset superuser password if forgotten
sudo -u postgres psql
ALTER USER postgres WITH PASSWORD 'new-password';
FLUSH PRIVILEGES;
\q
```

### Database Not Found

```bash
# List all databases
sudo -u postgres psql -l

# If 'wasla' database doesn't exist, create it
sudo -u postgres psql

CREATE DATABASE wasla WITH ENCODING 'UTF8' LOCALE 'C.UTF-8';
GRANT ALL PRIVILEGES ON DATABASE wasla TO wasla_user;
\q
```

### Permission Denied for User

```bash
# Check user privileges
sudo -u postgres psql -c "SELECT * FROM information_schema.table_privileges WHERE grantee='wasla_user' LIMIT 5;"

# Grant all privileges on database
sudo -u postgres psql
GRANT ALL PRIVILEGES ON DATABASE wasla TO wasla_user;

# Grant schema privileges
\c wasla
GRANT ALL PRIVILEGES ON SCHEMA public TO wasla_user;

# Grant all table privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO wasla_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO wasla_user;
\q
```

### Encoding Issues

```bash
# Check database encoding
sudo -u postgres psql -l

# Create database with proper encoding
CREATE DATABASE wasla WITH ENCODING 'UTF8' LOCALE 'C.UTF-8' TEMPLATE=template0;

# Check table encoding
\d+ table_name

# Check server encoding
SHOW server_encoding;
SHOW client_encoding;
```

---

## Security Best Practices

### 1. Strong Passwords

```bash
# Generate secure random password (64 characters)
openssl rand -base64 32

# Example:
# a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

### 2. Least Privilege Principle

```sql
-- Instead of GRANT ALL, grant only needed privileges
GRANT USAGE ON SCHEMA public TO wasla_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO wasla_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO wasla_user;

-- For specific tables only
GRANT SELECT, INSERT, UPDATE ON wasla.orders TO wasla_user;
```

### 3. Limit Network Access

```bash
# Only allow local connections
edit /etc/postgresql/15/main/postgresql.conf
# Set: listen_addresses = 'localhost'

# Reload configuration
sudo -u postgres psql -c "SELECT pg_reload_conf();"
```

### 4. Disable Unnecessary Superuser Privileges

```sql
-- Create application user without superuser privileges
DROP ROLE IF EXISTS wasla_user;

CREATE ROLE wasla_user WITH LOGIN PASSWORD 'secure-password';
GRANT USAGE ON SCHEMA public TO wasla_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO wasla_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO wasla_user;
```

### 5. Regular Updates

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get upgrade postgresql-15

# CentOS/RHEL
sudo yum update postgresql15-server

# Restart after update
sudo systemctl restart postgresql
```

### 6. Backup & Recovery

```bash
# Regular automated backups (see Backup section below)
# Keep encrypted backups in secure location
# Test restore procedures regularly
```

### 7. Monitor User Activities

```sql
-- Enable logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = on;
SELECT pg_reload_conf();

-- Check logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

---

## Backup & Recovery

### Manual Backup

#### Single Database

```bash
# Backup one database to SQL file
pg_dump -U wasla_user -d wasla > wasla_backup.sql

# Backup with date timestamp
pg_dump -U wasla_user -d wasla > wasla_backup_$(date +%Y%m%d_%H%M%S).sql

# Custom format (more compact)
pg_dump -U wasla_user -d wasla -F c > wasla_backup.dump
```

#### All Databases

```bash
# Backup all databases
pg_dumpall -U postgres > all_databases_backup.sql

# Exclude postgres, template0, template1
pg_dump -U postgres wasla > wasla_backup.sql
pg_dump -U postgres other_db > other_db_backup.sql
```

#### Compressed Backup (Recommended for Large Databases)

```bash
# Single database with gzip compression
pg_dump -U wasla_user -d wasla | gzip > wasla_backup.sql.gz

# All data with compression
pg_dumpall -U postgres | gzip > all_databases_backup.sql.gz

# Custom format (better compression)
pg_dump -U wasla_user -d wasla -F c -Z 9 > wasla_backup.dump.gz

# Verify backup file size
ls -lh wasla_backup.sql.gz
```

### Restore from Backup

#### Single Database

```bash
# Restore from SQL backup
psql -U wasla_user -d wasla < wasla_backup.sql

# From compressed backup
zcat wasla_backup.sql.gz | psql -U wasla_user -d wasla

# From custom format backup
pg_restore -U wasla_user -d wasla wasla_backup.dump
```

#### All Databases

```bash
# Restore all databases from backup
psql -U postgres < all_databases_backup.sql

# From compressed backup
zcat all_databases_backup.sql.gz | psql -U postgres

# Restore with verbose output
psql -U postgres -v ON_ERROR_STOP=1 < all_databases_backup.sql
```

### Automated Backup (Cron Job)

```bash
# Create backup script
cat > /home/user/backup_postgresql.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/home/user/postgresql_backups"
PG_USER="wasla_user"
PG_DB="wasla"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U $PG_USER -d $PG_DB | gzip > $BACKUP_DIR/wasla_$DATE.sql.gz

# Keep only last 7 days of backups
find $BACKUP_DIR -name "wasla_*.sql.gz" -mtime +7 -delete

echo "Backup completed: wasla_$DATE.sql.gz"
EOF

chmod +x /home/user/backup_postgresql.sh

# Add to crontab for daily 2 AM backup
crontab -e

# Add line:
# 0 2 * * * /home/user/backup_postgresql.sh
```

### Backup Verification

```bash
# List backups
ls -lh /path/to/backups/

# Check backup integrity
gunzip -t wasla_backup.sql.gz

# Verify backup contents
zcat wasla_backup.sql.gz | head -50

# Test restore to temporary database
psql -U postgres -c "CREATE DATABASE wasla_test;"
zcat wasla_backup.sql.gz | psql -U postgres -d wasla_test

# Drop test database
psql -U postgres -c "DROP DATABASE wasla_test;"
```

---

## Performance Tuning

### Monitor Database Performance

```sql
-- Show active connections
SELECT pid, usename, application_name, state FROM pg_stat_activity;

-- Show long-running queries
SELECT pid, usename, pg_stat_statements.query, pg_stat_statements.mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;

-- Show table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Show index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### Create Indexes for Performance

```sql
-- Create index on frequently queried columns
CREATE INDEX CONCURRENTLY idx_orders_user ON orders(user_id);
CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);
CREATE INDEX CONCURRENTLY idx_orders_created ON orders(created_at);

-- Create composite index
CREATE INDEX CONCURRENTLY idx_orders_user_status ON orders(user_id, status);

-- List all indexes
\di

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan FROM pg_stat_user_indexes;
```

### VACUUM and ANALYZE

```sql
-- Reclaim disk space and update statistics
VACUUM ANALYZE;

-- For specific table
VACUUM ANALYZE orders;

-- Show last analyzed time
SELECT schemaname, tablename, last_vacuum, last_analyze 
FROM pg_stat_user_tables;
```

### Auto VACUUM Configuration

```sql
-- Current autovacuum settings
SHOW autovacuum;
SHOW autovacuum_vacuum_threshold;
SHOW autovacuum_analyze_threshold;

-- Enable autovacuum
ALTER DATABASE wasla SET autovacuum = on;
```

---

## Common Django Database Operations

### Initialize Database

```bash
# Apply all migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations

# Create migration history (if missing)
python manage.py migrate --run-syncdb
```

### Create Migrations

```bash
# Create new migrations
python manage.py makemigrations

# Show migration SQL
python manage.py sqlmigrate app_name 0001

# Dry run (don't apply)
python manage.py migrate --plan
```

### Create Superuser

```bash
python manage.py createsuperuser

# Interactive prompts for:
# - Username
# - Email
# - Password
```

### Load/Dump Data

```bash
# Export data as JSON
python manage.py dumpdata > data.json

# Export specific app
python manage.py dumpdata app_name > app_data.json

# Load data from JSON
python manage.py loaddata data.json
```

### Database Shell

```bash
# Open interactive PostgreSQL shell via Django
python manage.py dbshell

# Inside PostgreSQL:
\dt  -- Show tables
SELECT COUNT(*) FROM django_migrations;
\q  -- Exit
```

---

## Environment Variables

### .env File Configuration

```bash
# PostgreSQL specific variables
DJANGO_DB_DEFAULT=postgresql
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wasla
DB_USER=wasla_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=5432
```

---

## Useful psql Commands

```bash
\l              -- List all databases
\du             -- List all users/roles
\c database     -- Connect to database
\dt             -- List tables in current database
\d table_name   -- Show table structure
\di             -- List all indexes
\ds             -- List all sequences
\dn             -- List all schemas
\x              -- Toggle expanded output
\timing         -- Toggle query timing
\q              -- Quit psql

-- SQL Commands:
SELECT version();                    -- Show PostgreSQL version
SELECT current_database();           -- Show current database
SELECT current_user;                 -- Show current user
SELECT NOW();                        -- Show current timestamp
```

---

## Support & Resources

- **PostgreSQL Official Documentation**: https://www.postgresql.org/docs/15/
- **Django PostgreSQL Backend**: https://docs.djangoproject.com/en/stable/ref/databases/#postgresql-notes
- **PostgreSQL Tutorial**: https://www.postgresql.org/docs/15/tutorial.html
- **Performance Tuning**: https://www.postgresql.org/docs/15/runtime-config.html
- **Backup & Recovery**: https://www.postgresql.org/docs/15/backup.html

---

**Last Updated:** February 17, 2026
**PostgreSQL Version:** 15
**Django Version:** 6.0+
