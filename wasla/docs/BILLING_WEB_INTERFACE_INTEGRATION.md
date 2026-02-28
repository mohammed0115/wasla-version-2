# Wasla Billing Web Interface - Integration Guide

**Status:** ✅ COMPLETE | Phase 2 Web Interface Implementation

**Last Updated:** 2026-02-26

---

## Overview

This guide provides integration instructions for the complete Django template-based billing web interface for Wasla's SaaS subscription management system.

### What's Included

- **6 Customer-Facing Templates** (1,600+ lines of HTML/CSS)
- **4 HTML Email Templates** (2,200+ lines of HTML/CSS)
- **1 Admin Dashboard Template** (400+ lines)
- **View Functions** (800+ lines of Python) for template rendering
- **URL Routing Configuration** with comprehensive documentation
- **Django Forms** for data validation and user input
- **CSS Styling** with responsive design and status badges

---

## Directory Structure

```
wasla/apps/subscriptions/
├── models_billing.py                    # Data models
├── services_billing.py                  # Business logic services
├── views_web.py                        # NEW: Web interface views
├── forms.py                             # NEW: Django forms
├── urls_web.py                          # NEW: URL routing
├── urls.py                              # EXISTING: API routing
├── views.py                             # EXISTING: API views
├── templates/subscriptions/
│   ├── dashboard.html                   # NEW: Main dashboard
│   ├── subscription_detail.html          # NEW: Subscription mgmt
│   ├── invoice_list.html                # NEW: Invoice listing
│   ├── invoice_detail.html              # NEW: Invoice details
│   ├── payment_method.html              # NEW: Payment method mgmt
│   ├── plan_change.html                 # NEW: Plan change interface
│   ├── admin_dashboard.html             # NEW: Admin analytics
│   ├── emails/
│   │   ├── invoice_issued.html          # NEW: HTML email
│   │   ├── payment_received.html        # NEW: HTML email
│   │   ├── grace_period_expiring.html   # NEW: HTML email
│   │   ├── store_suspended.html         # NEW: HTML email
│   │   ├── invoice_issued.txt           # EXISTING: Plain text
│   │   ├── payment_received.txt         # EXISTING: Plain text
│   │   ├── grace_period_expiring.txt    # EXISTING: Plain text
│   │   └── store_suspended.txt          # EXISTING: Plain text
│   └── base.html                        # EXISTING: Base template
```

---

## Installation Steps

### 1. Update Main URL Configuration

Edit `/wasla/config/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/billing/', include('wasla.apps.subscriptions.urls')),      # EXISTING
    path('billing/', include('wasla.apps.subscriptions.urls_web')),      # NEW
]
```

### 2. Update Django Settings

Edit `/wasla/config/settings.py`:

```python
# Add to INSTALLED_APPS if not already there
INSTALLED_APPS = [
    # ... existing apps
    'wasla.apps.subscriptions',
]

# Add template context processors (for user/tenant info in templates)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # ADD THIS:
                'django.template.context_processors.csrf',
            ],
        },
    },
]

# Email configuration for notifications
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-email-provider'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'billing@wasla.com'

# Webhook signature secret
WEBHOOK_SECRET = 'your-webhook-secret-key'
```

### 3. Create Base Template

