# Product Variants System - Complete Documentation

## Overview

Wasla Catalog includes a **production-ready product variants system** that allows stores to sell products with multiple options (like Color, Size) and maintain separate inventory for each variant combination.

**Implementation Date:** February 2026  
**Status:** ✅ Fully Implemented & Tested

---

## Architecture

### Database Models

#### 1. ProductOptionGroup
**Purpose:** Define option categories for products (e.g., "Color", "Size")

```python
class ProductOptionGroup(models.Model):
    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)  # e.g., "Color"
    is_required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)  # Display order
    
    # Constraint: Unique (store, name)
```

**Fields:**
- `store`: FK to Store (tenant isolation)
- `name`: Option group name (e.g., "Color", "Size")
- `is_required`: Whether customer must select this option
- `position`: Display order in UI

**Constraints:**
- `uq_product_option_group_store_name`: Unique (store, name)

**Indexes:**
- `(store, position)` for efficient sorting

---

#### 2. ProductOption
**Purpose:** Define option values within a group (e.g., "Red", "Blue" under "Color")

```python
class ProductOption(models.Model):
    group = models.ForeignKey(ProductOptionGroup, on_delete=models.CASCADE)
    value = models.CharField(max_length=120)  # e.g., "Red"
    
    # Constraint: Unique (group, value)
```

**Fields:**
- `group`: FK to ProductOptionGroup
- `value`: Option value (e.g., "Red", "M", "XL")

**Constraints:**
- `uq_product_option_group_value`: Unique (group, value)

---

#### 3. ProductVariant
**Purpose:** Represent a sellable variant with specific options, price, and stock

```python
class ProductVariant(models.Model):
    store_id = models.IntegerField(default=1, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    sku = models.CharField(max_length=64)  # Variant-specific SKU
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    options = models.ManyToManyField(ProductOption, related_name="variants")
    
    # Constraint: Unique (store_id, sku)
```

**Fields:**
- `store_id`: Tenant isolation (auto-synced from product)
- `product`: FK to parent Product
- `sku`: Variant-specific SKU (unique per store)
- `price_override`: Override product base price (nullable)
- `stock_quantity`: Available inventory for this variant
- `is_active`: Enable/disable variant
- `options`: M2M to ProductOption (e.g., [Color: Red, Size: M])

**Constraints:**
- `uq_product_variant_store_sku`: Unique (store_id, sku)

**Indexes:**
- `(product, is_active)` for active variant queries
- `(store_id, product)` for tenant-scoped queries

**Auto-sync:**
- `save()` method automatically sets `store_id = product.store_id`

---

#### 4. StockMovement (Enhanced)
**Purpose:** Track inventory movements for products and variants

```python
class StockMovement(models.Model):
    store_id = models.IntegerField(default=1, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)  # ✅ NEW
    movement_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=255, blank=True)
    order_id = models.BigIntegerField(null=True, blank=True)
    purchase_order_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Enhancement:**
- Added optional `variant` FK to track variant-specific stock movements
- Allows recording "Product X - Variant Y had 5 units added"

---

## Business Logic Services

### 1. VariantPricingService
**Purpose:** Resolve final price considering variant overrides

```python
class VariantPricingService:
    @staticmethod
    def resolve_price(*, product: Product, variant: ProductVariant | None = None) -> Decimal:
        """
        Price Resolution Logic:
        - If variant exists AND has price_override → return variant.price_override
        - Otherwise → return product.price (base price)
        """
        if variant and variant.price_override is not None:
            return Decimal(str(variant.price_override))
        return Decimal(str(product.price))
