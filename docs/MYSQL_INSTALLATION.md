# MySQL Installation & Configuration Guide

Complete guide for installing, configuring, and managing MySQL for WASLA v2 application.

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

---

## Quick Start

### Automatic Installation (Recommended for Linux)

```bash
# Navigate to project root
cd /path/to/wasla-version-2

# Run deployment script with traditional deployment type
DEPLOY_TYPE=traditional bash wasla/deploy.sh
```

The script will automatically:
- ✅ Install MySQL Server 8.0
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

#### Step 2: Install MySQL Server

```bash
# Install MySQL 8.0
sudo apt-get install -y mysql-server mysql-client mysql-workbench

# Or install latest version
sudo apt-get install -y mysql-server
```

**Supported Versions:**
- MySQL 8.0 (Recommended)
- MySQL 5.7 (Legacy support)

#### Step 3: Verify Installation

```bash
mysql --version
# Output: mysql  Ver 8.0.x for Linux on x86_64

sudo systemctl status mysql
# Output: ● mysql.service - MySQL Community Server
#            Loaded: loaded (/lib/systemd/system/mysql.service; enabled; vendor preset: enabled)
#            Active: active (running)
```

#### Step 4: Run Security Script (Optional but Recommended)

```bash
sudo mysql_secure_installation

# Prompts:
# - Enter root password
# - Remove anonymous users? → Y
# - Disable remote root login? → Y
# - Remove test database? → Y
# - Reload privilege tables? → Y
```

---

### CentOS/RHEL

#### Step 1: Add MySQL Repository

```bash
# CentOS/RHEL 8+
sudo dnf install mysql-server

# CentOS/RHEL 7
sudo yum install mysql-server
```

#### Step 2: Start MySQL Service

```bash
sudo systemctl start mysqld
sudo systemctl enable mysqld

# Verify
sudo systemctl status mysqld
```

#### Step 3: Get Temporary Root Password

```bash
# Find the temporary password in the log file
sudo grep 'temporary password' /var/log/mysqld.log
# Output: 2024-01-15T10:23:45.123456Z 6 [Note] [MY-010454] [Server] A temporary password is generated for root@localhost: #qwH>X!9aZ@y
```

#### Step 4: Reset Root Password

```bash
mysql -u root -p
# Enter the temporary password found above

# Inside MySQL:
ALTER USER 'root'@'localhost' IDENTIFIED BY 'your-strong-password';
FLUSH PRIVILEGES;
EXIT;
```

---

### macOS

#### Using Homebrew (Recommended)

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install MySQL
brew install mysql

# Start MySQL
brew services start mysql

# Verify installation
mysql --version

# Run security script
mysql_secure_installation
```

#### Using DMG Installer

1. Download from: https://dev.mysql.com/downloads/mysql/
2. Choose macOS platform
3. Download DMG installer
4. Run installer and follow prompts
5. Start MySQL:
   ```bash
   sudo launchctl start com.oracle.oss.mysql.mysqld
   ```

---

### Windows

#### Using MSI Installer

1. Download from: https://dev.mysql.com/downloads/mysql/
2. Choose Windows platform
3. Download MSI installer
4. Run installer as Administrator
5. Follow setup wizard:
   - Choose setup type (Developer Default, Server only, etc.)
   - Configure MySQL Server (port 3306)
   - Set root password
   - Configure Windows service
6. Enable MySQL service to auto-start

#### Using Chocolatey

```powershell
# Install Chocolatey if not already installed
# Then:

choco install mysql

# Start MySQL
mysql.server start

# Verify
mysql --version
```

---

## Post-Installation Setup

### Step 1: Connect as Root

```bash
# Ubuntu/Debian/macOS/CentOS/RHEL
sudo mysql

# Windows (if password set)
# Use MySQL Command Line Client from Start Menu
# Or use MySQL Workbench GUI
```

### Step 2: Create WASLA Database

```sql
CREATE DATABASE `wasla` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Step 3: Create Application User

