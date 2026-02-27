# Product Variants - Quick Reference Card

## 📋 Models at a Glance

### ProductOptionGroup
```python
store          # FK → Store (tenant isolation)
name           # str (unique per store)
is_required    # bool (customer must select)
position       # int (display order)
```

### ProductOption
```python
group          # FK → ProductOptionGroup
value          # str (unique per group)
               # e.g., "Red", "S", "Leather"
```

### ProductVariant
```python
product        # FK → Product
sku            # str (unique per store) ✅ CRITICAL
price_override # decimal (nullable) → uses product.price if NULL
stock_quantity # int (inventory for this variant)
is_active      # bool (enable/disable variant)
options        # M2M → ProductOption
store_id       # int (auto-synced from product)
```

### StockMovement (Enhanced)
```python
product        # FK → Product
variant        # FK → ProductVariant (nullable) ✅ NEW
movement_type  # str ("IN", "OUT", "ADJUST")
quantity       # int
reason         # str
created_at     # datetime
```

---

## 🚀 Common Operations

### Create Product with Variants
```python
from apps.catalog.services.variant_service import ProductConfigurationService

product = ProductConfigurationService.upsert_product_with_variants(
    store=store,
    payload={
        "sku": "SHIRT-001",
        "name": "T-Shirt",
        "price": "100.00",
        "option_groups": [
            {
                "name": "Size",
                "is_required": True,
                "position": 1,
                "options": [
                    {"value": "S"},
                    {"value": "M"},
                    {"value": "L"}
                ]
            }
        ],
        "variants": [
            {
                "sku": "SHIRT-001-S",
                "stock_quantity": 10,
                "is_active": True,
                "options": [{"group": "Size", "value": "S"}]
            }
        ]
    }
)
```

### Resolve Product/Variant Price
```python
from apps.catalog.services.variant_service import VariantPricingService

# With variant override
price = VariantPricingService.resolve_price(
    product=product,
    variant=variant  # If variant.price_override is set, uses that
)

# Without variant (base price)
price = VariantPricingService.resolve_price(
    product=product,
    variant=None  # Uses product.price
)
```

### Validate Checkout Stock
```python
from apps.catalog.services.variant_service import ProductVariantService

# Raises ValueError if:
# - Variant stock < requested quantity
# - Variant is inactive
# - Store mismatch
# - Quantity is 0
try:
    ProductVariantService.assert_checkout_stock(
        store_id=store.id,
        items=[
            {"product": product, "variant": variant, "quantity": 2}
        ]
    )
except ValueError as e:
    print(f"Checkout error: {e}")
```

### Get Variant(s)
```python
# Single variant
variant = ProductVariantService.get_variant_for_store(
    store_id=store.id,
    product_id=product.id,
    variant_id=variant_id
)

# Multiple variants (efficient)
variant_map = ProductVariantService.get_variants_map(
    store_id=store.id,
    variant_ids=[1, 2, 3, 4, 5]
)
```

---

## 🔗 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/catalog/products/` | Create product with variants |
| PUT | `/api/catalog/products/<id>/` | Update product and variants |
| PATCH | `/api/catalog/products/<id>/` | Partial product update |
| GET | `/api/catalog/products/<id>/price/?variant_id=<id>` | Resolve price |
| GET | `/api/catalog/variants/<id>/stock/` | Check variant stock |
| GET | `/api/merchants/inventory/movements/` | List stock movements |

---

## 📊 Example: 2D Product Matrix (Color × Size)

```
Product: "T-Shirt" (Base Price: $80)
├── Color: Black
│   ├── Size: S → SKU: SHIRT-BLACK-S, Stock: 10, Price: $80
│   ├── Size: M → SKU: SHIRT-BLACK-M, Stock: 20, Price: $80
│   └── Size: L → SKU: SHIRT-BLACK-L, Stock: 5, Price: $90 (override)
└── Color: White
    ├── Size: S → SKU: SHIRT-WHITE-S, Stock: 15, Price: $80
    ├── Size: M → SKU: SHIRT-WHITE-M, Stock: 25, Price: $80
    └── Size: L → SKU: SHIRT-WHITE-L, Stock: 8, Price: $90 (override)

Total variants: 6
```

---

## ⚠️ Common Mistakes to Avoid

### ❌ Don't: Duplicate SKUs
```python
# ❌ WRONG - Same SKU in same store
variants = [
    {"sku": "SHIRT-001", "stock_quantity": 10},
    {"sku": "SHIRT-001", "stock_quantity": 20},  # ERROR!
]
```

### ✅ Do: Unique SKUs Per Store
```python
# ✅ CORRECT - Unique SKUs per store
variants = [
    {"sku": "SHIRT-001-S", "stock_quantity": 10},
    {"sku": "SHIRT-001-M", "stock_quantity": 20},
    {"sku": "SHIRT-001-L", "stock_quantity": 5},
]
```

---

### ❌ Don't: Manually Check Stock
```python
# ❌ WRONG - Don't do this
if variant.stock_quantity >= quantity:
    allow_checkout()
```

