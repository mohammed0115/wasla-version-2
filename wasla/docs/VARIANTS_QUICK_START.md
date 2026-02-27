# Product Variants - Quick Reference Guide

## For Merchants (Dashboard)

### Create a Product with Variants

1. **Go to:** `/dashboard/products/` → Click "إضافة منتج جديد"

2. **Fill Product Details:**
   - SKU: `TSHIRT-BASE` (identifier for your store)
   - Name: `Classic T-Shirt`
   - Price: `100.00 ر.س` (base price for all variants)
   - Description (optional)

3. **Save** → Redirects to Edit page

4. **Add Option Groups:**
   - Click "+ إضافة مجموعة خيارات"
   - Name: `Color`
   - Check: "إجباري" (if customers must pick a color)
   - Click Save
   
   - Click "+ إضافة مجموعة خيارات" again
   - Name: `Size`
   - Check: "إجباري"
   - Click Save

5. **Edit Option Groups (Add Values):**
   - Click "تعديل" under "Color"
   - Add options: Red, Blue, Black, White
   - Click Save
   
   - Click "تعديل" under "Size"
   - Add options: S, M, L, XL, XXL
   - Click Save

6. **Add Variants (Combinations):**
   - Click "+ إضافة نسخة"
   - SKU: `TSHIRT-RED-M` (must be unique in your store)
   - Price: Leave blank (will use base 100 ر.س)
   - Stock: `50` (how many in stock)
   - Select Options: Check [Color: Red] + [Size: M]
   - Click Save
   
   - Repeat for: RED/L, RED/XL, BLUE/M, BLUE/L, ...etc

7. **Done!** Product now has variants. Customers will see option selectors on the storefront.

### Edit/Delete Variants

- **Edit:** Click "تعديل" on the variant row
- **Delete:** Click "حذف" on the variant row
- **Update Stock:** Edit variant, change "الكمية المتاحة", Save

---

## For Developers (Code)

### Create Product with Variants (API)

```python
from apps.catalog.services.variant_service import ProductConfigurationService
from decimal import Decimal

payload = {
    "sku": "TSHIRT",
    "name": "Classic T-Shirt",
    "price": Decimal("100.00"),
    "option_groups": [
        {
            "name": "Color",
            "is_required": True,
            "options": [
                {"value": "Red"},
                {"value": "Blue"},
            ]
        },
        {
            "name": "Size",
            "is_required": True,
            "options": [
                {"value": "M"},
                {"value": "L"},
                {"value": "XL"},
            ]
        }
    ],
    "variants": [
        {
            "sku": "TSHIRT-RED-M",
            "price_override": None,  # Use base price
            "stock_quantity": 10,
            "options": [
                {"group": "Color", "value": "Red"},
                {"group": "Size", "value": "M"},
            ]
        },
        {
            "sku": "TSHIRT-BLUE-L",
            "price_override": Decimal("120.00"),  # Premium variant
            "stock_quantity": 5,
            "options": [
                {"group": "Color", "value": "Blue"},
                {"group": "Size", "value": "L"},
            ]
        }
    ]
}

product = ProductConfigurationService.upsert_product_with_variants(
    store=store,
    payload=payload
)
```

### Get Variant Price

```python
from apps.catalog.services.variant_service import VariantPricingService
from apps.catalog.models import Product, ProductVariant

product = Product.objects.get(id=45)
variant = ProductVariant.objects.get(id=123)

# Get price for variant (uses override if set, otherwise base price)
price = VariantPricingService.resolve_price(product=product, variant=variant)
print(price)  # Decimal('120.00') or Decimal('100.00')
```

### Validate Variant for Store

```python
from apps.catalog.services.variant_service import ProductVariantService

try:
    variant = ProductVariantService.get_variant_for_store(
        store_id=1,
        product_id=45,
        variant_id=123
    )
except ValueError:
    print("Variant not found or wrong store")
```

### Add to Cart with Variant

```python
from apps.cart.application.use_cases.add_to_cart import AddToCartCommand, AddToCartUseCase
from apps.tenants.domain.tenant_context import TenantContext

tenant_ctx = TenantContext(
    tenant_id=1,
    store_id=1,
    currency="SAR",
    user_id=user.id,
    session_key=request.session.session_key,
)

cmd = AddToCartCommand(
    tenant_ctx=tenant_ctx,
    product_id=45,
    quantity=2,
    variant_id=123  # Optional
)

cart = AddToCartUseCase.execute(cmd)
# cart.items[0].variant_id == 123
# cart.items[0].unit_price_snapshot == Decimal('120.00')
```

### Validate Stock at Checkout

```python
from apps.catalog.services.variant_service import ProductVariantService
from apps.catalog.models import ProductVariant

# Get variants from cart
items = [
    {
        "quantity": 2,
        "variant": ProductVariant.objects.get(id=123),
    }
]

try:
    ProductVariantService.assert_checkout_stock(
        store_id=1,
        items=items
    )
    print("✓ All items have sufficient stock - proceed to payment")
except ValueError as e:
    print(f"✗ {e}")  # "Variant out of stock."
```

### Check Variant Stock

```python
from apps.catalog.models import ProductVariant

variant = ProductVariant.objects.get(id=123)
print(f"Stock: {variant.stock_quantity}")
print(f"Active: {variant.is_active}")

# Update stock
variant.stock_quantity = 25
variant.save(update_fields=["stock_quantity"])
```

