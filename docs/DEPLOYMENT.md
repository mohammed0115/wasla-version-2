# WASLA Deployment Guide

## Quick Start

### Prerequisites
- Docker & Docker Compose 1.29+
- Git
- An `.env` file configured from `.env.example`

### Local Development (Docker)

1. **Clone and Setup**
```bash
git clone <repo>
cd wasla-version-2
cp .env.example .env
```

2. **Configure Environment**
Edit `.env` with your local database and payment provider credentials:
```bash
DB_PASSWORD=your-secure-password
TAP_API_KEY=your-tap-key
STRIPE_API_KEY=sk_test_your_stripe_key
...
```

3. **Start Services**
```bash
# Build and start all services (PostgreSQL, Redis, Django, React, Nginx)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

4. **Access Application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api
- Admin: http://localhost:8000/admin (user: admin / pass: admin123)
- API Docs: http://localhost:8000/api/schema/

### Database Migrations

Migrations run automatically via `docker-entrypoint.sh`, but you can also run manually:

```bash
# Inside container
docker-compose exec backend python manage.py migrate

# Or from host
docker-compose run --rm backend python manage.py migrate
```

### Create Admin User

```bash
docker-compose exec backend python manage.py createsuperuser
```

### Collect Static Files

```bash
docker-compose exec backend python manage.py collectstatic --noinput
```

### Run Tests

```bash
docker-compose exec backend pytest
```

---

## Production Deployment

### Option 1: Docker (Recommended)

1. **Prepare Configuration**
```bash
# Set production environment variables
export DEBUG=False
export SECRET_KEY=$(openssl rand -hex 32)
export ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

2. **Build and Push Container**
```bash
# Build image
docker build -t myregistry/wasla:1.0.0 .

# Push to registry
docker push myregistry/wasla:1.0.0
```

3. **Deploy with Docker Compose** (on server)
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: Traditional Server

1. **Install Dependencies**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib nginx
```

2. **Setup Application**
```bash
cd /var/www/wasla
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure Database**
```bash
createdb wasla
python manage.py migrate
```

4. **Collect Static Files**
```bash
python manage.py collectstatic --noinput
```

5. **Start with Gunicorn**
```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 4
```

6. **Configure Nginx** (reverse proxy)
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location /static/ {
        alias /var/www/wasla/staticfiles/;
    }
    
    location /media/ {
        alias /var/www/wasla/media/;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Option 3: Kubernetes

1. **Build and Push Image**
```bash
docker build -t myregistry/wasla:latest .
docker push myregistry/wasla:latest
```

2. **Deploy with Helm**
```bash
helm install wasla ./helm --values helm/values-prod.yaml
```

---

## Monitoring & Maintenance

### Health Checks
```bash
# Basic health check
curl http://localhost:8000/api/health/

# Detailed health with dependencies
curl http://localhost:8000/api/health/detailed/

# Service status
curl http://localhost:8000/api/status/
```

### View Logs
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db
```

### Database Backup
```bash
docker-compose exec db pg_dump -U postgres wasla > backup.sql
```

### Database Restore
```bash
cat backup.sql | docker-compose exec -T db psql -U postgres
```

### Clear Cache
```bash
docker-compose exec redis redis-cli FLUSHALL
```

---

## Security Checklist

Before going to production:

- [ ] Set `SECRET_KEY` to a long random string
- [ ] Set `DEBUG = False`
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Enable HTTPS with SSL certificate (Let's Encrypt)
- [ ] Configure CORS_ALLOWED_ORIGINS properly
- [ ] Set strong database password
- [ ] Use environment variables for all secrets
- [ ] Enable Django security middleware
- [ ] Configure webhook HMAC secrets for all payment providers
- [ ] Setup email configuration for notifications
- [ ] Configure backup strategy for PostgreSQL
- [ ] Setup monitoring alerts (Sentry, Datadog, etc.)

---

## Troubleshooting

### Database Connection Refused
```bash
# Check PostgreSQL is running
docker-compose ps

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Static Files Not Loading
```bash
docker-compose exec backend python manage.py collectstatic --clear --noinput
docker-compose restart nginx
```

### Cache Connection Issues
```bash
# Test Redis connection
docker-compose exec redis redis-cli ping

# Clear cache
docker-compose exec redis redis-cli FLUSHALL
```

### Payment Provider Errors
- Check API keys in `.env` file
- Verify webhook URLs are accessible
- Check payment provider sandbox/production mode matches `is_sandbox_mode`

---

## Scaling

### Horizontal Scaling
```bash
# Scale Django workers
docker-compose up -d --scale backend=3

# Scale workers with load balancer
docker-compose up -d nginx
```

### Caching Strategy
- Enable Redis caching for frequently accessed data
- Use `@cache_page()` decorator on read-only views
- Cache invalidation on data updates

### Database Optimization
- Add indexes on frequently queried fields
- Use `select_related()` and `prefetch_related()`
- Archive old orders to separate table

---

## Support

For issues, check:
- [GitHub Issues](https://github.com/your-org/wasla/issues)
- [Documentation](https://docs.wasla.com)
- [Community Forum](https://community.wasla.com)