```sql
-- Drop user if exists (first time setup)
DROP USER IF EXISTS 'wasla_user'@'localhost';

-- Create user with secure password
CREATE USER 'wasla_user'@'localhost' IDENTIFIED BY 'strong-random-password-here';

-- Grant all privileges on wasla database
GRANT ALL PRIVILEGES ON `wasla`.* TO 'wasla_user'@'localhost';

-- Reload privileges
FLUSH PRIVILEGES;

-- Verify user creation
SELECT USER, HOST FROM mysql.user WHERE USER='wasla_user';
```

### Step 4: Create Remote Access User (Optional, for production)

```sql
-- For Docker or remote connections
CREATE USER 'wasla_user'@'%' IDENTIFIED BY 'strong-random-password-here';
GRANT ALL PRIVILEGES ON `wasla`.* TO 'wasla_user'@'%';
FLUSH PRIVILEGES;
```

### Step 5: Verify Setup

```sql
-- Connect as wasla_user
USE wasla;

-- Create test table
CREATE TABLE `test` (
  id INT AUTO_INCREMENT PRIMARY KEY,
  message VARCHAR(255)
);

-- Insert test data
INSERT INTO `test` (message) VALUES ('MySQL is working!');

-- Select data
SELECT * FROM test;

-- Drop test table
DROP TABLE test;
```

---

## Configuration

### MySQL Configuration File

**Location:**
- Ubuntu/Debian: `/etc/mysql/mysql.conf.d/mysqld.cnf`
- CentOS/RHEL: `/etc/my.cnf`
- macOS: `/usr/local/etc/my.cnf` (Homebrew)
- Windows: `C:\ProgramData\MySQL\MySQL Server 8.0\my.ini`

### Recommended Configuration for Django

```ini
[mysqld]
# Basic Settings
default-storage-engine=InnoDB
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
max_connections=100
wait_timeout=28800
max_allowed_packet=64M

# Performance Settings
innodb_buffer_pool_size=1G
innodb_log_file_size=256M
innodb_flush_logs_at_trx_commit=2

# Logging
log_error=/var/log/mysql/error.log
slow_query_log=1
slow_query_log_file=/var/log/mysql/slow.log
long_query_time=2

# Charset
[mysql]
default-character-set=utf8mb4

[mysqldump]
default-character-set=utf8mb4
```

### Apply Configuration Changes

```bash
# Edit configuration file
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf

# Restart MySQL to apply changes
sudo systemctl restart mysql

# Verify settings
mysql -u root -p -e "SHOW VARIABLES LIKE '%character%';"
mysql -u root -p -e "SHOW VARIABLES LIKE '%collation%';"
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

# Inside MySQL shell:
SELECT 1;
\q
```

#### 2. Test via Python

```bash
python3 << 'EOF'
import MySQLdb

try:
    connection = MySQLdb.connect(
        host='localhost',
        user='wasla_user',
        passwd='your-password',
        db='wasla'
    )
    cursor = connection.cursor()
    cursor.execute("SELECT 1 as test")
    result = cursor.fetchone()
    print(f"✅ MySQL Connection Test Passed: {result}")
    cursor.close()
    connection.close()
except MySQLdb.Error as e:
    print(f"❌ MySQL Connection Failed: {e}")
EOF
```

#### 3. Direct MySQL Connection

```bash
# Local connection (no password)
sudo mysql -u wasla_user -p wasla

# Prompt for password, enter:
# your-password

# OR with password inline (not recommended for production)
mysql -h localhost -u wasla_user -p'your-password' wasla

# Inside MySQL:
SELECT DATABASE();
SELECT VERSION();
EXIT;
```

### Docker Connection

```bash
# If using Docker Compose
docker-compose exec db mysql -u wasla_user -p'your-password' wasla

# Inside MySQL:
SELECT VERSION();
EXIT;
```

---

## Troubleshooting

### MySQL Service Won't Start

```bash
# Check service status
sudo systemctl status mysql

# View error logs
sudo tail -f /var/log/mysql/error.log

# Restart service
sudo systemctl restart mysql

# If it's a permission issue
sudo chown -R mysql:mysql /var/lib/mysql
sudo chmod -R 755 /var/lib/mysql
sudo systemctl start mysql
```

