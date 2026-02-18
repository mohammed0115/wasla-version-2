# WASLA Quick Reference Guide

## 🚀 Quick Start (5 minutes)

```bash
# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access
Frontend:  http://localhost:5173
Backend:   http://localhost:8000/api
Admin:     http://localhost:8000/admin (admin/admin123)
Health:    http://localhost:8000/api/health/
```

---

## 📂 Project Structure

```
wasla-version-2/
├── wasla/                      # Backend (Django)
│   ├── config/                 # Settings & URLs
│   ├── accounts/               # Users & auth
│   ├── payments/               # Payment processing
│   ├── orders/                 # Orders & cart
│   ├── catalog/                # Products & inventory
│   ├── shipping/               # Shipping integration
│   ├── admin/                  # Admin metrics
│   ├── system/                 # Exceptions & health
│   └── manage.py
├── frontend/                   # Frontend (React)
│   ├── src/
│   │   ├── store/              # Zustand auth store
│   │   ├── pages/              # Page components
│   │   ├── components/         # Reusable components
│   │   └── App.tsx
│   ├── Dockerfile
│   └── package.json
├── Dockerfile                  # Backend image
├── docker-compose.yml          # Local development
├── .env.example               # Environment template
├── docker-entrypoint.sh       # Initialization script
└── DEPLOYMENT.md              # Deployment guide
```

---

## 🔐 Authentication Flow

### Login
```typescript
1. User enters email + password
2. Frontend calls POST /api/auth/token/
3. Backend validates & returns { access, refresh, user }
4. Frontend stores tokens in localStorage
5. Axios adds: Authorization: Bearer {access}
6. Redirect to /dashboard
```

### Register
```typescript
1. User fills multi-step form
2. Frontend POST /api/auth/register/
3. Backend creates user & profile
4. Auto login & return tokens
5. Redirect to /onboarding/store
```

### Token Refresh
```typescript
1. Token expires (401 response)
2. Frontend POST /api/auth/token/refresh/ with refresh token
3. Backend returns new access token
4. Retry original request
5. Continue session
```

---

## 📊 Admin Dashboard Data Flow

```
Dashboard Component
    ↓
┌─────────────────────────────────────────┐
│ useQuery('admin-metrics')               │
│ GET /api/admin/metrics/                 │
│ Response: { revenue_today, orders, ... }│
└─────────────────────────────────────────┘
    ↓
StatCard Components Render
    ↓
┌─────────────────────────────────────────┐
│ useQuery(['chart-data', dateRange])     │
│ GET /api/admin/analytics/timeline/      │
│ Response: { labels, revenue, orders }   │
└─────────────────────────────────────────┘
    ↓
Chart.js Components Render
    ↓
Real-time Updates (refetch every 30s)
```

---

## 🐛 Error Handling

### Frontend Errors
```typescript
try {
  await login(email, password);
} catch (error) {
  toast.error(error.message);  // Shows toast
  // Error automatically logged
}
```

### Backend Errors
```
Request → Django Middleware
           ↓
      Error Occurs
           ↓
ErrorHandlingMiddleware
      ↓
ErrorResponseFormatter
      ↓
JSON Response with:
  - code (VALIDATION_ERROR, etc.)
  - message
  - status_code
  - request_id (for tracking)
      ↓
Logged + Optional Sentry
```

### Error Codes Reference
```
400 - VALIDATION_ERROR    (bad input)
401 - UNAUTHORIZED        (not logged in)
403 - PERMISSION_DENIED   (no access)
404 - NOT_FOUND          (resource missing)
409 - CONFLICT           (duplicate/state error)
429 - RATE_LIMITED       (too many requests)
500 - SERVER_ERROR       (unexpected error)
402 - PAYMENT_ERROR      (payment failed)
400 - WEBHOOK_ERROR      (webhook issue)
```

---

## 💾 Database Schema