Create `/wasla/templates/base.html` (if it doesn't exist):

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Wasla{% endblock %}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, sans-serif; color: #333; line-height: 1.6; }
        a { color: #0066cc; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav style="background: #f8f9fa; border-bottom: 1px solid #e0e0e0; padding: 1rem;">
        <div style="max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between;">
            <div><strong>Wasla Billing</strong></div>
            <div>
                {% if user.is_authenticated %}
                    {{ user.email }} | <a href="/logout">Logout</a>
                {%else %}
                    <a href="/login">Login</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <main style="max-width: 1200px; margin: 0 auto;">
        {% if messages %}
            <div style="margin: 1rem 0;">
                {% for message in messages %}
                    <div style="
                        padding: 1rem;
                        margin-bottom: 1rem;
                        border-radius: 4px;
                        {% if message.tags == 'error' %}
                            background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24;
                        {% elif message.tags == 'success' %}
                            background: #d4edda; border: 1px solid #c3e6cb; color: #155724;
                        {% else %}
                            background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460;
                        {% endif %}
                    ">
                        {{ message }}
                    </div>
                {% endfor %}
            </div>
        {% endif %}

        {% block content %}{% endblock %}
    </main>

    <footer style="background: #f8f9fa; border-top: 1px solid #e0e0e0; padding: 2rem; margin-top: 3rem; text-align: center; color: #666; font-size: 0.875rem;">
        <p>&copy; 2026 Wasla. All rights reserved.</p>
    </footer>
</body>
</html>
```

### 4. Create No Subscription Template

Create `/wasla/apps/subscriptions/templates/subscriptions/no_subscription.html`:

```html
{% extends "base.html" %}

{% block title %}No Subscription Found - Wasla{% endblock %}

{% block content %}
<div style="padding: 3rem 1rem; text-align: center;">
    <h1>No Active Subscription</h1>
    <p style="color: #666; margin: 1rem 0;">
        You don't have an active subscription yet.
    </p>
    <p>
        <a href="https://wasla.com/pricing" style="
            display: inline-block;
            background: #0066cc;
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 4px;
            text-decoration: none;
            margin-top: 1rem;
        ">Choose a Plan</a>
    </p>
</div>
{% endblock %}
```

### 5. Create Authentication Decorators/Mixins

Add to `/wasla/apps/subscriptions/views_web.py` (enhance existing):

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class SubscriptionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Ensure user has an active subscription."""
    
    def test_func(self):
        try:
            Subscription.objects.get(user=self.request.user)
            return True
        except Subscription.DoesNotExist:
            return False
    
    def handle_no_permission(self):
        return redirect('subscriptions:no-subscription')
```

---

## Template Usage Reference

### 1. Dashboard Template

**URL:** `/billing/dashboard/`

**Purpose:** Main billing overview page

**Context Variables Needed:**
```python
{
    'subscription': Subscription,           # Current subscription
    'outstanding_balance': Decimal,         # Total outstanding amount
    'outstanding_invoices': QuerySet,       # Invoices not paid
    'recent_invoices': QuerySet,            # Last 5 invoices
    'billing_cycles': QuerySet,             # Billing history
    'days_until_billing': int,              # Days until next charge
    'payment_method': PaymentMethod,        # Current payment method
}
```

**Key Features:**
- Status alerts (suspended, grace, overdue)
- KPI cards (plan, status, balance, next billing)
- Recent invoices table
- Billing history table
- Action buttons (manage subscription, update payment)

### 2. Subscription Detail Template

**URL:** `/billing/subscription/` or `/billing/subscription/<id>/`

**Purpose:** Manage subscription, view details, change/cancel

**Context Variables:**
```python
{
    'subscription': Subscription,           # Subscription object
    'items': QuerySet,                      # SubscriptionItem's
    'payment_method': PaymentMethod,        # Current payment method
    'plan_features': List,                  # Features of plan
}
```

**Form Actions:**
- POST with `action=cancel` and `cancel_reason`
- POST with `action=grace_period` and `grace_days`

### 3. Invoice List Template

**URL:** `/billing/invoices/`

**Purpose:** Browse and filter invoices

**Query Parameters:**
- `status`: 'all', 'issued', 'overdue', 'paid', 'partial'
- `overdue_only`: 'on' to filter overdue only
- `page`: pagination page number

**Context Variables:**
```python
{
    'page_obj': Page,                       # Paginated invoices
    'invoices': QuerySet,                   # Current page invoices
    'status_filter': str,                   # Applied status filter
    'overdue_only': bool,                   # Overdue filter applied
}
```

### 4. Invoice Detail Template

**URL:** `/billing/invoices/<id>/`

**Purpose:** View complete invoice with breakdown

**Context Variables:**
```python
{
    'invoice': Invoice,                     # Invoice object with related
    'dunning_attempts': QuerySet,           # Dunning attempts for invoice
    'payment_url': str,                     # URL to payment page
    'manage_subscription_url': str,         # URL to subscription page
}
```

### 5. Payment Method Template

**URL:** `/billing/payment-method/`

**Purpose:** View and update payment method

**Context Variables:**
```python
{
    'subscription': Subscription,
    'payment_method': PaymentMethod,        # Current or None
    'form': PaymentMethodForm,              # Django form instance
}
```

**Form Class:** `PaymentMethodForm`

**Supported Fields:**
- `method_type`: 'card' or 'bank'
- Card: card_number, cardholder_name, expiry_date, cvc
- Bank: account_number, bank_name
- save_for_later, agree_terms

### 6. Plan Change Template

**URL:** `/billing/plan-change/` or `/billing/plan-change/<id>/`

**Purpose:** View available plans, compare, and change

**Context Variables:**
```python
{
    'subscription': Subscription,           # Current subscription
    'available_plans': QuerySet,            # All active plans
    'comparison_features': List,            # Feature comparison
}
```

**Feature Comparison Structure:**
```python
[
    {
        'name': 'Feature Name',
        'plans': {
            plan_id: 'feature_value',
            # ... for each plan
        }
    },
    # ... more features
]
```

### 7. Admin Dashboard Template

**URL:** `/billing/admin/dashboard/`

**Purpose:** Admin analytics and metrics

**Context Variables:**
```python
{
    'total_mrr': Decimal,                   # Monthly recurring revenue
    'active_count': int,                    # Active subscriptions
    'overdue_count': int,                   # Overdue subscriptions
    'suspended_count': int,                 # Suspended subscriptions
    'subscriptions': QuerySet,              # All subscriptions
    'recent_invoices': QuerySet,            # Last 20 invoices
    'recent_payments': QuerySet,            # Last 10 payments
}
```

---

## Email Template Usage

### 1. Invoice Issued Email

**File:** `templates/subscriptions/emails/invoice_issued.html`

**Context Variables:**
```python
{
    'subscription': Subscription,
    'invoice': Invoice,
    'payment_url': str,
    'invoice_url': str,
    'manage_subscription_url': str,
    'support_url': str,
    'help_url': str,
    'faq_url': str,
}
```

**Usage in Service:**
```python
from django.core.mail import render_to_string

html_message = render_to_string(
    'subscriptions/emails/invoice_issued.html',
    context
)
send_mail(
    'Invoice Issued',
    text_message,  # plaintext fallback
    'billing@wasla.com',
    [subscription.user.email],
    html_message=html_message,
)
```

### 2. Payment Received Email

**File:** `templates/subscriptions/emails/payment_received.html`

**Context Variables:**
```python
{
    'subscription': Subscription,
    'invoice': Invoice,
    'payment_event': PaymentEvent,
    'payment_method': PaymentMethod,
    'invoice_url': str,
    'subscription_url': str,
    'support_url': str,
    'help_url': str,
    'faq_url': str,
}
```

### 3. Grace Period Expiring Email

**File:** `templates/subscriptions/emails/grace_period_expiring.html`

**Context Variables:**
```python
{
    'subscription': Subscription,
    'invoice': Invoice,
    'dunning_attempt': DunningAttempt,
    'grace_period': GracePeriod,
    'payment_url': str,
    'request_grace_url': str,
    'support_url': str,
    'manage_billing_url': str,
    'faq_url': str,
}
```

### 4. Store Suspended Email

**File:** `templates/subscriptions/emails/store_suspended.html`

**Context Variables:**
```python
{
    'subscription': Subscription,
    'invoice': Invoice,
    'suspension_date': date,
    'payment_method': PaymentMethod,
    'payment_url': str,
    'update_payment_url': str,
    'support_url': str,
    'billing_dashboard_url': str,
    'faq_url': str,
}
```

---

## Forms Usage

### PaymentMethodForm

```python
from wasla.apps.subscriptions.forms import PaymentMethodForm

if request.method == 'POST':
    form = PaymentMethodForm(request.POST)
    if form.is_valid():
        method_type = form.cleaned_data['method_type']
        # Process payment method
else:
    form = PaymentMethodForm()
```

**Validation Includes:**
- Luhn algorithm for card numbers
- Card expiry date validation
- CVV length and format
- Bank account number format
- Required field logic based on payment type

### PlanChangeForm

```python
from wasla.apps.subscriptions.forms import PlanChangeForm

form = PlanChangeForm(
    available_plans=available_plans,
    data=request.POST
)
```

### Additional Forms

- `GracePeriodRequestForm`: For grace period requests
- `SubscriptionCancellationForm`: For cancellation with feedback
- `InvoiceFilterForm`: For invoice filtering
- `InvoicePaymentForm`: For paying invoices

---

## URL Configuration

Add to your main `urls.py`:

```python
urlpatterns = [
    # ... other patterns
    path('billing/', include('wasla.apps.subscriptions.urls_web')),
]
```

### Available Routes

| Method | URL | View | Name |
|--------|-----|------|------|
| GET | `/billing/dashboard/` | billing_dashboard | dashboard |
| GET/POST | `/billing/subscription/` | subscription_detail | subscription-detail |
| GET/POST | `/billing/subscription/<id>/` | subscription_detail | subscription-detail-by-id |
| GET | `/billing/invoices/` | invoice_list | invoice-list |
| GET | `/billing/invoices/<id>/` | invoice_detail | invoice-detail |
| GET | `/billing/invoices/<id>/download/` | invoice_download | invoice-download |
| GET/POST | `/billing/payment-method/` | payment_method | payment-method |
| GET/POST | `/billing/plan-change/` | plan_change | plan-change |
| GET/POST | `/billing/plan-change/<id>/` | plan_change | plan-change-by-id |
| GET | `/billing/admin/dashboard/` | admin_billing_dashboard | admin-dashboard |
| POST | `/billing/api/proration/` | proration_calculator | proration-api |
| POST | `/billing/webhooks/payment/` | payment_webhook | payment-webhook |

---

## Static Assets & Styling

### CSS Framework

All templates use:
- **CSS Grid** for layouts
- **Flexbox** for components
- **CSS Variables** for theming (optional)
- **Responsive Design** with breakpoints

### Color Scheme

```css
Primary: #0066cc (Blues)
Success: #28a745 (Green)
Warning: #ffc107 (Yellow)
Danger: #dc3545 (Red)
Info: #0066cc (Blue)
Gray: #6c757d

Background: #f8f9fa
Border: #e0e0e0
Text: #333
Text Light: #666
```

### No External Dependencies

- No JavaScript frameworks (vanilla JS only)
- No CSS frameworks (Bootstrap, Tailwind, etc.)
- No icon libraries
- Pure HTML5/CSS3

---

## Security Considerations

### CSRF Protection

All forms include `{% csrf_token %}`:

```html
<form method="post">
    {% csrf_token %}
    <!-- form fields -->
</form>
```

### Authentication

All views require login:

```python
@login_required
def view_function(request):
    # ...
    pass
```

### Ownership Verification

All views verify user/tenant ownership:

```python
if invoice.billing_cycle.subscription.user != request.user:
    return HttpResponseForbidden()

if invoice.billing_cycle.subscription.tenant != request.user.tenant:
    return HttpResponseForbidden()
```

### Webhook Validation

Payment webhooks verify HMAC signature:

```python
expected_signature = hmac.new(
    settings.WEBHOOK_SECRET.encode(),
    request.body,
    hashlib.sha256
).hexdigest()

if not hmac.compare_digest(signature, expected_signature):
    return JsonResponse({'error': 'Invalid signature'}, status=403)
```

---

## Customization Guide

### Changing Colors

Edit the `<style>` block in each template:

```html
<style>
    .primary { color: #0066cc; }  /* Change this color */
</style>
```

Or create a shared CSS file:

```css
/* static/css/billing.css */
:root {
  --primary: #0066cc;
  --success: #28a745;
  --warning: #ffc107;
  --danger: #dc3545;
}
```

Then link in base.html:

```html
<link rel="stylesheet" href="{% static 'css/billing.css' %}">
```

### Adding Custom Fields

1. Update the model in `models_billing.py`
2. Create a migration
3. Update the form in `forms.py`
4. Update the template HTML
5. Update the view context

### Extending Templates

Use Django template inheritance:

```html
{% extends "subscriptions/dashboard.html" %}

{% block extra_css %}
    <style>
        /* Your custom styles */
    </style>
{% endblock %}

{% block content %}
    <!-- Your custom content -->
{% endblock %}
```

---

## Testing

### Running Tests

```bash
# Test all billing views
python manage.py test wasla.apps.subscriptions.tests

# Test specific view
python manage.py test wasla.apps.subscriptions.tests.BillingViewTests

# With coverage
coverage run --source='wasla.apps.subscriptions' manage.py test
coverage report
```

### Viewing Templates in Development

```bash
# Run development server
python manage.py runserver

# Visit templates
# - Dashboard: http://localhost:8000/billing/dashboard/
# - Invoices: http://localhost:8000/billing/invoices/
# - Payment: http://localhost:8000/billing/payment-method/
```

---

## Troubleshooting

### Templates Not Found

**Error:** `TemplateDoesNotExist: subscriptions/dashboard.html`

**Solution:**
1. Verify `wasla.apps.subscriptions` in `INSTALLED_APPS`
2. Check template path: `wasla/apps/subscriptions/templates/subscriptions/`
3. Run `python manage.py collectstatic`

### Missing Context Variables

**Error:** `Variable 'subscription' was not defined in template`

**Solution:**
1. Check view passes all required context
2. Verify variable names match template
3. Add debug print in view: `print(context)`

### CSRF Token Issues

**Error:** `Forbidden (403) CSRF verification failed`

**Solution:**
1. Add `{% csrf_token %}` to all forms
2. Verify middleware: `django.middleware.csrf.CsrfViewMiddleware`
3. Check template error messages

### Email Sending Not Working

**Error:** `SMTPException` or emails don't arrive

**Solution:**
1. Check EMAIL settings in settings.py
2. Test with: `python manage.py shell`
3. Run: `from django.core.mail import send_mail; send_mail(...)`
4. Check email logs/console

---

## Performance Optimization

### Database Queries

Use `select_related()` and `prefetch_related()`:

```python
invoices = Invoice.objects.select_related(
    'billing_cycle__subscription'
).prefetch_related(
    'dunning_attempts'
)
```

### Caching

Add caching for expensive computations:

```python
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)  # 5 minutes
def dashboard(request):
    # ...
    pass
```

### Pagination

All list views use pagination:

```python
paginator = Paginator(invoices, 10)  # 10 items per page
page_obj = paginator.get_page(request.GET.get('page'))
```

---

## Future Enhancements

1. **Invoice PDF Generation**
   - Use reportlab or weasyprint
   - Add download button to invoice detail

2. **Payment Retry UI**
   - Show dunning attempt history
   - Allow manual retry from admin

3. **Advanced Analytics**
   - Revenue charts
   - Churn analysis
   - Payment success rates

4. **Multi-language Support**
   - Add Django i18n
   - Translate templates

5. **Mobile App**
   - REST API already exists
   - Add mobile templates

---

## Support & Documentation

- **API Documentation:** See `BILLING_API_REFERENCE.md`
- **System Architecture:** See `BILLING_SYSTEM_INDEX.md`
- **Deployment:** See `BILLING_DEPLOYMENT_GUIDE.md`
- **Backend Code:** See `models_billing.py`, `services_billing.py`

---

**Integration Complete!** ✅

All templates, views, forms, and configuration are production-ready. Follow the installation steps above to activate the billing web interface.