### Connection Refused Error

```bash
# Verify MySQL is running
sudo systemctl status mysql

# Check if MySQL is listening on port 3306
sudo netstat -tlnp | grep mysql
# Or use ss command (newer systems)
sudo ss -tlnp | grep mysql

# Check MySQL bind address in config
sudo grep "bind-address" /etc/mysql/mysql.conf.d/mysqld.cnf

# For remote connections, ensure bind-address is set to 0.0.0.0
```

### Authentication Failed

```bash
# Reset root password (if forgotten)
sudo /usr/bin/mysqld_safe --skip-grant-tables &
mysql -u root

# Inside MySQL:
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY 'new-password';
EXIT;

# Kill the safe mode process and restart normally
sudo systemctl restart mysql
```

### Database Not Found

```bash
# List all databases
mysql -u root -p -e "SHOW DATABASES;"

# If 'wasla' database doesn't exist, create it
mysql -u root -p -e "CREATE DATABASE wasla CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### Permission Denied for User

```bash
# Check user privileges
mysql -u root -p -e "SHOW GRANTS FOR 'wasla_user'@'localhost';"

# Grant all privileges
mysql -u root -p -e "GRANT ALL PRIVILEGES ON wasla.* TO 'wasla_user'@'localhost';"
mysql -u root -p -e "FLUSH PRIVILEGES;"
```

### Charset/Collation Issues

```bash
# Verify database charset
mysql -u root -p -e "SHOW CREATE DATABASE wasla;"

# Change charset if needed
mysql -u root -p -e "ALTER DATABASE wasla CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Check table charset
mysql -u root -p wasla -e "SHOW CREATE TABLE table_name;"

# Convert existing tables
mysql -u root -p wasla -e "ALTER TABLE table_name CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
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
GRANT SELECT, INSERT, UPDATE, DELETE ON `wasla`.* TO 'wasla_user'@'localhost';

-- For specific tables only
GRANT SELECT, INSERT, UPDATE ON `wasla`.`orders` TO 'wasla_user'@'localhost';
```

### 3. Limit Remote Access

```bash
# Only allow local connections
bind-address = 127.0.0.1

# Or specify allowed hosts in configuration
# For Docker: bind-address = 0.0.0.0

# Verify connection method
mysql -h localhost -u wasla_user -p  # Local
# mysql -h remote-ip -u wasla_user -p  # Remote (if allowed)
```

### 4. Regular Updates

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get upgrade mysql-server

# CentOS/RHEL
sudo yum update mysql-server

# Restart after update
sudo systemctl restart mysql
```

### 5. User Isolation

```sql
-- Separate users for different purposes
CREATE USER 'wasla_read'@'localhost' IDENTIFIED BY 'password';
GRANT SELECT ON `wasla`.* TO 'wasla_read'@'localhost';

CREATE USER 'wasla_write'@'localhost' IDENTIFIED BY 'password';
GRANT SELECT, INSERT, UPDATE, DELETE ON `wasla`.* TO 'wasla_write'@'localhost';

CREATE USER 'wasla_admin'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON `wasla`.* TO 'wasla_admin'@'localhost';
```

### 6. Disable Root Remote Access

```sql
-- Delete remote root access
DELETE FROM mysql.user WHERE User='root' AND Host != 'localhost';
FLUSH PRIVILEGES;
```

---

## Backup & Recovery

### Manual Backup

#### Single Database

```bash
# Backup database to file
mysqldump -u wasla_user -p wasla > wasla_backup.sql

# With date timestamp
mysqldump -u wasla_user -p wasla > wasla_backup_$(date +%Y%m%d_%H%M%S).sql
```

#### All Databases

```bash
# Backup all databases
mysqldump -u root -p --all-databases > all_databases_backup.sql

# Backup all databases except test and information_schema
mysqldump -u root -p --all-databases --ignore-table=mysql.event > all_databases_backup.sql
```

#### Compressed Backup (Recommended for Large Databases)

