# WASLA API Documentation

## Overview

WASLA API provides comprehensive documentation using **OpenAPI 3.0 Specification** (formerly Swagger) with multiple interactive interfaces:

- **Swagger UI**: Modern, interactive API explorer
- **ReDoc**: Beautiful API documentation view
- **OpenAPI Schema**: Raw OpenAPI 3.0 specification (JSON)

## Quick Access

### Local Development
```
Swagger UI:    http://localhost:8000/api/docs/
ReDoc:         http://localhost:8000/api/redoc/
OpenAPI JSON:  http://localhost:8000/api/schema/
```

### Production
```
Swagger UI:    https://yourdomain.com/api/docs/
ReDoc:         https://yourdomain.com/api/redoc/
OpenAPI JSON:  https://yourdomain.com/api/schema/
```

---

## Using Swagger UI

### Features

✓ **Interactive Testing**: Execute API calls directly from the browser  
✓ **Request/Response Inspection**: See exact request format and response data  
✓ **Authentication**: Configure JWT tokens or session authentication  
✓ **Parameter Validation**: Real-time validation of required parameters  
✓ **Auto-complete**: Autocomplete for endpoints and parameters  

### Try It Out

1. Navigate to http://localhost:8000/api/docs/
2. Find an endpoint (e.g., `GET /api/products/`)
3. Click **"Try it out"** button
4. Fill in any required parameters
5. Click **"Execute"**
6. View response, headers, and curl command

### Authentication in Swagger

#### Session Authentication
1. Login via `/auth/login/` endpoint first
2. Session cookie is automatically included in subsequent requests

#### JWT Token Authentication
1. Get token from `/api/auth/token/` endpoint:
   ```json
   {
     "username": "user@example.com",
     "password": "your-password"
   }
   ```
2. Copy the `access` token from response
3. Click "Authorize" button in Swagger UI
4. Paste token in format: `Token <your-token-here>`
5. Click "Authorize" and "Close"

### Example: Creating a Product

1. POST `/api/catalog/products/`
2. Click "Try it out"
3. Update request body:
   ```json
   {
     "name": "Test Product",
     "description": "A test product",
     "price": "99.99",
     "category_id": 1,
     "store_id": 1
   }
   ```
4. Click "Execute"
5. Response shows created product with ID

---

## Using ReDoc

ReDoc provides a **read-only** API documentation view optimized for:

✓ **Learning**: Understand API structure and best practices  
✓ **Reference**: Search endpoints, models, and parameters  
✓ **Sharing**: Clean, professional documentation view  
✓ **Offline**: Download API spec for offline reading  

### Features

- **Sidebar Navigation**: Jump to any endpoint quickly
- **Search**: Find endpoints by name, tag, or description
- **Schema Examples**: See request/response format
- **Authentication Info**: Clear auth requirement indicators
- **Performance**: Optimized for large APIs

---

## API Structure

### Base URL

```
Development: http://localhost:8000/api/
Production:  https://yourdomain.com/api/
```

### Endpoints by Module

#### Authentication
- `POST /auth/login/` - Login with credentials
- `POST /auth/logout/` - Logout user
- `POST /auth/token/` - Get JWT token
- `POST /auth/token/refresh/` - Refresh JWT token

#### Products & Catalog
- `GET /catalog/products/` - List all products
- `POST /catalog/products/` - Create new product
- `GET /catalog/products/{id}/` - Get product details
- `PUT /catalog/products/{id}/` - Update product
- `DELETE /catalog/products/{id}/` - Delete product
- `GET /catalog/categories/` - List categories

#### Orders
- `GET /api/orders/` - List user orders
- `POST /api/orders/` - Create new order
- `GET /api/orders/{id}/` - Get order details
- `PUT /api/orders/{id}/` - Update order
- `GET /api/orders/{id}/items/` - Get order items

#### Cart
- `GET /api/cart/` - Get cart contents
- `POST /api/cart/items/` - Add item to cart
- `PUT /api/cart/items/{id}/` - Update cart item
- `DELETE /api/cart/items/{id}/` - Remove from cart
- `POST /api/cart/checkout/` - Checkout cart

#### Payments
- `POST /api/payments/` - Create payment
- `GET /api/payments/{id}/` - Get payment details
- `GET /api/payments/{id}/status/` - Check payment status
- `POST /api/payments/{id}/verify/` - Verify payment

