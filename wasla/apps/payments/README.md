# Payments Module | موديول المدفوعات (Payments)

**AR:** تسجيل ومعالجة المدفوعات المرتبطة بالطلبات (MVP).  
**EN:** Records and processes order payments (MVP).

---

## Key model | أهم جدول

**AR/EN:** `apps/payments/models.py::Payment`
- Links to `orders.Order`
- `status`: pending/success/failed
- Stores gateway reference if needed

---

## Services | الخدمات

**AR/EN:** `apps/payments/services/`:
- `payment_service.py`
- `gateway_service.py` (gateway abstraction placeholder)

---

## API | واجهة API

**AR/EN:** See `apps/payments/urls.py` and `apps/payments/views/api.py`.