```bash
# Single database with gzip compression
mysqldump -u wasla_user -p wasla | gzip > wasla_backup.sql.gz

# All data with compression
mysqldump -u root -p --all-databases | gzip > all_databases_backup.sql.gz

# Verify backup file size
ls -lh wasla_backup.sql.gz
```

### Restore from Backup

#### Single Database

```bash
# Restore database from backup
mysql -u wasla_user -p wasla < wasla_backup.sql

# From compressed backup
zcat wasla_backup.sql.gz | mysql -u wasla_user -p wasla
```

#### All Databases

```bash
# Restore all databases
mysql -u root -p < all_databases_backup.sql

# From compressed backup
zcat all_databases_backup.sql.gz | mysql -u root -p
```

### Automated Backup (Cron Job)

```bash
# Create backup script
cat > /home/user/backup_mysql.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/home/user/mysql_backups"
MYSQL_USER="wasla_user"
MYSQL_PASSWORD="password"
MYSQL_DB="wasla"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

mysqldump -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DB | gzip > $BACKUP_DIR/wasla_$DATE.sql.gz

# Keep only last 7 days of backups
find $BACKUP_DIR -name "wasla_*.sql.gz" -mtime +7 -delete

echo "Backup completed: wasla_$DATE.sql.gz"
EOF

chmod +x /home/user/backup_mysql.sh

# Add to crontab for daily 2 AM backup
crontab -e

# Add line:
# 0 2 * * * /home/user/backup_mysql.sh
```

### Backup Verification

```bash
# List backups
ls -lh /path/to/backups/

# Verify backup integrity
gunzip -t wasla_backup.sql.gz

# Check backup file contents
zcat wasla_backup.sql.gz | head -20
```

---

## Common Django Database Operations

### Initialize Database

```bash
# Apply all migrations
python manage.py migrate

# Create tables automatically
python manage.py migrate --run-syncdb
```

### Create Migrations

```bash
# Create new migrations
python manage.py makemigrations

# Show migration plan
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
# Open interactive MySQL shell via Django
python manage.py dbshell

# Inside MySQL:
SHOW TABLES;
SELECT COUNT(*) FROM auth_user;
EXIT;
```

---

## Performance Monitoring

### Check MySQL Processes

```bash
# Show active processes
mysql -u root -p -e "SHOW PROCESSLIST;"

# Kill slow query
mysql -u root -p -e "KILL query_id;"
```

### Monitor Disk Usage

```bash
# Check database size
mysql -u root -p -e "SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024, 2) AS size_mb FROM information_schema.tables GROUP BY table_schema;"

# Check specific database
mysql -u root -p -e "SELECT table_name, ROUND((data_length+index_length)/1024/1024, 2) AS size_mb FROM information_schema.tables WHERE table_schema='wasla' ORDER BY (data_length+index_length) DESC;"
```

### Enable Slow Query Log

```sql
-- Enable slow query logging
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;

-- Check status
SHOW VARIABLES LIKE '%slow_query_log%';
```

---

## Environment Variables

### .env File Configuration

```bash
# MySQL specific variables
DJANGO_DB_DEFAULT=mysql
DB_ENGINE=django.db.backends.mysql
MYSQL_DB_NAME=wasla
MYSQL_DB_USER=wasla_user
MYSQL_DB_PASSWORD=your-secure-password
MYSQL_DB_HOST=localhost
MYSQL_DB_PORT=3306
MYSQL_ROOT_PASSWORD=root-password

# Compatibility variables
DB_NAME=wasla
DB_USER=wasla_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=3306
```

---

## Support & Resources

- **MySQL Official Documentation**: https://dev.mysql.com/doc/
- **Django Database Backend**: https://docs.djangoproject.com/en/stable/ref/settings/#databases
- **MySQL Tutorial**: https://www.mysql.com/why-mysql/
- **Performance Tuning**: https://dev.mysql.com/doc/refman/8.0/en/optimization.html

---

**Last Updated:** February 17, 2026
**MySQL Version:** 8.0
**Django Version:** 6.0+