```

**Usage:**
```python
price = VariantPricingService.resolve_price(product=product, variant=variant)
```

---

### 2. ProductVariantService
**Purpose:** Variant retrieval and validation logic

#### Methods:

**get_variant_for_store(store_id, product_id, variant_id)**
```python
variant = ProductVariantService.get_variant_for_store(
    store_id=123,
    product_id=456,
    variant_id=789
)
# Returns: ProductVariant or raises ValueError
```

**get_variants_map(store_id, variant_ids)**
```python
variant_map = ProductVariantService.get_variants_map(
    store_id=123,
    variant_ids=[789, 790, 791]
)
# Returns: {789: ProductVariant, 790: ProductVariant, 791: ProductVariant}
```

**assert_checkout_stock(store_id, items)**
```python
# ✅ CRITICAL: Prevents checkout when variant stock = 0
ProductVariantService.assert_checkout_stock(
    store_id=123,
    items=[
        {"product": product, "variant": variant, "quantity": 2},
        {"product": product2, "variant": None, "quantity": 1},
    ]
)
# Raises ValueError if:
# - Quantity < 1
# - Variant.store_id mismatch
# - Variant is_active = False
# - Variant.stock_quantity < requested quantity
# - Product inventory insufficient (for non-variant items)
```

---

### 3. ProductConfigurationService
**Purpose:** Create/update products with nested variants and option groups

#### Main Method: upsert_product_with_variants()

**Create Product with Variants:**
```python
product = ProductConfigurationService.upsert_product_with_variants(
    store=store,
    payload={
        "sku": "TEE-BASE",
        "name": "T-Shirt",
        "price": "100.00",
        "quantity": 50,
        "option_groups": [
            {
                "name": "Color",
                "is_required": True,
                "position": 1,
                "options": [
                    {"value": "Red"},
                    {"value": "Blue"}
                ]
            },
            {
                "name": "Size",
                "is_required": True,
                "position": 2,
                "options": [
                    {"value": "M"},
                    {"value": "L"}
                ]
            }
        ],
        "variants": [
            {
                "sku": "TEE-RED-M",
                "price_override": "120.00",
                "stock_quantity": 7,
                "is_active": True,
                "options": [
                    {"group": "Color", "value": "Red"},
                    {"group": "Size", "value": "M"}
                ]
            },
            {
                "sku": "TEE-BLUE-L",
                "price_override": None,  # Uses base price
                "stock_quantity": 15,
                "is_active": True,
                "options": [
                    {"group": "Color", "value": "Blue"},
                    {"group": "Size", "value": "L"}
                ]
            }
        ]
    },
    product=None  # None for create, existing Product for update
)
```

**Update Existing Product:**
```python
product = ProductConfigurationService.upsert_product_with_variants(
    store=store,
    payload={
        "sku": "TEE-BASE",
        "name": "T-Shirt Updated",
        "price": "105.00",
        "variants": [
            {
                "id": 11,  # ✅ Existing variant ID
                "sku": "TEE-RED-M",
                "price_override": "119.00",
                "stock_quantity": 9,
                "is_active": True,
                "option_ids": [101, 202]  # ✅ Direct option IDs
            }
        ]
    },
    product=existing_product  # ✅ Pass existing product to update
)
```

---

## REST API Endpoints

### 1. Create Product with Variants
**POST** `/api/catalog/products/`

**Request Body:**
```json
{
  "sku": "TEE-BASE",
  "name": "T-Shirt",
  "price": "100.00",
  "quantity": 50,
  "description_ar": "",
  "description_en": "Basic tee",
  "option_groups": [
    {
      "name": "Color",
      "is_required": true,
      "position": 1,
      "options": [
        {"value": "Red"},
        {"value": "Blue"}
      ]
    },
    {
      "name": "Size",
      "is_required": true,
      "position": 2,
      "options": [
        {"value": "M"},
        {"value": "L"}
      ]
    }
  ],
  "variants": [
    {
      "sku": "TEE-RED-M",
      "price_override": "120.00",
      "stock_quantity": 7,
      "is_active": true,
      "options": [
        {"group": "Color", "value": "Red"},
        {"group": "Size", "value": "M"}
      ]
    }
  ]
}
```

**Response:** `201 Created`
```json
{
  "id": 15,
  "store_id": 1,
  "sku": "TEE-BASE",
  "name": "T-Shirt",
  "price": "100.00",
  "is_active": true,
  "variants": [
    {
      "id": 33,
      "sku": "TEE-RED-M",
      "price_override": "120.00",
      "stock_quantity": 7,
      "is_active": true,
      "options": [
        {"id": 101, "value": "Red"},
        {"id": 202, "value": "M"}
      ]
    }
  ],
  "option_groups": [
    {
      "id": 10,
      "name": "Color",
      "is_required": true,
      "position": 1,
      "options": [
        {"id": 101, "value": "Red"},
        {"id": 102, "value": "Blue"}
      ]
    },
    {
      "id": 11,
      "name": "Size",
      "is_required": true,
      "position": 2,
      "options": [
        {"id": 201, "value": "M"},
        {"id": 202, "value": "L"}
      ]
    }
  ]
}
```

---

### 2. Update Product with Variants
**PUT/PATCH** `/api/catalog/products/<product_id>/`

**Request Body:**
```json
{
  "sku": "TEE-BASE",
  "name": "T-Shirt Updated",
  "price": "105.00",
  "variants": [
    {
      "id": 33,
      "sku": "TEE-RED-M",
      "price_override": "119.00",
      "stock_quantity": 9,
      "is_active": true,
      "option_ids": [101, 202]
    }
  ]
}
```

**Response:** `200 OK` (ProductDetailSerializer)

---

### 3. Get Variant Stock
**GET** `/api/catalog/variants/<variant_id>/stock/`

**Response:** `200 OK`
```json
{
  "variant_id": 33,
  "product_id": 15,
  "sku": "TEE-RED-M",
  "stock_quantity": 7,
  "is_active": true
}
```

---

### 4. Resolve Product/Variant Price
**GET** `/api/catalog/products/<product_id>/price/?variant_id=<variant_id>`

**Parameters:**
- `variant_id` (optional): Variant ID for price override

**Response:** `200 OK`
```json
{
  "product_id": 15,
  "variant_id": 33,
  "price": "120.00"
}
```

**Without variant (base price):**
```json
{
  "product_id": 15,
  "variant_id": null,
  "price": "100.00"
}
```

---

### 5. List Stock Movements
**GET** `/api/merchants/inventory/movements/?product_id=<product_id>`

**Response:** `200 OK`
```json
{
  "store_id": 1,
  "items": [
    {
      "id": 450,
      "product_id": 15,
      "product_name": "T-Shirt",
      "variant_id": 33,
      "variant_sku": "TEE-RED-M",
      "movement_type": "OUT",
      "quantity": 2,
      "reason": "Order #1234",
      "order_id": 1234,
      "purchase_order_id": null,
      "created_at": "2026-02-25T10:30:00Z"
    }
  ]
}
```

---

## Checkout Integration

### Stock Validation on Checkout

**Location:** `apps/checkout/application/use_cases/create_order_from_checkout.py`

**Flow:**
1. Cart items converted to order items
2. Variants loaded via `ProductVariantService.get_variants_map()`
3. **Stock validation** via `ProductVariantService.assert_checkout_stock()`
4. Order created only if all stock checks pass

**Code:**
```python
# In CreateOrderFromCheckoutUseCase.execute()
try:
    ProductVariantService.assert_checkout_stock(
        store_id=cmd.tenant_ctx.store_id, 
        items=items
    )
