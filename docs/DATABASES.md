# Database Configuration Guide

!> This directory contains comprehensive documentation for setting up and managing databases for WASLA v2.

## Quick Links

### Installation & Configuration Guides

- **[MySQL Installation & Configuration](MYSQL_INSTALLATION.md)** - Complete MySQL 8.0 setup and management
- **[PostgreSQL Installation & Configuration](POSTGRESQL_INSTALLATION.md)** - Complete PostgreSQL 15 setup and management

---

## Database Selection

### Which Database Should I Choose?

#### MySQL 8.0 (Recommended for most projects)
**Best for:**
- Rapid development and deployment
- Good performance for most use cases
- Easier setup with automatic defaults
- Good support in shared hosting environments
- Simpler backup and recovery process

**Performance:**
- Excellent for read-heavy applications
- Good for moderate write operations
- Fast query execution for simple queries
- Suitable for datasets up to several TB

**Features:**
- Support for transactions (InnoDB)
- UTF-8 support with utf8mb4 charset
- Full-text search capabilities
- Replication support

---

#### PostgreSQL 15 (Advanced features, larger datasets)
**Best for:**
- Complex queries and advanced SQL operations
- Large datasets with complex relationships
- Projects requiring advanced features
- High-performance analytical queries
- Data integrity and ACID compliance priorities

**Performance:**
- Excellent for complex queries
- Superior for analytical workloads
- Better handling of very large datasets
- More efficient with JSON/JSONB data

**Features:**
- Advanced JSON/JSONB support
- Complex query optimization
- Window functions
- Common Table Expressions (CTEs)
- Partitioning capabilities
- Full-text search with ranking
- Array and range types
- Native UUID support

---

## Automated Setup

### Interactive Database Selection

The deployment script provides an interactive menu for database selection:

```bash
# Start the deployment script
DEPLOY_TYPE=traditional bash wasla/deploy.sh

# When prompted:
# 💾 Database Selection
# 
# Which database system would you like to use?
# 
# 1) MySQL 8.0       (Recommended - Good performance, easy setup)
# 2) PostgreSQL 15   (Advanced - More features, excellent for large datasets)
# 
# Enter your choice [1-2] (default: 1):
```

### Pre-select Database via Environment Variable

```bash
# Use MySQL 8.0
DB_SYSTEM=mysql DEPLOY_TYPE=traditional bash wasla/deploy.sh

# Use PostgreSQL 15
DB_SYSTEM=postgresql DEPLOY_TYPE=traditional bash wasla/deploy.sh

# Use Docker
DB_SYSTEM=mysql DEPLOY_TYPE=docker bash wasla/deploy.sh
DB_SYSTEM=postgresql DEPLOY_TYPE=docker bash wasla/deploy.sh
```

---

## Setup Process

### What Gets Installed

**MySQL Path:**
```
✅ MySQL Server 8.0
✅ Database 'wasla' (UTF-8 encoded)
✅ User 'wasla_user' (secure password)
✅ Python driver: mysqlclient
❌ PostgreSQL (not installed)
```

**PostgreSQL Path:**
```
✅ PostgreSQL 15
✅ Database 'wasla' (UTF-8 encoded)
✅ User 'wasla_user' (secure password)
✅ Python driver: psycopg2-binary
❌ MySQL (not installed)
```

### Automatic Configuration

The deployment script automatically:

1. **Detects existing installation**
   - Checks if database system is already installed
   - Skips reinstallation if found

2. **Creates database & user**
   - Database: `wasla`
   - User: `wasla_user`
   - Password: Auto-generated secure password

3. **Updates environment file**
   - Configures `.env` with database settings
   - Backs up existing `.env` before modifications
   - Sets correct port (3306 for MySQL, 5432 for PostgreSQL)
   - Sets correct database engine for Django

4. **Installs Python driver**
   - MySQL: `mysqlclient`
   - PostgreSQL: `psycopg2-binary`

5. **Tests database connection**
   - Verifies database is accessible
   - Reports connection status

---

## Configuration Files

### Environment Variables (.env)

**MySQL Configuration:**
```bash
DJANGO_DB_DEFAULT=mysql
DB_ENGINE=django.db.backends.mysql
DB_NAME=wasla
DB_USER=wasla_user
DB_PASSWORD=<secure-password>
DB_HOST=localhost
DB_PORT=3306
```

**PostgreSQL Configuration:**
```bash
DJANGO_DB_DEFAULT=postgresql
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wasla
DB_USER=wasla_user
DB_PASSWORD=<secure-password>
DB_HOST=localhost
DB_PORT=5432
```

### Django Settings (config/settings.py)

Supports all three database backends:

