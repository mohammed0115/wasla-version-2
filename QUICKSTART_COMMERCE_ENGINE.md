# Commerce Engine Quick Start

## Pre-Deployment Checklist (5 mins)

- [ ] Review migrations in `apps/coupons/migrations/0001_initial.py`
- [ ] Review migrations in `apps/cart/migrations/0003_cart_abandoned_tracking.py`
- [ ] Review migrations in `apps/shipping/migrations/0002_shipping_zones_and_rates.py`

## Deployment Steps (10-15 mins)

### Step 1: Run Migrations
```bash
cd /home/mohamed/Desktop/wasla-version-2
source .venv/bin/activate

python manage.py makemigrations
python manage.py migrate
```

Output should show:
```
Running migrations:
  Applying coupons.0001_initial... OK
  Applying cart.0003_cart_abandoned_tracking... OK
  Applying shipping.0002_shipping_zones_and_rates... OK
```

### Step 2: Create Test Data
```bash
python manage.py shell
```

```python
from apps.coupons.models import Coupon
from apps.stores.models import Store
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

# Get a store
store = Store.objects.first()

# Create test coupon
coupon = Coupon.objects.create(
    store=store,
    code="SAVE20",
    discount_type="percentage",
    discount_value=Decimal("20.00"),
    start_date=timezone.now(),
    end_date=timezone.now() + timedelta(days=30),
    is_active=True,
)

print(f"Created coupon: {coupon.code}")

# Create test shipping zone
from apps.shipping.models import ShippingZone
zone = ShippingZone.objects.create(
    store=store,
    name="Saudi Arabia",
    countries="SA",
    is_active=True,
)

# Create test shipping rate
from apps.shipping.models import ShippingRate
rate = ShippingRate.objects.create(
    zone=zone,
    name="Standard Shipping",
    rate_type="flat",
    base_rate=Decimal("50.00"),
)

print(f"Created zone: {zone.name}")
print(f"Created rate: {rate.name}")
```

### Step 3: Run Tests
```bash
python manage.py test apps.coupons --verbosity=2
```

Expected output:
```
test_coupon_creation (apps.coupons.tests.CouponModelTest) ... ok
test_coupon_percentage_discount (apps.coupons.tests.CouponModelTest) ... ok
test_coupon_expiry (apps.coupons.tests.CouponModelTest) ... ok
```

### Step 4: Test Coupon API
```bash
# Test coupon validation
curl -X POST http://localhost:8000/api/coupons/validate/ \
  -d "code=SAVE20&subtotal=100.00&store_id=1"

# Expected response:
# {
#   "valid": true,
#   "code": "SAVE20",
#   "discount_amount": "20.00",
#   "final_total": "80.00"
# }
```

### Step 5: Test Abandoned Cart Command
```bash
# Dry run to preview
python manage.py process_abandoned_carts --dry-run

# With actual processing
python manage.py process_abandoned_carts --hours 24 --send-reminders
```

## Verification

### Check Coupons in Admin
```
1. Go to http://localhost:8000/admin/
2. Navigate to "Coupons" → "Coupons"
3. Verify "SAVE20" coupon exists
4. Check Usage: 0/Unlimited
```

### Check Shipping in Admin
```
1. Go to http://localhost:8000/admin/
2. Navigate to "Shipping" → "Shipping Zones"
3. Verify "Saudi Arabia" zone exists
4. Click to see rates
5. Verify "Standard Shipping" rate exists
```

### Check Cart Model
```bash
python manage.py shell
from apps.cart.models import Cart

# Check for new fields
cart = Cart.objects.first()
if cart:
    print(f"abandoned_at: {cart.abandoned_at}")
    print(f"reminder_sent: {cart.reminder_sent}")
    print(f"is_abandoned: {cart.is_abandoned()}")
```

## Integration Points

### Add Coupon to Checkout

In your checkout view:

```python
from apps.coupons.services import CouponValidationService
from decimal import Decimal

# Get coupon code from request
coupon_code = request.POST.get('coupon_code')

if coupon_code:
    # Find coupon
    coupon = Coupon.objects.get(store_id=store_id, code=coupon_code)
    
    # Validate
    service = CouponValidationService()
    is_valid, error = service.validate_coupon(
        coupon=coupon,
        customer=request.user.customer if request.user.is_authenticated else None,
        subtotal=order.subtotal,
    )
    
    if is_valid:
        # Calculate discount
        discount_amount = coupon.calculate_discount(order.subtotal)
        
        # Apply to order
        order.coupon = coupon
        order.discount_amount = discount_amount
        order.total_amount = order.subtotal - discount_amount
        
        # Log usage
        service.apply_coupon(coupon, order, discount_amount)
```

### Add Shipping Calculation

In your checkout view:

```python
from apps.shipping.services import ShippingCalculationService
from decimal import Decimal

service = ShippingCalculationService()

# Calculate shipping
shipping_cost, rate, zone = service.calculate_shipping_cost(
    store=store,
    country_code=request.POST.get('country'),
    weight=Decimal("2.5"),  # kg
    order_total=order.subtotal - order.discount_amount,
)

if shipping_cost is None:
    messages.error(request, "Shipping not available to this location")
else:
    order.shipping_cost = shipping_cost
    order.total_amount += shipping_cost
```

### Schedule Abandoned Cart Task

Set up in Celery Beat (`config/settings.py`):

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'process-abandoned-carts': {
        'task': 'apps.cart.tasks.process_abandoned_carts',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
        'args': (),
    },
}
```

Or run manually daily:

```bash
# Add to cron
0 6 * * * cd /path/to/wasla && python manage.py process_abandoned_carts --send-reminders
```

## Troubleshooting

### Migration Fails

```bash
# Check migration status
python manage.py showmigrations

# If needed, fake migration (careful!)
python manage.py migrate apps.coupons --fake
```

### Coupon API Returns 400

```bash
# Check parameters
# Required: code, subtotal, store_id
# Make sure all are provided

curl -X POST http://localhost:8000/api/coupons/validate/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "code=SAVE20&subtotal=100.00&store_id=1"
```

### Emails Not Sending

```bash
# Check email settings
python manage.py shell
from apps.emails.models import TenantEmailSettings

settings = TenantEmailSettings.objects.first()
print(f"Provider: {settings.provider}")
print(f"From Email: {settings.from_email}")
print(f"Enabled: {settings.is_enabled}")

# Check email logs
from apps.emails.models import EmailLog
logs = EmailLog.objects.all().order_by('-created_at')[:5]
for log in logs:
    print(f"{log.recipient}: {log.status}")
```

## Files to Review Before Deployment

1. **Coupon Model** → `apps/coupons/models.py` (150 lines)
2. **Coupon Service** → `apps/coupons/services.py` (200 lines)
3. **Shipping Models** → `apps/shipping/models.py` (200 lines added)
4. **Shipping Service** → `apps/shipping/services.py` (200 lines added)
5. **Cart Model Changes** → `apps/cart/models.py` (30 lines added)
6. **Order Emails** → `apps/orders/email_templates.py` (450 lines)
7. **Order Signals** → `apps/orders/email_signals.py` (200 lines)

## Rollback Plan

If issues occur:

```bash
# Rollback migrations
python manage.py migrate cart 0002  # Previous cart migration
python manage.py migrate coupons zero  # Remove coupons app
python manage.py migrate shipping 0001  # Previous shipping migration

# Remove coupons from INSTALLED_APPS in settings.py
# Restart application
```

## Performance Validation

After deployment, check performance:

```bash
# Check slow queries
python manage.py shell
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as context:
    from apps.coupons.models import Coupon
    coupons = Coupon.objects.select_related('store').filter(is_active=True)
    list(coupons)

print(f"Queries: {len(context)}")
for q in context:
    print(f"  Time: {q['time']}s - {q['sql'][:100]}")
```

## Success Indicators

✅ **Deployment successful when:**
1. All migrations apply without errors
2. All tests pass
3. Coupon API returns valid JSON
4. Coupons appear in admin
5. Shipping zones configured
6. Abandoned cart command runs without errors
7. Order emails send (check SMTP logs)

---

**Estimated time: 15-30 minutes for full deployment**

See `COMMERCE_ENGINE_GUIDE.md` for detailed documentation.