### ✅ Do: Use Service Validation
```python
# ✅ CORRECT - Use the service
try:
    ProductVariantService.assert_checkout_stock(
        store_id=store.id,
        items=cart_items
    )
except ValueError:
    block_checkout()
```

---

### ❌ Don't: Compare Prices Directly
```python
# ❌ WRONG - Ignores price override
if product.price > 100:
    apply_discount()
```

### ✅ Do: Use Price Service
```python
# ✅ CORRECT - Handles override
price = VariantPricingService.resolve_price(
    product=product,
    variant=variant
)
if price > 100:
    apply_discount()
```

---

## 🧪 Testing Checklist

- [ ] Create product with variants
- [ ] Verify variant creation
- [ ] Test price resolution (base & override)
- [ ] Test checkout stock validation
- [ ] Verify inactive variant blocking
- [ ] Test stock = 0 checkout prevention
- [ ] Verify multi-tenant isolation
- [ ] Test unique SKU constraint
- [ ] Test bulk variant retrieval
- [ ] Verify API endpoints respond correctly

---

## 🔐 Permissions Required

```python
@require_permission("catalog.create_product")
def create_product(): ...

@require_permission("catalog.update_product")
def update_product(): ...
```

---

## 💾 Database Indexes

```sql
-- Option Group queries
CREATE INDEX idx_option_group_store_position 
ON catalog_productoptiongroup(store_id, position);

-- Active variant queries
CREATE INDEX idx_variant_product_active 
ON catalog_productvariant(product_id, is_active);

-- Store + Product queries
CREATE INDEX idx_variant_store_product 
ON catalog_productvariant(store_id, product_id);

-- Stock movement history
CREATE INDEX idx_stock_movement_store_date 
ON catalog_stockmovement(store_id, created_at);
```

---

## 🎯 Performance Tips

### ✅ Prefetch Options
```python
variants = product.variants.prefetch_related('options').all()
# Single query, no N+1
for variant in variants:
    print(variant.options.all())
```

### ✅ Use Variant Map
```python
# Single query for multiple variants
variant_map = ProductVariantService.get_variants_map(
    store_id=store.id,
    variant_ids=[1, 2, 3, 4, 5]
)
variant = variant_map.get(variant_id)
```

### ✅ Cache Availability
```python
from django.core.cache import cache

def get_availability(variant_id):
    key = f"variant_{variant_id}_availability"
    availability = cache.get(key)
    if availability is None:
        variant = ProductVariant.objects.get(id=variant_id)
        availability = variant.stock_quantity > 0
        cache.set(key, availability, 300)
    return availability
```

---

## 🐛 Debugging

### Check Variant Exists
```python
from apps.catalog.models import ProductVariant

variant = ProductVariant.objects.filter(
    id=variant_id,
    store_id=store.id,
    product_id=product.id
).first()

if not variant:
    print("Variant not found")
```

### Check Stock
```python
print(f"Stock: {variant.stock_quantity}")
print(f"Active: {variant.is_active}")
print(f"Price: {variant.price_override or product.price}")
```

### Check Options
```python
print(f"Options: {list(variant.options.values_list('value', flat=True))}")
```

### Check Stock Movements
```python
movements = variant.stock_movements.order_by('-created_at')[:10]
for m in movements:
    print(f"{m.movement_type}: {m.quantity} ({m.reason})")
```

---

## 📞 Support Resources

| Resource | Link |
|----------|------|
| **Complete Guide** | [PRODUCT_VARIANTS_GUIDE.md](./PRODUCT_VARIANTS_GUIDE.md) |
| **API Examples** | [PRODUCT_VARIANTS_API_EXAMPLES.md](./PRODUCT_VARIANTS_API_EXAMPLES.md) |
| **Implementation** | [PRODUCT_VARIANTS_IMPLEMENTATION.md](./PRODUCT_VARIANTS_IMPLEMENTATION.md) |
| **Models Source** | [apps/catalog/models.py](../apps/catalog/models.py) |
| **Services Source** | [apps/catalog/services/variant_service.py](../apps/catalog/services/variant_service.py) |
| **API Source** | [apps/catalog/api.py](../apps/catalog/api.py) |
| **Tests** | [apps/catalog/tests/test_variants.py](../apps/catalog/tests/test_variants.py) |

---

## ✅ Verification Checklist

- [x] ProductOptionGroup model with all fields
- [x] ProductOption model with all fields
- [x] ProductVariant model with all fields
- [x] StockMovement.variant FK
- [x] Checkout stock validation
- [x] Price resolution logic
- [x] API serializers
- [x] API endpoints
- [x] Admin integration
- [x] Migration script
- [x] Comprehensive tests
- [x] Full documentation

**Status:** ✅ **100% COMPLETE**

---

**Quick Links:**
- 📖 [Full Guide](./PRODUCT_VARIANTS_GUIDE.md)
- 🔗 [API Examples](./PRODUCT_VARIANTS_API_EXAMPLES.md)
- 📊 [Implementation](./PRODUCT_VARIANTS_IMPLEMENTATION.md)
- 📦 [Complete Overview](./PRODUCT_VARIANTS_COMPLETE.md)

**Version:** 1.0.0 | **Status:** ✅ Production Ready | **Date:** Feb 25, 2026