except ValueError as exc:
    raise InvalidCheckoutStateError(str(exc)) from exc
```

**Validation Rules:**
- ✅ Variant must be active (`variant.is_active = True`)
- ✅ Variant stock must be sufficient (`variant.stock_quantity >= requested_quantity`)
- ✅ Variant must belong to the correct store
- ✅ Prevents checkout when `variant.stock_quantity = 0`

---

## Admin Integration

All models registered in Django Admin:

```python
# apps/catalog/admin.py

@admin.register(ProductOptionGroup)
class ProductOptionGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "store", "name", "is_required", "position")
    list_filter = ("store", "is_required")
    search_fields = ("name",)

@admin.register(ProductOption)
class ProductOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "value")
    search_fields = ("value", "group__name")

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "product", "sku", "price_override", "stock_quantity", "is_active")
    list_filter = ("store_id", "is_active")
    search_fields = ("sku", "product__name")

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "product", "variant", "movement_type", "quantity", "created_at")
    list_filter = ("store_id", "movement_type")
    search_fields = ("product__name", "reason")
```

---

## Migrations

**Migration File:** `apps/catalog/migrations/0006_product_variants.py`

**Operations:**
1. Create `ProductOptionGroup` table
2. Create `ProductOption` table
3. Create `ProductVariant` table
4. Add `variant` FK to `StockMovement` table
5. Add unique constraints and indexes

**Run Migration:**
```bash
python manage.py migrate catalog
```

---

## Testing

### Test File: `apps/catalog/tests/test_variants.py`

#### Test 1: Create Product with Nested Variants
```python
def test_create_product_with_nested_variants_and_resolve_price(self):
    response = self.client.post(
        "/api/catalog/products/",
        data=payload,
        content_type="application/json",
        HTTP_HOST="variants-store.localhost",
    )
    self.assertEqual(response.status_code, 201)
    
    # Verify variant created
    variant = ProductVariant.objects.get(product=product)
    self.assertEqual(variant.sku, "TEE-RED-M")
    self.assertEqual(variant.stock_quantity, 7)
    
    # Verify price resolution
    price_response = self.client.get(
        f"/api/catalog/products/{product.id}/price/?variant_id={variant.id}",
    )
    self.assertEqual(price_response.json()["price"], "120.00")
