# Wasla Analytics - Quick Start Guide

## 5-Minute Integration Guide

### Step 1: Add Merchant Dashboard to Menu

Add link to merchant navigation:
```html
<a href="{% url 'analytics_web:merchant_dashboard' %}">📊 Dashboard</a>
```

### Step 2: Track Product Views

In your product detail view:

```python
from apps.analytics.signals import track_product_view
from django.shortcuts import render
from apps.catalog.models import Product

def product_detail(request, product_id):
    product = Product.objects.get(id=product_id)
    
    # Track the view
    track_product_view(
        store_id=product.store_id,
        product_id=product_id,
        user_id=request.user.id if request.user.is_authenticated else None,
        session_key=request.session.session_key
    )
    
    return render(request, 'product_detail.html', {'product': product})
```

### Step 3: Track Checkout Start

In your checkout view:

```python
from apps.analytics.signals import track_checkout_started
from apps.cart.models import Cart

def checkout_view(request):
    cart = Cart.objects.get(session_key=request.session.session_key)
    
    # Track checkout initiation
    track_checkout_started(
        store_id=cart.store_id,
        cart=cart,
        user_id=request.user.id if request.user.is_authenticated else None,
        session_key=request.session.session_key
    )
    
    # Rest of checkout flow...
    return render(request, 'checkout.html', {'cart': cart})
```

### Step 4: Done! ✅

The following events are **automatically tracked**:
- ✅ `add_to_cart` - When CartItem is created
- ✅ `purchase_completed` - When Order status becomes COMPLETED/PAID

---

## Available Dashboard URLs

### For Merchants (login required)

```
/analytics/dashboard/              - Interactive KPI dashboard
/analytics/merchant/kpi/            - JSON API: KPI data
/analytics/api/revenue-chart/       - JSON API: Revenue chart
/analytics/api/funnel/              - JSON API: Funnel analysis
/analytics/export/kpi.csv           - CSV: Export KPIs
/analytics/export/revenue.csv       - CSV: Export revenue
/analytics/export/funnel.csv        - CSV: Export funnel
```

### For Admins (is_staff required)

```
/admin/dashboard/                   - Executive dashboard
/admin/api/kpi/                     - JSON API: Admin KPIs
/admin/export/kpi.csv               - CSV: Export admin KPIs
```

---

## What Gets Tracked

### Auto-Tracked (No Code Needed)
- ✅ **Cart additions** - When item added to cart
- ✅ **Purchases** - When order completed

### Need to Track (Add 2 lines to your view)
- `product_view` - Add to product detail view
- `checkout_started` - Add to checkout view

---

## KPI Metrics Available

### Real-Time Metrics
| Metric | What It Measures |
|--------|------------------|
| **Revenue Today** | Today's total sales |
| **Orders Today** | Number of orders placed today |
| **Conversion Rate** | % of checkout starts → purchases |
| **Avg Order Value** | Average order amount |
| **Cart Abandonment** | % of carts not converted |
| **Low Stock Products** | Products with < 10 units |

### Trend Metrics (7d, 30d)
- Revenue over 7/30 days
- Order volume over 7/30 days
- Conversion funnel drop-off rates

---

## Example: Complete Integration

### Product View Tracking

```python
# apps/storefront/views.py
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from apps.catalog.models import Product
from apps.analytics.signals import track_product_view

@cache_page(60)  # Cache for 60 seconds
def product_detail(request, slug):
    """Product detail page with analytics tracking."""
    product = get_object_or_404(Product, slug=slug)
    
    # Track the view
    track_product_view(
        store_id=product.store_id,
        product_id=product.id,
        user_id=request.user.id if request.user.is_authenticated else None,
        session_key=request.session.session_key
    )
    
    # Get related products
    related = product.get_related_products()[:5]
    
    context = {
        'product': product,
        'related': related,
    }
    return render(request, 'storefront/product_detail.html', context)
```

### Checkout Tracking

```python
# apps/checkout/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.cart.models import Cart
from apps.analytics.signals import track_checkout_started

@login_required
def checkout_view(request):
    """Checkout page with analytics tracking."""
    try:
        cart = Cart.objects.get(session_key=request.session.session_key)
    except Cart.DoesNotExist:
        return redirect('storefront:home')
    
    # Track checkout initiation
    track_checkout_started(
        store_id=cart.store_id,
        cart=cart,
        user_id=request.user.id,
        session_key=request.session.session_key
    )
    
    # Payment form processing
    if request.method == 'POST':
        # Process payment
        order = cart.create_order()
        return redirect('checkout:success', order_id=order.id)
    
    context = {
        'cart': cart,
        'total': cart.get_total(),
    }
    return render(request, 'checkout/checkout.html', context)
```

### Auto-Track via Signals

```python
# No code needed! These are automatic:

# When CartItem is created:
from apps.cart.models import CartItem
cart_item = CartItem.objects.create(
    cart=cart,
    product=product,
    quantity=1
)
# → Automatically fires add_to_cart event

# When Order is completed:
order.status = Order.STATUS_COMPLETED
order.save()
# → Automatically fires purchase_completed event
```

---

## Checking the Dashboard

### View as Merchant

