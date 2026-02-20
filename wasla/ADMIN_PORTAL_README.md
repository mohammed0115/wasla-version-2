# Wasla Admin Portal

**Staff-Only Administration Interface for Wasla Platform**

## Overview

The Wasla Admin Portal is a secure, staff-only web interface for monitoring and managing the Wasla multi-tenant SaaS platform. It bypasses the store-based middleware and provides system-wide visibility into tenants, stores, payments, settlements, invoices, and webhooks.

## ✅ Features Completed

### Phase E - Admin Portal (Completed)

- **Middleware Bypass**: `/admin-portal/` routes bypass `TenantResolverMiddleware` to work on the main domain without subdomain requirements
- **Staff-Only Authentication**: Custom `@admin_portal_required` decorator enforces `is_staff` status
- **Dashboard with KPIs**:
  - Total tenants, stores, payments (30d), revenue (30d)
  - Pending settlements, total invoices, webhook events (30d)
  - Recent payments and webhooks tables
- **Entity Management Views**:
  - **Tenants**: List all tenants with store count, payment count, and status
  - **Stores**: List stores with tenant, subdomain, payment count, and status
  - **Payments**: Filterable payment attempts (by status/provider) with pagination
  - **Settlements**: Settlement records filtered by payout status
  - **Invoices**: Monthly invoice drafts by tenant with line counts
  - **Webhooks**: Webhook events filtered by provider and status
- **Bootstrap 5 UI**: Modern, responsive interface with Wasla brand colors (#1F4FD8, #3B6EF5, #F7941D)
- **Sidebar Navigation**: Fixed sidebar with active state indicators

## 🚀 Getting Started

### Access the Admin Portal

```bash
# URL (requires staff user)
http://localhost:8000/admin-portal/

# Test Credentials
Username: admin
Password: admin123
```

### Create Staff User

```bash
cd /home/mohamed/Desktop/wasla-version-2/wasla
source /home/mohamed/Desktop/wasla-version-2/.venv/bin/activate
python create_staff_user.py
```

### Generate Test Data

```bash
python create_test_data.py
```

This creates:
- 1 test tenant ("Test Merchant Co.")
- 1 test store ("Test Store")
- 20 webhook events with various statuses

## 📁 File Structure

```
wasla/
├── apps/
│   └── admin_portal/
│       ├── __init__.py
│       ├── apps.py                  # AdminPortalConfig
│       ├── decorators.py            # @admin_portal_required
│       ├── views.py                 # All views (login, dashboard, lists)
│       └── urls.py                  # URL routing
├── config/
│   ├── settings.py                  # INSTALLED_APPS += admin_portal
│   └── urls.py                      # path("admin-portal/", ...)
├── apps/tenants/middleware.py      # TenantResolverMiddleware bypass
└── templates/
    └── admin_portal/
        ├── base.html                # Simple base for login
        ├── base_portal.html         # Full layout with sidebar
        ├── login.html
        ├── dashboard.html
        ├── tenants.html
        ├── stores.html
        ├── payments.html
        ├── settlements.html
        ├── invoices.html
        └── webhooks.html
```

## 🔒 Security

- **Staff-Only Access**: All views (except login) require `user.is_staff = True`
- **Middleware Bypass**: `/admin-portal/` paths skip store resolution, setting `request.store = None` and `request.tenant = None`
- **Django Sessions**: Uses standard Django session authentication
- **Permission Denied**: Non-staff users receive HTTP 403 response

## 🎨 UI/UX

- **Colors**:
  - Primary: `#1F4FD8`
  - Secondary: `#3B6EF5`
  - Accent: `#F7941D`
- **Components**:
  - Bootstrap 5.3 (navbar, sidebar, cards, tables, badges, pagination)
  - Bootstrap Icons (visual indicators)
  - Responsive layout (mobile-friendly collapsible sidebar)
- **Typography**: System font stack (Apple/SF Pro, Segoe UI, Roboto)

## 📊 Dashboard KPIs

| KPI | Description | Query |
|-----|-------------|-------|
| Total Tenants | All tenants count | `Tenant.objects.count()` |
| Total Stores | All stores count | `Store.objects.count()` |
| Payments (30d) | PaymentAttempt records in last 30 days | `.filter(created_at__gte=last_30_days).count()` |
| Revenue (30d) | Sum of paid amounts in last 30 days | `.aggregate(Sum('amount'))` |
| Pending Settlements | Settlement records awaiting payout | `.filter(payout_status='pending').count()` |
| Total Invoices | All invoice drafts | `Invoice.objects.count()` |
| Webhooks (30d) | Webhook events in last 30 days | `.filter(received_at__gte=last_30_days).count()` |

## 🛠️ Implementation Notes

### Middleware Patch

Located in `apps/tenants/middleware.py`:

```python
class TenantResolverMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith("/admin-portal/"):
            request.store = None
            request.tenant = None
            return None
        # ... rest of subdomain logic
```

## 🔗 Navigation

| Route | View | Description |
|-------|------|-------------|
| `/admin-portal/` | dashboard_view | KPIs + recent activity |
| `/admin-portal/login/` | login_view | Staff login form |
| `/admin-portal/logout/` | logout_view | Session logout |
| `/admin-portal/tenants/` | tenants_view | Tenant list with pagination |
| `/admin-portal/stores/` | stores_view | Store list |
| `/admin-portal/payments/` | payments_view | Payment attempts (filterable) |
| `/admin-portal/settlements/` | settlements_view | Settlement records |
| `/admin-portal/invoices/` | invoices_view | Monthly invoices |
| `/admin-portal/webhooks/` | webhooks_view | Webhook events (filterable) |

## 📦 Dependencies

- Django 5.2.11
- Bootstrap 5.3.0 (CDN)
- Bootstrap Icons 1.11.0 (CDN)
- Python 3.12.3

## ✅ Phase E Complete

All requirements for the admin portal have been successfully implemented and tested.