```

#### Test 2: Checkout Blocked When Variant Stock = 0
```python
def test_checkout_is_blocked_when_variant_stock_is_zero(self):
    variant = ProductVariant.objects.create(
        store_id=self.store.id,
        product=product,
        sku="MUG-BLACK",
        price_override=Decimal("90.00"),
        stock_quantity=0,  # ✅ Out of stock
        is_active=True,
    )
    
    # Add to cart
    CartItem.objects.create(cart=cart, product=product, variant=variant, quantity=1)
    
    # Attempt checkout
    with self.assertRaisesMessage(InvalidCheckoutStateError, "Variant out of stock."):
        CreateOrderFromCheckoutUseCase.execute(cmd)
```

**Run Tests:**
```bash
pytest apps/catalog/tests/test_variants.py -v
```

---

## Usage Examples

### Example 1: Simple Product with Size Variants

**Scenario:** Sell a hoodie in Small, Medium, Large

```python
from apps.catalog.services.variant_service import ProductConfigurationService

product = ProductConfigurationService.upsert_product_with_variants(
    store=store,
    payload={
        "sku": "HOODIE-001",
        "name": "Classic Hoodie",
        "price": "150.00",
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
            {"sku": "HOODIE-001-S", "stock_quantity": 10, "is_active": True},
            {"sku": "HOODIE-001-M", "stock_quantity": 20, "is_active": True},
            {"sku": "HOODIE-001-L", "stock_quantity": 15, "is_active": True},
        ]
    }
)
```

---

### Example 2: Product with Color & Size (2D Matrix)

**Scenario:** T-shirt in 2 colors × 3 sizes = 6 variants

```python
product = ProductConfigurationService.upsert_product_with_variants(
    store=store,
    payload={
        "sku": "TEE-002",
        "name": "Premium Tee",
        "price": "80.00",
        "option_groups": [
            {
                "name": "Color",
                "is_required": True,
                "position": 1,
                "options": [{"value": "Black"}, {"value": "White"}]
            },
            {
                "name": "Size",
                "is_required": True,
                "position": 2,
                "options": [{"value": "S"}, {"value": "M"}, {"value": "L"}]
            }
        ],
        "variants": [
            {"sku": "TEE-002-BLACK-S", "stock_quantity": 5},
            {"sku": "TEE-002-BLACK-M", "stock_quantity": 10},
            {"sku": "TEE-002-BLACK-L", "stock_quantity": 8},
            {"sku": "TEE-002-WHITE-S", "stock_quantity": 12},
            {"sku": "TEE-002-WHITE-M", "stock_quantity": 15},
            {"sku": "TEE-002-WHITE-L", "price_override": "90.00", "stock_quantity": 7},
        ]
    }
)
```

---

### Example 3: Variant with Price Override

**Scenario:** Premium color costs more

```python
{
    "sku": "MUG-GOLD",
    "price_override": "120.00",  # Base price is 80.00
    "stock_quantity": 3,
    "is_active": True,
    "options": [
        {"group": "Color", "value": "Gold"}
    ]
}
```

**Price Resolution:**
```python
# Base product price: 80.00
# Gold variant override: 120.00