### List Variants for Product

```python
from apps.catalog.models import Product

product = Product.objects.get(id=45)
variants = product.variants.prefetch_related("options").all()

for variant in variants:
    print(f"{variant.sku}: {variant.stock_quantity} in stock")
    for option in variant.options.all():
        print(f"  - {option.group.name}: {option.value}")
```

---

## JavaScript (Storefront)

### VariantSelector Class

**Auto-initialized on product page:**

```javascript
// Embedded in template as:
new VariantSelector({
  productId: 45,
  variantData: {...},  // Embedded JSON
  basePrice: 100.00,
});
```

**What it does:**
- Tracks selected option buttons
- Finds matching variant from embedded data
- Updates price, stock status
- Enables/disables add-to-cart button

**No manual setup required** - it's built into `product_detail.html`

---

## URL Map

### Merchant Dashboard
```
/dashboard/products/                                  # List
/dashboard/products/create/                           # New
/dashboard/products/{id}/                             # View
/dashboard/products/{id}/edit/                        # Edit
/dashboard/products/{id}/option-groups/create/       # New group
/dashboard/products/{id}/option-groups/{gid}/edit/   # Edit group
/dashboard/products/{id}/variants/create/            # New variant
/dashboard/products/{id}/variants/{vid}/edit/        # Edit variant
/dashboard/products/{id}/variants/{vid}/delete/      # Delete variant
```

### API Endpoints
```
POST   /api/catalog/products/               # Create with variants
PUT    /api/catalog/products/{id}/          # Update
PATCH  /api/catalog/products/{id}/          # Partial update
GET    /api/catalog/products/{id}/price/    # Get price (with ?variant_id=X)
GET    /api/catalog/variants/{id}/stock/    # Get stock
```

### Storefront
```
GET    /store/product/{id}/                 # Product page (with variants UI)
POST   /api/cart/add/                       # Add to cart (with variant_id)
```

---

## Common Tasks

### Display All Variants of a Product

```python
from apps.catalog.models import Product

product = Product.objects.get(id=45)
for variant in product.variants.all():
    print(f"{variant.sku}: {variant.stock_quantity}")
```

### Get Best-Selling Variant

```python
from django.db.models import Count
from apps.catalog.models import ProductVariant

best = ProductVariant.objects.filter(
    product_id=45
).annotate(
    order_count=Count('cartitem')
).order_by('-order_count').first()

print(f"Most popular: {best.sku}")
```

### Update Variant Stock After Order

```python
from apps.catalog.models import ProductVariant, StockMovement

variant = ProductVariant.objects.get(id=123)
variant.stock_quantity -= 2  # Reduce by order qty
variant.save(update_fields=["stock_quantity"])

# Log the movement
StockMovement.objects.create(
    store_id=1,
    product_id=variant.product_id,
    variant=variant,
    movement_type=StockMovement.TYPE_OUT,
    quantity=2,
    reason=f"Order #{order.id}",
    order_id=order.id,
)
```

### Get Variants with Low Stock

```python
from django.db.models import Q
from apps.catalog.models import ProductVariant

low_stock = ProductVariant.objects.filter(
    store_id=1,
    stock_quantity__lt=5
).select_related("product")

for variant in low_stock:
    print(f"{variant.sku}: {variant.stock_quantity} left")
```

### Export Variants to CSV

```python
import csv
from apps.catalog.models import ProductVariant

variants = ProductVariant.objects.filter(
    store_id=1
).select_related("product")

with open('variants.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['Product SKU', 'Variant SKU', 'Price', 'Stock', 'Active'])
    for v in variants:
        writer.writerow([
            v.product.sku,
            v.sku,
            v.price_override or v.product.price,
            v.stock_quantity,
            'Yes' if v.is_active else 'No'
        ])
```

---

## Troubleshooting

**Q: Variant not showing in storefront?**
- Check `variant.is_active = True`
- Check variant has options selected
- Check product has option groups
- Browser cache - refresh

**Q: Price not updating when variant changed?**
- Check browser console for JS errors
- Clear browser cache and reload
- Check variant data embedded in page (view source)

**Q: Add-to-cart fails for variant?**
- Verify `variant_id` is being sent in POST
- Check variant belongs to correct product
- Verify variant.is_active = True
- Check store isolation

**Q: Checkout says "out of stock"?**
- This is correct - stock validated before payment
- Product's stock_quantity < order quantity
- Update variant stock in dashboard
- Customer can reduce quantity or change variant

---

## Testing

**Run all variant tests:**
```bash
pytest apps/catalog/tests/test_product_variants.py -v
```

**Run specific test:**
```bash
pytest apps/catalog/tests/test_product_variants.py::VariantPricingServiceTests::test_override_price_when_variant_has_override -v
```

---

## Key Points

✅ **SKU Uniqueness:** Per store (not global)  
✅ **Pricing:** Can override on each variant  
✅ **Stock:** Tracked per variant  
✅ **Multi-tenant:** Full store isolation  
✅ **Price Snapshots:** Captured when added to cart  
✅ **Stock Validation:** At checkout (not add)  
✅ **Dashboard:** Full CRUD for variants  
✅ **Storefront:** Dynamic option selectors  

---

Questions? Check [PRODUCT_VARIANTS_FINAL.md](PRODUCT_VARIANTS_FINAL.md) for complete architecture.
