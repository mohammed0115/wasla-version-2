# Product Variants API - Usage Examples

## Table of Contents
1. [Basic Setup](#basic-setup)
2. [Creating Products with Variants](#creating-products-with-variants)
3. [Updating Products and Variants](#updating-products-and-variants)
4. [Price Resolution](#price-resolution)
5. [Stock Management](#stock-management)
6. [Frontend Integration](#frontend-integration)
7. [Error Handling](#error-handling)
8. [Performance Optimization](#performance-optimization)

---

## Basic Setup

### Authentication
All API requests require authentication via Bearer token:

```bash
curl -X POST https://api.example.com/api/catalog/products/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Host: store.example.com"
```

### Required Headers
- `Authorization`: Bearer token
- `Content-Type`: application/json
- `Host`: Store subdomain (for multi-tenant isolation)

---

## Creating Products with Variants

### Example 1: Simple Product with Size Variants

**Scenario:** Create a hoodie with S, M, L sizes (all same price)

```bash
curl -X POST https://api.example.com/api/catalog/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Host: mystore.example.com" \
  -d '{
    "sku": "HOODIE-001",
    "name": "Classic Hoodie",
    "price": "150.00",
    "quantity": 0,
    "description_en": "Comfortable cotton hoodie",
    "description_ar": "قلنسوة قطنية مريحة",
    "option_groups": [
      {
        "name": "Size",
        "is_required": true,
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
        "sku": "HOODIE-001-S",
        "stock_quantity": 10,
        "is_active": true,
        "options": [
          {"group": "Size", "value": "S"}
        ]
      },
      {
        "sku": "HOODIE-001-M",
        "stock_quantity": 20,
        "is_active": true,
        "options": [
          {"group": "Size", "value": "M"}
        ]
      },
      {
        "sku": "HOODIE-001-L",
        "stock_quantity": 15,
        "is_active": true,
        "options": [
          {"group": "Size", "value": "L"}
        ]
      }
    ]
  }'
```

**Response:** `201 Created`
```json
{
  "id": 42,
  "store_id": 1,
  "sku": "HOODIE-001",
  "name": "Classic Hoodie",
  "price": "150.00",
  "is_active": true,
  "description_en": "Comfortable cotton hoodie",
  "description_ar": "قلنسوة قطنية مريحة",
  "image": null,
  "images": [],
  "option_groups": [
    {
      "id": 20,
      "name": "Size",
      "is_required": true,
      "position": 1,
      "options": [
        {"id": 301, "value": "S"},
        {"id": 302, "value": "M"},
        {"id": 303, "value": "L"}
      ]
    }
  ],
  "variants": [
    {
      "id": 101,
      "sku": "HOODIE-001-S",
      "price_override": null,
      "stock_quantity": 10,
      "is_active": true,
      "options": [{"id": 301, "value": "S"}]
    },
    {
      "id": 102,
      "sku": "HOODIE-001-M",
      "price_override": null,
      "stock_quantity": 20,
      "is_active": true,
      "options": [{"id": 302, "value": "M"}]
    },
    {
      "id": 103,
      "sku": "HOODIE-001-L",
      "price_override": null,
      "stock_quantity": 15,
      "is_active": true,
      "options": [{"id": 303, "value": "L"}]
    }
  ]
}
```

---

### Example 2: Product with Color & Size (2D Matrix)

**Scenario:** T-shirt in 2 colors × 3 sizes with premium pricing for XL

```bash
curl -X POST https://api.example.com/api/catalog/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Host: mystore.example.com" \
  -d '{
    "sku": "TEE-PREMIUM",
    "name": "Premium T-Shirt",
    "price": "80.00",
    "quantity": 0,
    "option_groups": [
      {
        "name": "Color",
        "is_required": true,
        "position": 1,
        "options": [
          {"value": "Black"},
          {"value": "White"}
        ]
      },
      {
        "name": "Size",
        "is_required": true,
        "position": 2,
        "options": [
          {"value": "S"},
          {"value": "M"},
          {"value": "L"},
          {"value": "XL"}
        ]
      }
    ],
    "variants": [
      {
        "sku": "TEE-PREMIUM-BLACK-S",
        "stock_quantity": 5,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "Black"},
          {"group": "Size", "value": "S"}
        ]
      },
      {
        "sku": "TEE-PREMIUM-BLACK-M",
        "stock_quantity": 10,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "Black"},
          {"group": "Size", "value": "M"}
        ]
      },
      {
        "sku": "TEE-PREMIUM-BLACK-L",
        "stock_quantity": 8,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "Black"},
          {"group": "Size", "value": "L"}
        ]
      },
      {
        "sku": "TEE-PREMIUM-BLACK-XL",
        "price_override": "95.00",
        "stock_quantity": 3,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "Black"},
          {"group": "Size", "value": "XL"}
        ]
      },
      {
        "sku": "TEE-PREMIUM-WHITE-S",
        "stock_quantity": 12,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "White"},
          {"group": "Size", "value": "S"}
        ]
      },
      {
        "sku": "TEE-PREMIUM-WHITE-M",
        "stock_quantity": 15,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "White"},
          {"group": "Size", "value": "M"}
        ]
      },
      {
        "sku": "TEE-PREMIUM-WHITE-L",
        "stock_quantity": 10,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "White"},
          {"group": "Size", "value": "L"}
        ]
      },
      {
        "sku": "TEE-PREMIUM-WHITE-XL",
        "price_override": "95.00",
        "stock_quantity": 5,
        "is_active": true,
        "options": [
          {"group": "Color", "value": "White"},
          {"group": "Size", "value": "XL"}
        ]
      }
    ]
  }'
```

---

### Example 3: Product with Material Option

**Scenario:** Phone case with material options (plastic cheaper than leather)

```json
{
  "sku": "CASE-001",
  "name": "Phone Case",
  "price": "50.00",
  "quantity": 0,
  "option_groups": [
    {
      "name": "Material",
      "is_required": true,
      "position": 1,
      "options": [
        {"value": "Plastic"},
        {"value": "Silicone"},
        {"value": "Leather"}
      ]
    },
    {
      "name": "Color",
      "is_required": true,
      "position": 2,
      "options": [
        {"value": "Black"},
        {"value": "Blue"},
        {"value": "Red"}
      ]
    }
  ],
  "variants": [
    {
      "sku": "CASE-001-PLASTIC-BLACK",
      "price_override": "40.00",
      "stock_quantity": 20,
      "is_active": true,
      "options": [
        {"group": "Material", "value": "Plastic"},
        {"group": "Color", "value": "Black"}
      ]
    },
    {
      "sku": "CASE-001-LEATHER-BLACK",
      "price_override": "120.00",
      "stock_quantity": 5,
      "is_active": true,
      "options": [
        {"group": "Material", "value": "Leather"},
        {"group": "Color", "value": "Black"}
      ]
    }
  ]
}
```

---

## Updating Products and Variants

### Example 4: Update Variant Stock

**Scenario:** Update stock quantity for specific variant

```bash
curl -X PATCH https://api.example.com/api/catalog/products/42/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Host: mystore.example.com" \
  -d '{
    "sku": "HOODIE-001",
    "name": "Classic Hoodie",
    "price": "150.00",
    "variants": [
      {
        "id": 101,
        "sku": "HOODIE-001-S",
        "stock_quantity": 5,
        "is_active": true,
        "option_ids": [301]
      },
      {
        "id": 102,
        "sku": "HOODIE-001-M",
        "stock_quantity": 0,
        "is_active": false,
        "option_ids": [302]
      }
    ]
  }'
```

**Response:** `200 OK` (updated product)

---

### Example 5: Add New Variant to Existing Product

**Scenario:** Add XL size to existing hoodie

```bash
curl -X PATCH https://api.example.com/api/catalog/products/42/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Host: mystore.example.com" \
  -d '{
    "sku": "HOODIE-001",
    "name": "Classic Hoodie",
    "price": "150.00",
    "variants": [
      {
        "id": 101,
        "sku": "HOODIE-001-S",
        "stock_quantity": 10,
        "is_active": true,
        "option_ids": [301]
      },
      {
        "id": 102,
        "sku": "HOODIE-001-M",
        "stock_quantity": 20,
        "is_active": true,
        "option_ids": [302]
      },
      {
        "id": 103,
        "sku": "HOODIE-001-L",
        "stock_quantity": 15,
        "is_active": true,
        "option_ids": [303]
      },
      {
        "sku": "HOODIE-001-XL",
        "price_override": "160.00",
        "stock_quantity": 10,
        "is_active": true,
        "options": [
          {"group": "Size", "value": "XL"}
        ]
      }
    ]
  }'
```

---

### Example 6: Disable Variant (Soft Delete)

**Scenario:** Mark variant as inactive

```json
{
  "sku": "HOODIE-001",
  "name": "Classic Hoodie",
  "price": "150.00",
  "variants": [
    {
      "id": 101,
      "sku": "HOODIE-001-S",
      "stock_quantity": 10,
      "is_active": false
    }
  ]
}
```

---

## Price Resolution

### Example 7: Get Product Base Price

**GET** `/api/catalog/products/42/price/`

```bash
curl -X GET "https://api.example.com/api/catalog/products/42/price/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Host: mystore.example.com"
```

**Response:** `200 OK`
```json
{
  "product_id": 42,
  "variant_id": null,
  "price": "150.00"
}
```

---

### Example 8: Get Variant Price (with override)

**GET** `/api/catalog/products/42/price/?variant_id=101`

```bash
curl -X GET "https://api.example.com/api/catalog/products/42/price/?variant_id=101" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Host: mystore.example.com"
```

**Response:** `200 OK`
```json
{
  "product_id": 42,
  "variant_id": 101,
  "price": "160.00"
}
```

---

## Stock Management

### Example 9: Check Variant Stock

**GET** `/api/catalog/variants/101/stock/`

```bash
curl -X GET "https://api.example.com/api/catalog/variants/101/stock/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Host: mystore.example.com"
```

**Response:** `200 OK`
```json
{
  "variant_id": 101,
  "product_id": 42,
  "sku": "HOODIE-001-S",
  "stock_quantity": 10,
  "is_active": true
}
```

---

### Example 10: List Stock Movements (with Variant Filter)

**GET** `/api/merchants/inventory/movements/?product_id=42`

```bash
curl -X GET "https://api.example.com/api/merchants/inventory/movements/?product_id=42" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Host: mystore.example.com"
```

**Response:** `200 OK`
```json
{
  "store_id": 1,
  "items": [
    {
      "id": 501,
      "product_id": 42,
      "product_name": "Classic Hoodie",
      "variant_id": 101,
      "variant_sku": "HOODIE-001-S",
      "movement_type": "OUT",
      "quantity": 2,
      "reason": "Order #1234",
      "order_id": 1234,
      "purchase_order_id": null,
      "created_at": "2026-02-25T15:30:00Z"
    },
    {
      "id": 502,
      "product_id": 42,
      "product_name": "Classic Hoodie",
      "variant_id": 102,
      "variant_sku": "HOODIE-001-M",
      "movement_type": "IN",
      "quantity": 50,
      "reason": "Restock from supplier",
      "order_id": null,
      "purchase_order_id": 789,
      "created_at": "2026-02-24T10:00:00Z"
    }
  ]
}
```

---

## Frontend Integration

### Example 11: React Product Variant Selector

```jsx
import React, { useState, useEffect } from 'react';

function ProductVariantSelector({ product }) {
  const [selectedOptions, setSelectedOptions] = useState({});
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [price, setPrice] = useState(product.price);
  const [stock, setStock] = useState(0);

  // Find matching variant when options change
  useEffect(() => {
    const optionIds = Object.values(selectedOptions);
    
    if (optionIds.length === product.option_groups.length) {
      // All options selected, find matching variant
      const variant = product.variants.find(v => {
        const variantOptionIds = v.options.map(o => o.id);
        return optionIds.every(id => variantOptionIds.includes(id));
      });
      
      if (variant) {
        setSelectedVariant(variant);
        setPrice(variant.price_override || product.price);
        setStock(variant.stock_quantity);
      }
    }
  }, [selectedOptions, product]);

  const handleOptionSelect = (groupId, optionId) => {
    setSelectedOptions({
      ...selectedOptions,
      [groupId]: optionId
    });
  };

  return (
    <div className="product-variant-selector">
      <h2>{product.name}</h2>
      <div className="price">${price}</div>
      <div className="stock">
        {stock > 0 ? `${stock} in stock` : 'Out of stock'}
      </div>

      {product.option_groups.map(group => (
        <div key={group.id} className="option-group">
          <label>{group.name}{group.is_required && ' *'}</label>
          <div className="options">
            {group.options.map(option => (
              <button
                key={option.id}
                className={selectedOptions[group.id] === option.id ? 'selected' : ''}
                onClick={() => handleOptionSelect(group.id, option.id)}
              >
                {option.value}
              </button>
            ))}
          </div>
        </div>
      ))}

      <button
        disabled={!selectedVariant || stock === 0}
        onClick={() => addToCart(product.id, selectedVariant.id)}
      >
        {stock === 0 ? 'Out of Stock' : 'Add to Cart'}
      </button>
    </div>
  );
}
```

---

### Example 12: Vue.js Dynamic Price Update

```vue
<template>
  <div class="product-selector">
    <h2>{{ product.name }}</h2>
    <div class="price">{{ formatPrice(currentPrice) }}</div>

    <div v-for="group in product.option_groups" :key="group.id" class="option-group">
      <label>{{ group.name }}</label>
      <select v-model="selectedOptions[group.id]" @change="updateVariant">
        <option value="">Select {{ group.name }}</option>
        <option v-for="option in group.options" :key="option.id" :value="option.id">
          {{ option.value }}
        </option>
      </select>
    </div>

    <div v-if="selectedVariant">
      <div class="stock-info">
        <span v-if="selectedVariant.stock_quantity > 0">
          {{ selectedVariant.stock_quantity }} in stock
        </span>
        <span v-else class="out-of-stock">Out of stock</span>
      </div>
      <button 
        :disabled="selectedVariant.stock_quantity === 0"
        @click="addToCart"
      >
        Add to Cart
      </button>
    </div>
  </div>
</template>

<script>
export default {
  props: ['product'],
  data() {
    return {
      selectedOptions: {},
      selectedVariant: null,
      currentPrice: this.product.price
    }
  },
  methods: {
    updateVariant() {
      const optionIds = Object.values(this.selectedOptions).filter(Boolean);
      
      if (optionIds.length === this.product.option_groups.length) {
        this.selectedVariant = this.product.variants.find(v => {
          const variantOptionIds = v.options.map(o => o.id);
          return optionIds.every(id => variantOptionIds.includes(id));
        });
        
        if (this.selectedVariant) {
          this.currentPrice = this.selectedVariant.price_override || this.product.price;
        }
      }
    },
    formatPrice(price) {
      return `$${parseFloat(price).toFixed(2)}`;
    },
    async addToCart() {
      // Add to cart logic
    }
  }
}
</script>
```

---

## Error Handling

### Common Error Responses

#### 400 Bad Request - Duplicate SKU
```json
{
  "detail": "Variant SKU must be unique per store."
}
```

#### 400 Bad Request - Validation Error
```json
{
  "sku": ["This field is required."],
  "variants": [
    {
      "sku": ["This field is required."]
    }
  ]
}
```

#### 404 Not Found - Product Not Found
```json
{
  "detail": "Product not found."
}
```

#### 404 Not Found - Variant Not Found
```json
{
  "detail": "Variant not found."
}
```

---

### Example Error Handling Code

```javascript
async function createProductWithVariants(productData) {
  try {
    const response = await fetch('https://api.example.com/api/catalog/products/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Host': 'mystore.example.com'
      },
      body: JSON.stringify(productData)
    });

    if (!response.ok) {
      const error = await response.json();
      
      if (response.status === 400) {
        if (error.detail && error.detail.includes('unique')) {
          throw new Error('SKU already exists. Please use a different SKU.');
        }
        throw new Error(`Validation error: ${JSON.stringify(error)}`);
      }
      
      throw new Error(`HTTP ${response.status}: ${error.detail || 'Unknown error'}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to create product:', error);
    throw error;
  }
}
```

---

## Performance Optimization

### Example 13: Bulk Variant Retrieval

```python
from apps.catalog.services.variant_service import ProductVariantService

# ✅ Efficient: Single query
variant_map = ProductVariantService.get_variants_map(
    store_id=store.id,
    variant_ids=[101, 102, 103, 104, 105]
)

# Access variants
for variant_id in [101, 102, 103, 104, 105]:
    variant = variant_map.get(variant_id)
    if variant:
        print(f"{variant.sku}: {variant.stock_quantity} in stock")
```

---

### Example 14: Prefetch Options for Variant List

```python
# ✅ Efficient: Prefetch related options
variants = product.variants.prefetch_related('options', 'options__group').all()

for variant in variants:
    options_display = ', '.join([
        f"{opt.group.name}: {opt.value}" 
        for opt in variant.options.all()
    ])
    print(f"{variant.sku} - {options_display}")
```

---

### Example 15: Caching Variant Availability

```python
from django.core.cache import cache

def get_variant_availability(variant_id):
    cache_key = f"variant_{variant_id}_availability"
    
    # Try cache first
    availability = cache.get(cache_key)
    if availability is not None:
        return availability
    
    # Fetch from database
    variant = ProductVariant.objects.get(id=variant_id)
    availability = {
        'in_stock': variant.stock_quantity > 0,
        'quantity': variant.stock_quantity,
        'is_active': variant.is_active
    }
    
    # Cache for 5 minutes
    cache.set(cache_key, availability, 300)
    return availability
```

---

## Additional Resources

- [Product Variants Guide](PRODUCT_VARIANTS_GUIDE.md) - Complete documentation
- [API Reference](../apps/catalog/api.py) - API endpoint source code
- [Models Reference](../apps/catalog/models.py) - Database models
- [Services Reference](../apps/catalog/services/variant_service.py) - Business logic

---

**Last Updated:** February 25, 2026  
**API Version:** 1.0