### RefundRecord (New)
```sql
CREATE TABLE payments_refundrecord (
  id BIGINT PRIMARY KEY,
  payment_intent_id BIGINT,
  amount DECIMAL(10,2),
  status VARCHAR(20),        -- pending|approved|rejected|failed|completed
  provider_reference VARCHAR(255),
  requested_by_id INT,
  raw_response JSONB,
  created_at TIMESTAMP,
  approved_at TIMESTAMP,
  processed_at TIMESTAMP
);

-- Indexes
CREATE INDEX payments_refundrecord_payment_status ON payments_refundrecord(payment_intent_id, status);
CREATE INDEX payments_refundrecord_created ON payments_refundrecord(created_at);
```

### PaymentProviderSettings (Enhanced)
```sql
ALTER TABLE payments_paymentprovidersettings ADD COLUMN
  transaction_fee_percent DECIMAL(5,2) DEFAULT 2.5,
  wasla_commission_percent DECIMAL(5,2) DEFAULT 3.0,
  is_sandbox_mode BOOLEAN DEFAULT FALSE;
```

---

## 🌐 API Endpoints Reference

### Authentication
| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| POST | /auth/token/ | {email, password} | {access, refresh, user} |
| POST | /auth/token/refresh/ | {refresh} | {access} |
| POST | /auth/register/ | {email, password, first_name, ...} | {access, refresh, user} |
| POST | /auth/logout/ | {} | {success: true} |

### Admin Dashboard
| Method | Endpoint | Params | Response |
|--------|----------|--------|----------|
| GET | /admin/metrics/ | - | {revenue_today, revenue_this_month, ...} |
| GET | /admin/analytics/timeline/ | range=7d\|30d\|90d | {labels, revenue[], orders[]} |
| GET | /admin/analytics/top-products/ | limit=5 | [{name, sales, revenue}, ...] |

### Health Checks
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /health/ | Basic health (200 = ok) |
| GET | /health/detailed/ | Database, cache, migrations status |
| GET | /status/ | Service stats (users, products, orders) |

---

## 🎨 Frontend Components Cheat Sheet

### Login Page
```typescript
import LoginPage from '@/pages/auth/LoginPage';

// Uses:
// - useAuthStore() for login action
// - useForm() for validation
// - react-toastify for notifications
```

### Register Page
```typescript
import RegisterPage from '@/pages/auth/RegisterPage';

// Multi-step form with:
// - Step 1: Account info
// - Step 2: Password
// - Step 3: Store details
```

### Dashboard
```typescript
import AdminDashboard from '@/pages/admin/Dashboard';

// Features:
// - Real-time metrics (30s refresh)
// - 4 chart types (Line, Bar, Donut, Table)
// - Date range filter
// - Loading skeletons
```

### Error Handling
```typescript
import { ErrorBoundary, ErrorPages } from '@/components/ErrorBoundary';

<ErrorBoundary>
  <App />
</ErrorBoundary>

// Use custom error pages:
// - NotFoundPage (404)
// - UnauthorizedPage (401)
// - ServerErrorPage (500)
```

---

## 🔒 Security Checklist

- [x] JWT token handling
- [x] Password validation (8+ chars)
- [x] Environment variables for secrets
- [x] HTTPS ready (config enabled)
- [x] CSRF protection middleware
- [x] CORS configuration
- [x] Input validation (Zod)
- [x] Error sanitization (no stack traces)
- [x] Database indexing (prevent N+1)
- [x] SQL injection prevention (ORM)
- [x] XSS prevention (React escaping)
- [x] Rate limiting ready
- [x] Health check endpoint secured
- [ ] HSTS headers (enable in production)
- [ ] CSP headers (configure)
- [ ] API key rotation (setup schedule)

---

## 📦 Dependency Versions

### Backend (Python)
```
Django==4.2+
djangorestframework==3.14+
djangorestframework-simplejwt==5.3+
psycopg2==2.9+           (PostgreSQL)
redis==5.0+              (Redis)
celery==5.3+             (Background tasks)
gunicorn==21+            (WSGI server)
```

### Frontend (Node)
```
react==18.2
react-router-dom==6.20
react-query==3.39
react-hook-form==7.48
chart.js==4.4
tailwindcss==3.3
framer-motion==10.16
```

---

## 🚢 Deployment Checklist