---

## Authentication

### Session Authentication

Used for web browser requests:

```bash
# Login
curl -X POST http://localhost:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user@example.com","password":"password"}'

# Subsequent requests include session cookie automatically
curl http://localhost:8000/api/orders/ \
  -b cookies.txt
```

### JWT Token Authentication

Used for API clients:

```bash
# Get token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user@example.com","password":"password"}' | jq -r '.access')

# Use token
curl http://localhost:8000/api/orders/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## Common Response Formats

### Success Response (200 OK)
```json
{
  "id": 1,
  "name": "Product Name",
  "description": "Product description",
  "price": "99.99",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### List Response (200 OK)
```json
{
  "count": 50,
  "next": "http://api.example.com/products/?page=2",
  "previous": null,
  "results": [
    { "id": 1, "name": "Product 1" },
    { "id": 2, "name": "Product 2" }
  ]
}
```

### Error Response (400, 401, 403, 404, 500)
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Validation Error (400 Bad Request)
```json
{
  "field_name": ["This field is required."],
  "email": ["Enter a valid email address."],
  "price": ["Ensure this value is greater than or equal to 0."]
}
```

### Authentication Error (401 Unauthorized)
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### Permission Error (403 Forbidden)
```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

## Rate Limiting

API rate limiting may be enforced. Check response headers:

```
X-RateLimit-Limit: 100        # Requests per hour
X-RateLimit-Remaining: 45     # Remaining requests
X-RateLimit-Reset: 1642435200 # Unix timestamp when limit resets
```

If rate limited (429):
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

---

## Pagination

List endpoints support pagination:

```bash
# Get page 1 (default size: 20 items)
GET /api/products/

# Get page 2
GET /api/products/?page=2

# Custom page size
GET /api/products/?page=1&page_size=50

# Cursor-based pagination
GET /api/products/?cursor=cD00NTA=
```

Response includes:
```json
{
  "count": 150,
  "next": "http://api.example.com/products/?page=2",
  "previous": null,
  "results": [...]
}
```

---

## Filtering and Search

List endpoints support filtering:

```bash
# Filter by category
GET /api/products/?category=electronics

# Filter by price range
GET /api/products/?price_min=10&price_max=100

# Search by name
GET /api/products/?search=laptop

# Multiple filters
GET /api/products/?category=electronics&price_min=100&search=laptop

# Ordering
GET /api/products/?ordering=-created_at  # newest first
GET /api/products/?ordering=price        # lowest price first
```

---

## Integration Examples

### JavaScript/Fetch API

```javascript
// Get all products
const response = await fetch('http://localhost:8000/api/catalog/products/');
const data = await response.json();
console.log(data);

// With authentication
const token = 'your-jwt-token';
const response = await fetch('http://localhost:8000/api/orders/', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

### Python/Requests

```python
import requests

# Get products
response = requests.get('http://localhost:8000/api/catalog/products/')
products = response.json()

# Create order (with token)
headers = {'Authorization': f'Bearer {token}'}
order_data = {
    'items': [
        {'product_id': 1, 'quantity': 2},
        {'product_id': 2, 'quantity': 1}
    ]
}
response = requests.post(
    'http://localhost:8000/api/orders/',
    json=order_data,
    headers=headers
)
```

### cURL

```bash
# Get products
curl http://localhost:8000/api/catalog/products/

# Create order with token
curl -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"items":[{"product_id":1,"quantity":2}]}'
```

---

## OpenAPI Specification

### Downloading OpenAPI Schema

```bash
# Get JSON schema
curl http://localhost:8000/api/schema/ > openapi.json

# Get YAML schema
curl http://localhost:8000/api/schema/?format=yaml > openapi.yaml
```

### Using with Tools

#### Generate Client Library (OpenAPI Generator)

```bash
# Generate Python client
openapi-generator-cli generate \
  -i openapi.json \
  -g python \
  -o ./generated-client

# Generate TypeScript client  
openapi-generator-cli generate \
  -i openapi.json \
  -g typescript-fetch \
  -o ./generated-client
```

#### Import into Postman

1. Open Postman
2. Click "Import"
3. Paste: `http://localhost:8000/api/schema/`
4. Collections created with all endpoints
5. Set variables for base URL and authentication

---

## Best Practices

### Request Format

✓ Always send `Content-Type: application/json` for JSON data  
✓ Use proper HTTP methods (GET, POST, PUT, PATCH, DELETE)  
✓ Include authentication token in Authorization header  
✓ Send parameters as JSON in request body (not query string) for POST/PUT  

### Error Handling

✓ Check response status code before processing data  
✓ Handle 429 rate limit errors with exponential backoff  
✓ Implement retry logic for 5xx errors  
✓ Log full response for debugging failed requests  

### Performance

✓ Use pagination for large lists  
✓ Filter results server-side rather than fetching all data  
✓ Cache GET requests to reduce API calls  
✓ Use partial responses with sparse fieldsets if supported  

### Security

✓ Store JWT tokens securely (not in LocalStorage)  
✓ Use HTTPS in production (never HTTP)  
✓ Validate all user input before sending to API  
✓ Never commit API keys or tokens  
✓ Implement CSRF protection for state-changing requests  

---

## Troubleshooting

### 401 Unauthorized

**Problem**: "Authentication credentials were not provided"

**Solutions**:
1. Ensure JWT token is included in Authorization header
2. Check token hasn't expired (refresh if needed)
3. Verify credentials are correct
4. Check authentication method (JWT vs session)

### 403 Forbidden

**Problem**: "You do not have permission to perform this action"

**Solutions**:
1. Verify user has required permissions
2. Check user belongs to correct group/role
3. Verify user created the resource (for ownership checks)
4. Admin may need to grant permissions

### 404 Not Found

**Problem**: "Not found" for existing resource

**Solutions**:
1. Verify resource ID is correct
2. Check URL path spelling
3. Verify API version in URL
4. Confirm user has access to resource

### 400 Bad Request

**Problem**: Validation errors in request

**Solutions**:
1. Review error message for missing fields
2. Verify field values match expected format
3. Check field type (string vs number)
4. Validate required vs optional fields

### Timeout

**Problem**: Request takes too long or times out

**Solutions**:
1. Increase request timeout (default 30s)
2. Use pagination for large result sets
3. Add more specific filters to reduce data
4. Check server performance/logs

---

## API Versioning

Current API version: **v1** (implicit in `/api/` path)

Future versions will use:
```
/api/v2/
/api/v3/
```

Versions may have breaking changes. Old versions supported for 6 months after new version release.

---

## Support & Documentation

- **Interactive API Docs**: http://localhost:8000/api/docs/
- **Beautiful Docs**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/
- **GitHub Issues**: https://github.com/your-org/wasla/issues
- **Support Email**: support@wasla.com
- **Documentation**: https://docs.wasla.com

---

## Schema Management

### Auto-Schema Generation

drf-spectacular automatically generates schema from:
- Django models and serializers
- DRF viewsets and APIViews
- Method documentation strings
- Field validators and choices

### Custom Schema Enhancements

Add docstrings to endpoints:

```python
class ProductListView(ViewSet):
    """
    List, create, retrieve, update, and delete products.
    
    Filtering:
    - category: Filter by category ID
    - price_min/price_max: Filter by price range
    - search: Search by name or description
    
    Ordering:
    - created_at: Sort by creation date
    - price: Sort by price
    """
    
    def list(self, request):
        """
        Get all products.
        
        Returns paginated list of products with details.
        """
```

### Schema Extension

For complex API specifications, extend schema in settings:

```python
# config/settings.py
SPECTACULAR_SETTINGS = {
    ...
    "SERVERS": [
        {"url": "http://localhost:8000", "description": "Local"},
        {"url": "https://yourdomain.com", "description": "Production"},
    ],
    "EXAMPLES": {
        "product_id": 1,
        "category_id": 5,
    }
}
```

---

## Monitoring & Analytics

Track API usage via:
- **Sentry**: Error tracking and monitoring
- **Datadog**: Performance metrics and APM
- **Custom logging**: Request/response logging for debugging

Check logs for:
- Failed authentication attempts
- Rate limit violations
- Slow API responses
- Data validation errors

---

## Changelog

### v1.0.0 (Current)
- OpenAPI 3.0 specification
- Swagger UI integration
- ReDoc documentation
- All core API endpoints documented
- Authentication and authorization
- Pagination, filtering, and search