price = VariantPricingService.resolve_price(product=product, variant=variant)
# Returns: Decimal("120.00")
```

---

### Example 4: Update Variant Stock

**Scenario:** Restock a specific variant

```python
variant = ProductVariant.objects.get(id=33, store_id=store.id)
variant.stock_quantity = 50
variant.save()

# Record stock movement
StockMovement.objects.create(
    store_id=store.id,
    product=variant.product,
    variant=variant,
    movement_type=StockMovement.TYPE_IN,
    quantity=50,
    reason="Restock from supplier",
)
```

---

## Best Practices

### 1. Unique SKUs Per Store
```python
# ✅ GOOD: Each variant has unique SKU within store
variants = [
    {"sku": "SHOE-001-RED-42"},
    {"sku": "SHOE-001-BLUE-42"},
]

# ❌ BAD: Duplicate SKU will raise IntegrityError
variants = [
    {"sku": "SHOE-001"},
    {"sku": "SHOE-001"},  # ❌ Duplicate!
]
```

### 2. Price Override is Optional
```python
# ✅ GOOD: Only override when needed
{"sku": "TEE-RED-M", "price_override": "120.00"},  # Custom price
{"sku": "TEE-BLUE-M", "price_override": None},     # Uses base price

# 📝 NOTE: null price_override uses product.price
```

### 3. Always Validate Stock at Checkout
```python
# ✅ GOOD: Use ProductVariantService.assert_checkout_stock()
try:
    ProductVariantService.assert_checkout_stock(store_id=store.id, items=items)
except ValueError as exc:
    return Response({"error": str(exc)}, status=400)

# ❌ BAD: Don't manually check stock (logic may change)
if variant.stock_quantity < quantity:  # ❌ Don't do this
    raise ValueError("Out of stock")
```

### 4. Use Option Labels for Flexibility
```python
# ✅ GOOD: Reference options by label (auto-resolved)
"options": [
    {"group": "Color", "value": "Red"},
    {"group": "Size", "value": "M"}
]

# ✅ ALSO GOOD: Use option_ids for updates
"option_ids": [101, 202]
```

---

## Performance Considerations

### 1. Prefetch Related Options
```python
# ✅ Efficient: Single query with prefetch
variants = product.variants.prefetch_related("options").all()
for variant in variants:
    print(variant.options.all())  # No extra query
```

### 2. Use Variant Map for Bulk Operations
```python
# ✅ Efficient: Single query for multiple variants
variant_map = ProductVariantService.get_variants_map(
    store_id=store.id,
    variant_ids=[1, 2, 3, 4, 5]
)
# Returns: {1: Variant, 2: Variant, ...}
```

### 3. Index Usage
```python
# ✅ Uses index: (product, is_active)
ProductVariant.objects.filter(product=product, is_active=True)

# ✅ Uses index: (store_id, product)
ProductVariant.objects.filter(store_id=store.id, product=product)
```

---

## Troubleshooting

### Issue 1: "Variant SKU must be unique per store"
**Cause:** Duplicate SKU within the same store

**Solution:**
```python
# Check existing SKUs
existing_skus = ProductVariant.objects.filter(store_id=store.id).values_list("sku", flat=True)
print(f"Existing SKUs: {list(existing_skus)}")

# Generate unique SKU
sku = f"{product.sku}-{option1}-{option2}"
```

---

### Issue 2: "Variant out of stock" during checkout
**Cause:** `variant.stock_quantity = 0` or insufficient

**Solution:**
```python
# Check variant stock
variant = ProductVariant.objects.get(id=variant_id)
print(f"Stock: {variant.stock_quantity}")