```python
# In Django shell
python manage.py shell

from apps.analytics.application.dashboard_services import MerchantDashboardService

kpi = MerchantDashboardService.get_merchant_kpis(store_id=1)

print(f"Revenue today: ${kpi.revenue_today}")
print(f"Orders today: {kpi.orders_today}")
print(f"Conversion: {kpi.conversion_rate:.2f}%")
print(f"Low stock: {len(kpi.low_stock_products)} products")
```

### View as Admin

```python
from apps.analytics.application.dashboard_services import AdminExecutiveDashboardService

kpi = AdminExecutiveDashboardService.get_admin_kpis()

print(f"GMV: ${kpi.gmv}")
print(f"Total stores: {kpi.active_stores}")
print(f"Churn: {kpi.churn_rate:.2f}%")

for merchant in kpi.top_merchants[:3]:
    print(f"  {merchant['name']}: ${merchant['revenue']}")
```

---

## Event Data Structure

All events are stored in `Event` model with:

```python
{
    "event_name": "product_view",         # or add_to_cart, checkout_started, purchase_completed
    "actor_type": "CUSTOMER",             # or ANON, MERCHANT, ADMIN
    "actor_id_hash": "sha256hash...",     # User ID (anonymized)
    "session_key_hash": "sha256hash...",  # Session (anonymized)
    "object_type": "PRODUCT",             # or CART, ORDER
    "object_id": "12345",                 # Product/Cart/Order ID
    "properties": {
        "store_id": 1,
        "quantity": 2,                    # For cart/order events
        "cart_value": "100.00"            # For checkout events
    },
    "occurred_at": "2024-02-28T15:30:00Z"
}
```

---

## CSV Export Examples

### Export Merchant KPIs
```bash
# Download in your browser
GET /analytics/export/kpi.csv

# Or via Python
import requests
response = requests.get('/analytics/export/kpi.csv')
with open('kpi.csv', 'wb') as f:
    f.write(response.content)
```

File contains:
```
Metric,Value
Revenue Today,1234.50
Orders Today,12
Revenue 7 Days,8675.50
...
```

### Export Revenue Chart
```bash
GET /analytics/export/revenue.csv?days=7

# File contents:
Date,Revenue,Orders,Average Order Value
2024-02-22,1234.50,10,123.45
2024-02-23,945.00,8,118.13
...
```

---

## Troubleshooting

### Dashboard Shows No Data

**Check 1**: Are there orders in the database?
```python
from apps.orders.models import Order
from django.utils import timezone

orders = Order.objects.filter(
    store_id=1,
    created_at__gte=timezone.now() - timedelta(days=1),
    status__in=['completed', 'paid']
)
print(f"Orders in last 24h: {orders.count()}")
```

**Check 2**: Is the cache expired?
```python
from django.core.cache import cache
cache.delete('merchant_kpis:1')  # Clear cache for store 1
```

### Events Not Being Tracked

**Check 1**: Are signals registered?
```python
# Should see apps.analytics.signals imported
from django.apps import apps
config = apps.get_app_config('analytics')
print(config)  # Should show AnalyticsConfig with ready() method
```

**Check 2**: Track manually and check Event table
```python
from apps.analytics.signals import track_product_view
from apps.analytics.models import Event

# Manually track
track_product_view(store_id=1, product_id=1, user_id=1)

# Check database
event = Event.objects.latest('id')
print(f"Last event: {event.event_name}")
```

---

## Performance Tips

1. **Cache is enabled by default** (5-10 min TTL)
   - Dashboards load in <500ms
   - No need to optimize further

2. **Event tracking is async-safe**
   - Can be wrapped in Celery task if needed:
   ```python
   @shared_task
   def track_view_async(store_id, product_id, user_id):
       track_product_view(store_id, product_id, user_id)
   ```

3. **CSV exports are streamed**
   - Can handle large datasets
   - No memory issues

---

## Next Steps

1. ✅ Analytics dashboard is ready to use
2. Add product view tracking to your product view
3. Add checkout tracking to your checkout view
4. Data will start flowing immediately
5. Visit `/analytics/dashboard/` to see results

**Time to implementation**: ~5 minutes per view

---

## Support & Examples

### Full Code Example: Product View

```python
# apps/storefront/views.py

from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from apps.catalog.models import Product
from apps.analytics.signals import track_product_view

@cache_page(60)
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    
    # Analytics: Track product view
    if request.user.is_authenticated:
        user_id = request.user.id
    else:
        user_id = None
    
    track_product_view(
        store_id=product.store_id,
        product_id=product.id,
        user_id=user_id,
        session_key=request.session.session_key
    )
    
    # ... rest of view
    return render(request, 'product.html', {'product': product})
```

### Full Code Example: Checkout

```python
# apps/checkout/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from apps.cart.models import Cart
from apps.analytics.signals import track_checkout_started

@login_required
def checkout_view(request):
    cart = Cart.objects.get(session_key=request.session.session_key)
    
    # Analytics: Track checkout initiation
    track_checkout_started(
        store_id=cart.store_id,
        cart=cart,
        user_id=request.user.id,
        session_key=request.session.session_key
    )
    
    # ... checkout processing
    if request.method == 'POST':
        order = process_payment(cart)
        # purchase_completed event fires automatically on Order.save()
        return redirect('success')
    
    return render(request, 'checkout.html', {'cart': cart})
```

---

**🎉 Analytics dashboard is ready to deploy!**

Add 2 lines to your views, and start tracking real-time KPIs immediately.
