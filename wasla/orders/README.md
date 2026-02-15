# Orders Module | موديول الطلبات (Orders)

**AR:** إدارة الطلبات وبنود الطلب وحالات الطلب (MVP).  
**EN:** Manages orders, order items, and basic order statuses (MVP).

---

## Key models | أهم الجداول

**AR/EN (see `apps/orders/models.py`):**
- `Order` (store-scoped via `store_id`, with status/state)
- `OrderItem` (belongs to an `Order`)

---

## Services | الخدمات

**AR/EN:** `apps/orders/services/` contains:
- `order_service.py` (create/list)
- `order_lifecycle_service.py` (status transitions)
- `pricing_service.py` (pricing helper)

---

## API | واجهة API

**AR/EN:** See `apps/orders/urls.py` and `apps/orders/views/api.py`.