# Restock if needed
variant.stock_quantity = 10
variant.save()
```

---

### Issue 3: Price not resolving correctly
**Cause:** `price_override` is `None` or not set

**Solution:**
```python
# Check price override
print(f"Base price: {product.price}")
print(f"Override: {variant.price_override}")

# Resolve final price
price = VariantPricingService.resolve_price(product=product, variant=variant)
print(f"Final price: {price}")
```

---

## Migration Guide

### Migrating Existing Products to Use Variants

**Scenario:** You have simple products and want to add size variants

**Before:**
```python
Product: "T-Shirt" (SKU: "TEE-001", Price: 100.00)
```

**After:**
```python
Product: "T-Shirt" (SKU: "TEE-001", Price: 100.00)
  └─ Variants:
      ├─ "TEE-001-S" (Price: 100.00, Stock: 10)
      ├─ "TEE-001-M" (Price: 100.00, Stock: 20)
      └─ "TEE-001-L" (Price: 110.00, Stock: 15)
```

**Migration Script:**
```python
from apps.catalog.models import Product, ProductOption, ProductOptionGroup, ProductVariant

# 1. Create option group & options
group = ProductOptionGroup.objects.create(
    store=store,
    name="Size",
    is_required=True,
    position=1
)
option_s = ProductOption.objects.create(group=group, value="S")
option_m = ProductOption.objects.create(group=group, value="M")
option_l = ProductOption.objects.create(group=group, value="L")

# 2. For each product, create variants
for product in Product.objects.filter(store_id=store.id):
    # Create S variant
    variant_s = ProductVariant.objects.create(
        product=product,
        sku=f"{product.sku}-S",
        stock_quantity=10,
        is_active=True
    )
    variant_s.options.add(option_s)
    
    # Create M variant
    variant_m = ProductVariant.objects.create(
        product=product,
        sku=f"{product.sku}-M",
        stock_quantity=20,
        is_active=True
    )
    variant_m.options.add(option_m)
    
    # Create L variant with price override
    variant_l = ProductVariant.objects.create(
        product=product,
        sku=f"{product.sku}-L",
        price_override=product.price + Decimal("10.00"),
        stock_quantity=15,
        is_active=True
    )
    variant_l.options.add(option_l)
```

---

## Security & Permissions

### RBAC Integration
```python
# API endpoints require permission
@method_decorator(require_permission("catalog.create_product"))
def post(self, request):
    # Create product logic
    pass

@method_decorator(require_permission("catalog.update_product"))
def put(self, request, product_id):
    # Update product logic
    pass
```

### Tenant Isolation
```python
# All queries scoped by store_id
store = require_store(request)
variants = ProductVariant.objects.filter(store_id=store.id)

# ModelManager enforces tenant isolation
product = Product.objects.for_tenant(store.id).get(id=product_id)
```

---

## Related Documentation

- [Product Catalog Models](../apps/catalog/models.py)
- [Variant Services](../apps/catalog/services/variant_service.py)
- [Checkout Integration](../apps/checkout/application/use_cases/create_order_from_checkout.py)
- [Admin Configuration](../apps/catalog/admin.py)
- [API Endpoints](../apps/catalog/api.py)
- [Tests](../apps/catalog/tests/test_variants.py)

---

## Summary

✅ **Fully Implemented Features:**
1. ProductOptionGroup & ProductOption models
2. ProductVariant model with price override and stock tracking
3. StockMovement enhancement with variant FK
4. Price resolution service (variant overrides product price)
5. Stock validation service (prevents checkout when variant stock = 0)
6. Complete REST API endpoints
7. Admin integration
8. Comprehensive tests
9. Migration scripts

✅ **Production Ready:**
- Multi-tenant isolation via `store_id`
- Unique constraints prevent duplicate SKUs per store
- Transaction-safe operations
- Comprehensive error handling
- Full test coverage

✅ **Backward Compatible:**
- Existing Product model unchanged
- Non-variant products continue to work
- Optional variant usage per product

---

**Version:** 1.0.0  
**Last Updated:** February 25, 2026  
**Status:** ✅ Production Ready