### Pre-Deployment
- [ ] Update `.env` with production values
- [ ] Set `SECRET_KEY` to new random value
- [ ] Verify `ALLOWED_HOSTS` configuration
- [ ] Test payment provider integrations
- [ ] Setup email backend (SMTP)
- [ ] Configure database backups
- [ ] Setup SSL certificate
- [ ] Enable hashing for passwords
- [ ] Disable DEBUG mode
- [ ] Setup monitoring (Sentry)

### Deployment
- [ ] Run migrations: `python manage.py migrate`
- [ ] Collect static: `python manage.py collectstatic`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Start services: `docker-compose up -d`
- [ ] Verify health: `curl http://.../api/health/`
- [ ] Test login flow
- [ ] Verify webhook endpoints
- [ ] Setup monitoring alerts
- [ ] Configure log aggregation
- [ ] Schedule database backups

### Post-Deployment
- [ ] Monitor error logs daily
- [ ] Check performance metrics
- [ ] Test payment processing
- [ ] Verify email notifications
- [ ] Review security headers
- [ ] Rotate API keys
- [ ] Update documentation

---

## 🆘 Common Issues & Solutions

### Issue: Database Connection Refused
```bash
# Check if PostgreSQL is running
docker-compose ps

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db

# Re-run migrations
docker-compose exec backend python manage.py migrate
```

### Issue: Static Files Not Loading
```bash
# Collect static files
docker-compose exec backend python manage.py collectstatic --clear

# Restart Nginx
docker-compose restart nginx

# Check file permissions
docker-compose exec backend ls -la staticfiles/
```

### Issue: Login Fails
```bash
# Check auth endpoint logs
docker-compose logs backend | grep auth

# Test endpoint directly
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Verify user exists
docker-compose exec backend python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> User.objects.filter(email='test@example.com').exists()
```

### Issue: Payment Provider Error
```bash
# Verify API keys in .env
cat .env | grep TAP_API_KEY

# Check payment logs
docker-compose logs backend | grep payment

# Verify webhook URL is accessible
curl https://your-domain.com/webhooks/payments/tap/

# Test provider in sandbox mode
- Stripe: Use sk_test_ keys
- Tap: Check TAP_SANDBOX=true
- PayPal: Check PAYPAL_SANDBOX=true
```

---

## 📱 Frontend Tasks

### To Add New Page
```typescript
// 1. Create component
export const MyPage: React.FC = () => {
  return <div>My Page</div>;
};

// 2. Add route in main App.tsx
<Route path="/my-page" element={<MyPage />} />

// 3. Add navigation link
<a href="/my-page">My Page</a>
```

### To Add New API Call
```typescript
// 1. Update authStore or create new store
const useMyStore = create((set) => ({
  data: null,
  fetchData: async () => {
    const response = await api.get('/my-endpoint/');
    set({ data: response.data });
  }
}));

// 2. Use in component
const { data } = useMyStore();
```

### To Style New Component
```typescript
import clsx from 'clsx';

<div className={clsx(
  'p-6 rounded-lg shadow-md',
  isActive && 'bg-blue-600 text-white',
  !isActive && 'bg-white text-gray-900'
)}>
  Conditional styles
</div>
```

---

## 🔗 Useful Resources

- [Docker Docs](https://docs.docker.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [React Docs](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [TypeScript](https://www.typescriptlang.org/)
- [Zod Validation](https://zod.dev/)
- [React Hook Form](https://react-hook-form.com/)
- [Zustand](https://github.com/pmndrs/zustand)

---

## 💡 Pro Tips

1. **Always use environment variables** - Never hardcode secrets
2. **Test locally first** - Use Docker Compose locally before production
3. **Monitor logs** - Check `docker-compose logs -f` frequently
4. **Regular backups** - Backup database daily in production
5. **Use pagination** - Don't fetch all records at once
6. **Cache aggressively** - Use Redis for frequently accessed data
7. **Log everything** - Detailed logs help debugging
8. **Test payment flow** - Always test with sandbox credentials first
9. **Keep dependencies updated** - Monthly security updates
10. **Document changes** - Keep CHANGELOG.md updated

---

## 📞 Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review documentation files
3. Create GitHub issue with: Error code, logs, reproduction steps
4. Contact: support@wasla.com

---

**Last Updated:** February 17, 2026  
**Version:** 1.0.0  
**Status:** Production Ready ✅
