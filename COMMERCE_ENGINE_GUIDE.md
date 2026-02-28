# Commerce Engine Upgrade - Features & Integration Guide

## Overview

Wasla has been upgraded to market-ready commerce level with 5 critical features:

1. **Coupons Engine** - Discount management system
2. **Shipping Zones** - Geographic shipping management
3. **Carrier Integration** - Abstraction layer for shipping carriers
4. **Order Confirmation Emails** - Post-purchase communications
5. **Abandoned Cart Tracking** - Cart recovery system

---

## 1. Coupons Engine

### Features

- ✅ **Discount Types**: Percentage (%) and Fixed Amount discounts
- ✅ **Usage Limits**: Global limit and per-customer limit
- ✅ **Expiry Management**: Start and end dates
- ✅ **Minimum Purchase**: Enforce minimum order value
- ✅ **Max Discount Cap**: Cap percentage discounts (e.g., max 50 SAR)
- ✅ **Per-Store Scope**: Each store manages own coupons
- ✅ **Analytics**: Track usage and effectiveness

### Models

**Coupon**
```python
- store: ForeignKey(Store)
- code: CharField (unique per store)
- discount_type: CharField (PERCENTAGE or FIXED)
- discount_value: DecimalField
- max_discount_amount: DecimalField (optional)
- minimum_purchase_amount: DecimalField
- usage_limit: IntegerField (optional)
- usage_limit_per_customer: IntegerField (default: 1)
- times_used: IntegerField (auto-tracked)
- is_active: BooleanField
- start_date, end_date: DateTimeField
- created_by: CharField
```

**CouponUsageLog**
```python
- coupon: ForeignKey(Coupon)
- customer: ForeignKey(Customer, null=True)
- order: ForeignKey(Order)
- discount_applied: DecimalField
- used_at: DateTimeField
```

### Services

**CouponValidationService**
```python
validate_coupon(coupon, customer=None, subtotal=0)
  → (is_valid, error_message)
  
apply_coupon(coupon, order, discount_amount)
  → CouponUsageLog instance
  
revoke_coupon_usage(order)
  → Removes usage log and decrements counter
```

**CouponAnalyticsService**
```python
get_coupon_stats(coupon)
  → {total_uses, total_discount, usage_percentage, ...}
  
get_store_stats(store)
  → {total_coupons, active_coupons, total_discount, total_uses}
```

### API Endpoints

