# Catalog Module | موديول الكتالوج (Catalog)

**AR:** مسؤول عن المنتجات، التصنيفات، والمخزون بشكل مبسّط (MVP).  
**EN:** Owns products, categories, and basic inventory (MVP).

---

## Key models | أهم الجداول

**AR/EN (see `apps/catalog/models.py`):**
- `Category` (store-scoped via `store_id`)
- `Product` (unique per store by `(store_id, sku)`)
- `Inventory` (one-to-one with `Product`)

---

## Services | الخدمات

**AR/EN:** `apps/catalog/services/` provides basic operations:
- `product_service.py`
- `inventory_service.py`

---

## Tenant isolation | عزل المتجر

**AR:** كل الاستعلامات/الخدمات يجب أن تقيّد بـ `store_id` (Tenant column).  
**EN:** Queries/services should be scoped by `store_id`.