```python
# Database backend selection via DJANGO_DB_DEFAULT
DB_DEFAULT_ALIAS = os.getenv("DJANGO_DB_DEFAULT", "mysql")

# Available configurations:
DATABASES = {
    "default": DEFAULT_DB,  # SQLite, MySQL, or PostgreSQL
    "sqlite": SQLITE_CONFIG,
    "mysql": MYSQL_CONFIG,
    "postgresql": POSTGRESQL_CONFIG,
}
```

---

## Connection Methods

### Command Line

**MySQL:**
```bash
mysql -h localhost -u wasla_user -p wasla
# Enter password when prompted
```

**PostgreSQL:**
```bash
psql -h localhost -U wasla_user -d wasla
# Enter password when prompted
```

### Django Management Command

```bash
python manage.py dbshell
```

### Python Direct Connection

**MySQL:**
```python
import MySQLdb
connection = MySQLdb.connect(
    host='localhost',
    user='wasla_user',
    passwd='password',
    db='wasla'
)
```

**PostgreSQL:**
```python
import psycopg2
connection = psycopg2.connect(
    host='localhost',
    user='wasla_user',
    password='password',
    database='wasla'
)
```

---

## Service Management

### Start/Stop/Restart Services

**MySQL:**
```bash
# Start MySQL
sudo systemctl start mysql

# Stop MySQL
sudo systemctl stop mysql

# Restart MySQL
sudo systemctl restart mysql

# Check status
sudo systemctl status mysql
```

**PostgreSQL:**
```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Stop PostgreSQL
sudo systemctl stop postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql

# Check status
sudo systemctl status postgresql
```

---

## Backup & Recovery

### Quick Backup

**MySQL:**
```bash
mysqldump -u wasla_user -p wasla | gzip > backup_$(date +%Y%m%d).sql.gz
```

**PostgreSQL:**
```bash
pg_dump -U wasla_user -d wasla | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Quick Restore

**MySQL:**
```bash
zcat backup_2024.sql.gz | mysql -u wasla_user -p wasla
```

**PostgreSQL:**
```bash
zcat backup_2024.sql.gz | psql -U wasla_user -d wasla
```

---

## Troubleshooting

### Connection Issues

**Check if database service is running:**
```bash
# MySQL
sudo systemctl status mysql

# PostgreSQL
sudo systemctl status postgresql
```

**Verify database exists:**
```bash
# MySQL
mysql -u root -p -e "SHOW DATABASES;"

# PostgreSQL
sudo -u postgres psql -l
```

**Check user permissions:**
```bash
# MySQL
mysql -u root -p -e "SELECT User, Host FROM mysql.user;"

# PostgreSQL
sudo -u postgres psql -c "SELECT * FROM pg_user;"
```

### Common Issues

See the specific database guide for detailed troubleshooting:
- [MySQL Troubleshooting](MYSQL_INSTALLATION.md#troubleshooting)
- [PostgreSQL Troubleshooting](POSTGRESQL_INSTALLATION.md#troubleshooting)

---

## Django Database Operations

All operations work with both database systems:

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Open database shell
python manage.py dbshell

# Export data
python manage.py dumpdata > data.json

# Import data
python manage.py loaddata data.json
```

---

## Performance Considerations

### MySQL 8.0
- Better for typical web applications
- Lower memory overhead
- Faster setup and configuration
- Good for read-heavy workloads
- Simple backup procedures

### PostgreSQL 15
- Better for complex queries
- More advanced indexing options
- Superior for large datasets
- Better ACID compliance guarantees
- More sophisticated backup options

Both databases can handle production workloads. Choose based on your specific requirements.

---

## Docker Deployment

Both databases are supported in Docker Compose:

```bash
# Deploy with MySQL
DEPLOY_TYPE=docker DB_SYSTEM=mysql bash wasla/deploy.sh

# Deploy with PostgreSQL
DEPLOY_TYPE=docker DB_SYSTEM=postgresql bash wasla/deploy.sh
```

Both options are pre-configured in the docker-compose.yml and will:
- Pull appropriate database image
- Create database container
- Set up volumes for data persistence
- Configure health checks
- Enable automatic startup

---

## Support

For detailed instructions and troubleshooting:

- **MySQL Questions:** See [MYSQL_INSTALLATION.md](MYSQL_INSTALLATION.md)
- **PostgreSQL Questions:** See [POSTGRESQL_INSTALLATION.md](POSTGRESQL_INSTALLATION.md)
- **Deployment Help:** See [../DEPLOYMENT.md](../DEPLOYMENT.md)
- **Django Setup:** See [../TECHNICAL_GUIDE.md](../TECHNICAL_GUIDE.md)

---

**Last Updated:** February 17, 2026
**Supported Versions:** MySQL 8.0, PostgreSQL 15
**Django Compatibility:** 6.0+
