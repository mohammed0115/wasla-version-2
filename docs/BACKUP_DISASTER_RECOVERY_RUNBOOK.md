# Wassla Backup & Disaster Recovery Runbook

## Scope
This runbook covers:
- Automated daily PostgreSQL backups
- Media file backups
- Backup health verification
- Restore test procedure (DR drill)

Scripts location:
- `wasla/scripts/backup/postgres_daily_backup.sh`
- `wasla/scripts/backup/media_backup.sh`
- `wasla/scripts/backup/backup_health_check.sh`
- `wasla/scripts/backup/restore_test_procedure.sh`

---

## 1) Prerequisites
Install required tooling on the app host:

```bash
sudo apt update
sudo apt install -y postgresql-client tar gzip coreutils
```

Create backup directory:

```bash
sudo mkdir -p /var/backups/wasla/{db,media,logs}
sudo chown -R www-data:www-data /var/backups/wasla
```

---

## 2) Environment Variables
Set these in the execution context (systemd env file or cron wrapper):

```env
BACKUP_ROOT=/var/backups/wasla
RETENTION_DAYS=14

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=wasla
DB_USER=wasla_user
DB_PASSWORD=<secure-db-password>

MEDIA_DIR=/var/www/wasla/wasla/media
MAX_AGE_HOURS=26
```

Notes:
- Do not hardcode secrets in scripts.
- Provide `DB_PASSWORD` or `PGPASSWORD` via environment/secret store only.

---

## 3) Automated Backup Scheduling

### Option A: Cron (simple)
Use `crontab -e` for the service user (example `www-data`):

```cron
# PostgreSQL backup daily at 01:10 UTC
10 1 * * * BACKUP_ROOT=/var/backups/wasla DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=wasla DB_USER=wasla_user DB_PASSWORD=*** /var/www/wasla/wasla/scripts/backup/postgres_daily_backup.sh

# Media backup daily at 01:30 UTC
30 1 * * * BACKUP_ROOT=/var/backups/wasla MEDIA_DIR=/var/www/wasla/wasla/media RETENTION_DAYS=14 /var/www/wasla/wasla/scripts/backup/media_backup.sh

# Backup health verification daily at 02:00 UTC
0 2 * * * BACKUP_ROOT=/var/backups/wasla MAX_AGE_HOURS=26 /var/www/wasla/wasla/scripts/backup/backup_health_check.sh
```

### Option B: systemd timer (recommended)
Ready-made files are included in:
- `wasla/scripts/backup/systemd/`

Copy files:

```bash
sudo mkdir -p /etc/wasla
sudo cp /var/www/wasla/wasla/scripts/backup/systemd/backup.env.example /etc/wasla/backup.env
sudo chmod 600 /etc/wasla/backup.env
sudo nano /etc/wasla/backup.env

sudo cp /var/www/wasla/wasla/scripts/backup/systemd/wasla-backup-db.service /etc/systemd/system/
sudo cp /var/www/wasla/wasla/scripts/backup/systemd/wasla-backup-db.timer /etc/systemd/system/
sudo cp /var/www/wasla/wasla/scripts/backup/systemd/wasla-backup-media.service /etc/systemd/system/
sudo cp /var/www/wasla/wasla/scripts/backup/systemd/wasla-backup-media.timer /etc/systemd/system/
sudo cp /var/www/wasla/wasla/scripts/backup/systemd/wasla-backup-healthcheck.service /etc/systemd/system/
sudo cp /var/www/wasla/wasla/scripts/backup/systemd/wasla-backup-healthcheck.timer /etc/systemd/system/
```

Enable timers:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now wasla-backup-db.timer wasla-backup-media.timer wasla-backup-healthcheck.timer
sudo systemctl list-timers | grep wasla-backup
```

Reference unit (database) example:

```ini
[Unit]
Description=Wassla PostgreSQL backup

[Service]
Type=oneshot
User=www-data
EnvironmentFile=/etc/wasla/backup.env
ExecStart=/var/www/wasla/wasla/scripts/backup/postgres_daily_backup.sh
```

Create timer `/etc/systemd/system/wasla-backup-db.timer`:

```ini
[Unit]
Description=Run Wassla PostgreSQL backup daily

[Timer]
OnCalendar=*-*-* 01:10:00
Persistent=true

[Install]
WantedBy=timers.target
```

Repeat equivalent units for media backup and health-check scripts.

Enable timers:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now wasla-backup-db.timer
```

---

## 4) Backup Health Verification Job
Health script checks:
- Latest DB backup exists and is fresh
- Latest media backup exists and is fresh
- DB gzip integrity (`gzip -t`)
- Media archive integrity (`tar -tzf`)

Manual run:

```bash
BACKUP_ROOT=/var/backups/wasla MAX_AGE_HOURS=26 /var/www/wasla/wasla/scripts/backup/backup_health_check.sh
```

Exit code:
- `0` = healthy
- `1` = failure (alert)

Integrate with monitoring/alerting by checking command exit status.

---

## 5) Restore Instructions (Production Incident)

## 5.1 PostgreSQL restore (full)

```bash
export PGPASSWORD='<secure-db-password>'
gzip -dc /var/backups/wasla/db/latest.sql.gz | psql -h 127.0.0.1 -p 5432 -U wasla_user -d wasla
```

## 5.2 Media restore

```bash
sudo tar -xzf /var/backups/wasla/media/latest.tar.gz -C /var/www/wasla/wasla/media
sudo chown -R www-data:www-data /var/www/wasla/wasla/media
```

## 5.3 Post-restore validation

```bash
cd /var/www/wasla/wasla
source .venv/bin/activate
python manage.py check
python manage.py showmigrations | grep '\[ \]' || echo "All migrations applied"
```

Application checks:
- Admin login
- Merchant dashboard loads
- Product media renders
- Checkout/payment path sanity

---

## 6) Restore Test Procedure (DR Drill)
Run at least monthly:

```bash
BACKUP_ROOT=/var/backups/wasla DB_HOST=127.0.0.1 DB_PORT=5432 DB_USER=wasla_user DB_PASSWORD='<secure-db-password>' TEST_DB_NAME=wasla_restore_test RESTORE_WORKDIR=/tmp/wasla_restore_test /var/www/wasla/wasla/scripts/backup/restore_test_procedure.sh
```

Expected outcomes:
- Disposable DB recreated and restored
- `django_migrations` query succeeds
- Media archive extracts cleanly

Record drill results in an ops log with date, operator, and duration.

---

## 7) Retention and Storage Policy
- Local retention: `RETENTION_DAYS=14` (minimum)
- Recommended: replicate `/var/backups/wasla` to object storage (S3-compatible) daily
- Keep at least one offsite copy
- Encrypt backup storage at rest

---

## 8) Failure Handling
If any backup job fails:
1. Check latest script log under `/var/backups/wasla/logs`
2. Re-run the failed script manually with same env vars
3. Validate integrity (`gzip -t`, `tar -tzf`)
4. Trigger incident if no valid backup in 24h

---

## 9) Operational Checklist
- [ ] Daily DB backup successful
- [ ] Daily media backup successful
- [ ] Daily health check successful
- [ ] Monthly restore drill completed
- [ ] Offsite replication verified
