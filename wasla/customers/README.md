# Customers Module | موديول العملاء (Customers)

**AR:** إدارة عملاء المتجر وعناوينهم (MVP).  
**EN:** Manages store customers and their addresses (MVP).

---

## Key models | أهم الجداول

**AR/EN (see `apps/customers/models.py`):**
- `Customer` (unique per store by `(store_id, email)`)
- `Address` (belongs to a `Customer`)

---

## API | واجهة API

**AR/EN:** See `apps/customers/urls.py` and `apps/customers/views/api.py`:
- Create customer endpoint under `api/`.

---

## Services | الخدمات

**AR/EN:** `apps/customers/services/` contains basic customer/address operations.