**POST /api/coupons/validate/**
```json
Request:
{
  "code": "SAVE20",
  "subtotal": "100.00",
  "store_id": 1
}

Response (Valid):
{
  "valid": true,
  "code": "SAVE20",
  "discount_type": "percentage",
  "discount_value": "20.00",
  "discount_amount": "20.00",
  "final_total": "80.00",
  "message": "SAVE20 applied successfully!"
}

Response (Invalid):
{
  "valid": false,
  "error": "This coupon has expired"
}
```

**GET /api/coupons/{code}/?store_id=1**
```json
Response:
{
  "code": "SAVE20",
  "discount_type": "Percentage Discount (%)",
  "discount_value": "20.00",
  "minimum_purchase_amount": "50.00",
  "max_discount_amount": "50.00",
  "description": "Save 20% on orders over 50 SAR",
  "is_active": true
}
```

### Admin Interface

Access at `/admin/coupons/coupon/`

- List view with status badges (Active, Expired, Disabled, Pending)
- Usage tracking (2/10 = 20%)
- Inline discount display (20% or 50 SAR)
- Prepopulated slug field
- Search by code and description

### Checkout Integration

**In your checkout view:**

```python
from apps.coupons.services import CouponValidationService

service = CouponValidationService()

# Validate coupon
is_valid, error = service.validate_coupon(
    coupon=coupon,
    customer=request.user.customer,
    subtotal=order.subtotal,
)

if is_valid:
    # Calculate discount
    discount_amount = coupon.calculate_discount(order.subtotal)
    
    # Apply to order
    order.discount_amount = discount_amount
    order.coupon = coupon
    
    # Log usage
    service.apply_coupon(coupon, order, discount_amount)
```

---

## 2. Shipping Zones & Rates

### Features

- ✅ **Geographic Zones**: Country-based shipping zones (SA, GCC, International)
- ✅ **Multiple Rates**: Different rates per zone (Standard, Express)
- ✅ **Flat Rate**: Fixed shipping cost
- ✅ **Weight-Based**: Per-kg pricing (e.g., 5 SAR/kg)
- ✅ **Free Shipping**: Threshold-based (e.g., free over 100 SAR)
- ✅ **Priority System**: Zone and rate matching by priority

### Models

**ShippingZone**
```python
- store: ForeignKey(Store)
- name: CharField (e.g., "GCC Countries")
- description: TextField
- countries: CharField (comma-separated codes: "SA,AE,KW,QA")
- is_active: BooleanField
- priority: IntegerField (higher = matched first)
- created_at, updated_at: DateTimeField
```

**ShippingRate**
```python
- zone: ForeignKey(ShippingZone)
- name: CharField (e.g., "Standard", "Express")
- rate_type: CharField (FLAT or WEIGHT)
- base_rate: DecimalField (cost or cost/kg)
- min_weight: DecimalField (minimum kg)
- max_weight: DecimalField (maximum kg, optional)
- free_shipping_threshold: DecimalField (e.g., 100 SAR)
- is_active: BooleanField
- priority: IntegerField
- estimated_days: IntegerField (e.g., 3 days)
- created_at, updated_at: DateTimeField
```

### Services

**ShippingCalculationService**
```python
find_zone_for_country(store, country_code)
  → ShippingZone or None
  
calculate_shipping_cost(store, country_code, weight, order_total)
  → (shipping_cost, rate, zone)
  
get_available_rates_for_country(store, country_code)
  → QuerySet of ShippingRate
```

### Usage Example

```python
from apps.shipping.services import ShippingCalculationService

service = ShippingCalculationService()

# Find zone for customer's country
zone = service.find_zone_for_country(store, "SA")

# Calculate shipping
cost, rate, zone = service.calculate_shipping_cost(
    store=store,
    country_code="SA",
    weight=2.5,  # kg
    order_total=Decimal("150.00"),
)

if cost is not None:
    order.shipping_cost = cost
    order.shipping_rate = rate
else:
    # No shipping available
    show_error("Shipping not available to this country")
```

### Admin Interface

**ShippingZone Admin** (`/admin/shipping/shippingzone/`)
- List with status (Active/Inactive)
- Countries CSV editor
- Priority ordering

**ShippingRate Admin** (`/admin/shipping/shippingrate/`)
- Weight range configuration
- Flat vs Weight-based options
- Free shipping thresholds
- Estimated delivery display

---

## 3. Carrier Integration Abstraction

### Features

- ✅ **Interface-Based Design**: CarrierInterface abstract class
- ✅ **Aramex Adapter**: Stub implementation with API placeholder
- ✅ **SMSA Adapter**: Stub implementation with API placeholder
- ✅ **Label Generation**: Placeholder for PDF label creation
- ✅ **Tracking Status**: Lookup tracking updates
- ✅ **Shipment Cancellation**: Revoke shipments

### Architecture

**CarrierInterface** (Abstract)
```python
class CarrierInterface:
    create_shipment(shipment, order) 
      → {"tracking_number": "...", "label_url": "...", "status": "pending"}
    
    get_tracking_status(tracking_number)
      → {"tracking_number": "...", "status": "in_transit", "location": "..."}
    
    generate_label(tracking_number)
      → {"label_url": "...", "format": "pdf"}
    
    cancel_shipment(tracking_number)
      → {"status": "cancelled"}
```

**Aramex Adapter**
```python
AramexAdapter(
    api_key="...",
    account_number="...",
    entity_type="SMB"
)
```

**SMSA Express Adapter**
```python
SMSAAdapter(
    api_key="...",
    customer_code="..."
)
```

**CarrierFactory**
```python
carrier = CarrierFactory.create_carrier(
    "aramex",
    api_key="xxx",
    account_number="yyy"
)

result = carrier.create_shipment(shipment, order)
```

### Implementation Hooks

When payment succeeds:
```python
from apps.shipping.services import CarrierFactory

# Create shipment
shipment = Shipment.objects.create(
    order=order,
    carrier="aramex",
)

# Get carrier
carrier = CarrierFactory.create_carrier(
    "aramex",
    api_key=settings.ARAMEX_API_KEY,
    account_number=settings.ARAMEX_ACCOUNT,
)

# Create shipment with carrier
result = carrier.create_shipment(shipment, order)
shipment.tracking_number = result["tracking_number"]
shipment.save()
```

---

## 4. Order Confirmation Emails

### Features

- ✅ **Auto-Trigger**: Sent after payment success
- ✅ **HTML Template**: Professional branded template
- ✅ **VAT Breakdown**: Shows VAT amount separately
- ✅ **Order Status**: Display current status
- ✅ **Product Details**: Item listing with prices
- ✅ **Shipping Info**: Address and carrier details
- ✅ **Tracking Link**: Link to order tracking

### Email Templates

**Order Confirmation Email** (`apps/orders/email_templates.py`)
- Header with order number
- Order status badge
- Item listing table (Product, Qty, Price, Total)
- VAT breakdown (shows 15% VAT calculation)
- Shipping address display
- Order total with VAT
- Next steps guidance
- Contact information

**Order Shipped Email**
- Tracking number highlight
- Carrier information
- Tracking link
- Status update

### Signal Handler

```python
# apps/orders/email_signals.py

@receiver(post_save, sender=Order)
def send_order_confirmation_email(sender, instance, created, **kwargs):
    """Send confirmation email after payment"""
    if instance.status in ['processing', 'confirmed']:
        send_order_confirmation(instance)

@receiver(post_save, sender=Shipment)
def send_shipment_notification_email(sender, instance, created, **kwargs):
    """Send shipping notification"""
    if created and instance.tracking_number:
        send_shipment_email(instance)
```

### HTML Template Features

```html
- Professional gradient header
- VAT calculation section
- Item table with columns: Product, Qty, Unit Price, Total
- Shipping address block
- Order action buttons (Track Order)
- Contact information with store details
- Footer with store branding
- Responsive design (works on mobile)
```

### Customization

To customize the email template:

```python
# In your store-specific app
from apps.orders.email_templates import render_order_confirmation_email

def my_custom_template(order):
    # Customize the default template
    html = render_order_confirmation_email(order)
    # Make changes...
    return html
```

---

## 5. Abandoned Cart Tracking

### Features

- ✅ **TTL Tracking**: Marks carts abandoned after 24h inactivity
- ✅ **Reminder Emails**: Send recovery emails to customers
- ✅ **Admin Reporting**: Dashboard stats on abandoned carts
- ✅ **Recovery Links**: Send personalized recovery URLs
- ✅ **Value Tracking**: Total abandoned cart value

### Model Extension

**Cart Model** additions:
```python
- abandoned_at: DateTimeField (when marked abandoned)
- reminder_sent: BooleanField (track if email sent)
- reminder_sent_at: DateTimeField (when reminder sent)

Methods:
- is_abandoned(hours=24): bool
- mark_abandoned(): None
- get_item_value(): Decimal
- is_empty(): bool
```

### Services

**AbandonedCartService**
```python
get_abandoned_carts(store=None, hours=24)
  → QuerySet of abandoned carts
  
get_abandoned_carts_for_reminder(store=None, hours=24)
  → QuerySet of carts ready for reminder
  
get_abandoned_cart_stats(store=None)
  → {
      total_abandoned_carts: 42,
      total_abandoned_value: 5000.00,
      average_cart_value: 119.05,
    }
  
mark_reminder_sent(cart): None

recover_cart(cart): None
  → Resets abandoned status
```

**AbandonedCartRecoveryEmailService**
```python
render_recovery_email(cart) → HTML string

send_recovery_email(cart) → bool (success)
```

### Management Command

**Process Abandoned Carts:**

```bash
# Mark carts as abandoned (24h inactivity)
python manage.py process_abandoned_carts

# Mark and send reminders
python manage.py process_abandoned_carts --send-reminders

# For specific store
python manage.py process_abandoned_carts --store-id=1 --send-reminders

# Dry run (preview without changes)
python manage.py process_abandoned_carts --dry-run
```

### Admin Dashboard

Add to `/admin/`:

```python
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'store_id', 'is_empty', 'abandoned_at', 'reminder_sent']
    list_filter = ['abandoned_at', 'reminder_sent', 'store_id']
    search_fields = ['user__email', 'session_key']
    readonly_fields = ['created_at', 'updated_at']
```

### Scheduling

Set up periodic task in Celery Beat:

```python
# config/settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'process-abandoned-carts': {
        'task': 'apps.cart.tasks.process_abandoned_carts',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    },
}
```

Or use a Celery task:

```python
# apps/cart/tasks.py
from celery import shared_task
from apps.cart.services import AbandonedCartService, AbandonedCartRecoveryEmailService

@shared_task
def process_abandoned_carts():
    """Send reminder emails for abandoned carts"""
    carts = AbandonedCartService.get_abandoned_carts_for_reminder()
    
    for cart in carts:
        AbandonedCartRecoveryEmailService.send_recovery_email(cart)
```

---

## Integration Checklist

### Before Launch

- [ ] Run migrations:
  ```bash
  python manage.py makemigrations
  python manage.py migrate
  ```

- [ ] Create test coupons in admin:
  - Test percentage discount
  - Test fixed discount
  - Test with usage limits
  - Test expired coupons

- [ ] Set up shipping:
  - [ ] Create shipping zones (SA, GCC, International)
  - [ ] Add shipping rates per zone
  - [ ] Test shipping cost calculation

- [ ] Configure carriers:
  - [ ] Set Aramex credentials in settings
  - [ ] Set SMSA credentials in settings
  - [ ] Test carrier integration

- [ ] Test emails:
  - [ ] Place test order
  - [ ] Verify confirmation email received
  - [ ] Check VAT breakdown
  - [ ] Test shipment email

- [ ] Abandoned cart setup:
  - [ ] Create test carts
  - [ ] Run management command
  - [ ] Verify reminder emails

- [ ] Security review:
  - [ ] CSRF protection on coupon endpoints
  - [ ] Rate limiting on coupon validation
  - [ ] Email rate limiting

### Database Migrations

```bash
# Create migrations for new models
python manage.py makemigrations coupons cart

# Apply migrations
python manage.py migrate

# Verify
python manage.py showmigrations
```

### Settings Configuration

Add to `config/settings.py`:

```python
# Shipping Carriers
ARAMEX_API_KEY = os.getenv("ARAMEX_API_KEY", "")
ARAMEX_ACCOUNT_NUMBER = os.getenv("ARAMEX_ACCOUNT_NUMBER", "")
ARAMEX_ENTITY_TYPE = os.getenv("ARAMEX_ENTITY_TYPE", "SMB")

SMSA_API_KEY = os.getenv("SMSA_API_KEY", "")
SMSA_CUSTOMER_CODE = os.getenv("SMSA_CUSTOMER_CODE", "")

# Abandoned Cart
ABANDONED_CART_THRESHOLD_HOURS = int(os.getenv("ABANDONED_CART_THRESHOLD_HOURS", "24"))
ABANDONED_CART_REMINDER_HOURS = int(os.getenv("ABANDONED_CART_REMINDER_HOURS", "24"))
```

### URLs Integration

Add to `config/urls.py`:

```python
urlpatterns = [
    # ... existing patterns
    path("", include(("apps.coupons.urls", "coupons"), namespace="coupons")),
]
```

---

## Testing

### Run Tests

```bash
# All tests
python manage.py test apps.coupons apps.cart apps.orders apps.shipping

# Specific test
python manage.py test apps.coupons.tests.CouponModelTest.test_coupon_creation

# With coverage
coverage run --source='apps' manage.py test
coverage report
```

### Test Cases Included

- ✅ Coupon creation and validation
- ✅ Percentage and fixed discounts
- ✅ Usage limits and expiry
- ✅ Shipping zone matching
- ✅ Weight-based calculations
- ✅ Abandoned cart detection
- ✅ Email rendering

---

## Backward Compatibility

✅ **All existing functionality preserved:**
- No changes to core Order model (coupon fields are optional)
- Cart model extended (new fields are optional with defaults)
- No breaking changes to API

✅ **Gradual rollout:**
1. Deploy coupons separately
2. Enable shipping in admin (optional feature)
3. Enable emails after testing
4. Set up abandoned cart tracking

---

## Performance Considerations

### Database Indexes

- ShippingZone: (store, is_active), (priority)
- ShippingRate: (zone, is_active), (rate_type, priority)
- Coupon: (store, code), (store, is_active), (end_date)
- CouponUsageLog: (coupon, customer), (used_at)
- Cart: (store, updated_at), (abandoned_at), (reminder_sent)

### Query Optimization

```python
# Use select_related for foreign keys
coupons = Coupon.objects.select_related('store')

# Use prefetch_related for many-to-many/reverse FK
carts = Cart.objects.prefetch_related('items__product')

# Use only() to limit columns
coupons = Coupon.objects.only('code', 'discount_value', 'is_active')
```

### Caching Recommendations

```python
from django.core.cache import cache

# Cache active coupons per store
def get_active_coupons(store_id):
    key = f"coupons:store:{store_id}:active"
    coupons = cache.get(key)
    if not coupons:
        coupons = Coupon.objects.filter(
            store_id=store_id,
            is_active=True,
        ).values_list('code', flat=True)
        cache.set(key, coupons, 3600)  # 1 hour
    return coupons
```

---

## Support & Maintenance

### Regular Tasks

- **Weekly**: Review coupon analytics, check abandoned cart stats
- **Monthly**: Audit coupon usage, update carrier credentials
- **Quarterly**: Clean up expired coupons, analyze email delivery

### Troubleshooting

**Coupons not validating:**
- Check is_active flag
- Verify dates (start_date ≤ now ≤ end_date)
- Check minimum purchase amount
- Verify usage limits

**Emails not sending:**
- Check email settings in database (TenantEmailSettings)
- Verify SMTP credentials
- Check Celery task queue
- Review email logs in admin

**Shipping not calculating:**
- Verify zones are active
- Check country codes match
- Ensure rates are configured
- Check weight ranges

---

## Next Steps

1. Run migrations
2. Create test data
3. Configure settings
4. Test all features
5. Deploy to staging
6. QA testing
7. Production rollout

**Estimated implementation time: 2-4 hours deployment + 1 day QA**
