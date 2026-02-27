# Wallet API Reference

Complete API documentation for merchant and admin wallet endpoints.

---

## Authentication

All endpoints require authentication via:
- **Session** (for template views)
- **Token/JWT** (for API clients)
- **User permission** check (owner of store)

```bash
# Example with curl and token
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.wasla.local/api/wallet/stores/123/wallet/summary/
```

---

## Merchant APIs

### Get Wallet Summary

**Endpoint:** `GET /api/wallet/stores/{store_id}/wallet/summary/`

**Description:** Get merchant's wallet balance overview with recent activity.

**Request:**
```bash
GET /api/wallet/stores/1/wallet/summary/
```

**Response (200 OK):**
```json
{
  "store_id": 1,
  "available_balance": "1500.50",
  "pending_balance": "250.00",
  "total_balance": "1750.50",
  "currency": "USD",
  "recent_transactions": [
    {
      "date": "2026-02-25",
      "type": "payment_captured",
      "reference": "ORD-12345",
      "amount": "100.00",
      "status": "posted"
    }
  ],
  "pending_withdrawals": [
    {
      "id": 45,
      "reference_code": "WD-001",
      "amount": "500.00",
      "status": "pending",
      "requested_at": "2026-02-24T10:30:00Z"
    }
  ],
  "effective_available": "1000.50"
}
```

**Error Responses:**
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not owner of this store
- `404 Not Found` - Store not found

---

### Get Wallet Details

**Endpoint:** `GET /api/wallet/stores/{store_id}/wallet/`

**Description:** Detailed wallet information with balance breakdown.

**Response (200 OK):**
```json
{
  "id": 1,
  "store_id": 1,
  "available_balance": "1500.50",
  "pending_balance": "250.00",
  "last_updated": "2026-02-25T14:20:00Z",
  "currency": "USD"
}
```

---

### Get Journal Ledger

**Endpoint:** `GET /api/wallet/stores/{store_id}/wallet/ledger/`

**Description:** Complete journal ledger with filtering and pagination.

**Query Parameters:**
- `entry_type` - Filter: payment_captured, order_delivered, refund, withdrawal, adjustment
- `date_from` - Filter: YYYY-MM-DD
- `date_to` - Filter: YYYY-MM-DD
- `page` - Pagination: default 1
- `page_size` - Items per page: default 20

**Request:**
```bash
GET /api/wallet/stores/1/wallet/ledger/?entry_type=payment_captured&date_from=2026-02-01
```

**Response (200 OK):**
```json
{
  "count": 125,
  "next": "https://api.wasla.local/api/wallet/stores/1/wallet/ledger/?page=2",
  "previous": null,
  "results": [
    {
      "id": 98,
      "entry_date": "2026-02-25",
      "entry_type": "payment_captured",
      "reference_id": "ORD-12345",
      "description": "Order payment - Item: Widget",
      "status": "posted",
      "lines": [
        {
          "account_code": "1000",
          "account_name": "Cash",
          "debit": "100.00",
          "credit": "0.00"
        },
        {
          "account_code": "2100",
          "account_name": "Merchant Payable - Pending",
          "debit": "0.00",
          "credit": "97.50"
        },
        {
          "account_code": "4000",
          "account_name": "Platform Revenue - Fees",
          "debit": "0.00",
          "credit": "2.50"
        }
      ]
    }
  ]
}
```

---

### Get Journal Entry Detail

**Endpoint:** `GET /api/wallet/stores/{store_id}/wallet/ledger/{entry_id}/`

**Description:** Complete details of a single journal entry with all lines.

**Response (200 OK):**
```json
{
  "id": 98,
  "store_id": 1,
  "entry_date": "2026-02-25",
  "entry_type": "payment_captured",
  "reference_id": "ORD-12345",
  "description": "Order payment received",
  "status": "posted",
  "created_at": "2026-02-25T10:30:00Z",
  "idempotency_key": "payment-5678",
  "is_balanced": true,
  "lines": [
    {
      "id": 201,
      "account": {
        "code": "1000",
        "name": "Cash",
        "type": "asset"
      },
      "debit": "100.00",
      "credit": "0.00",
      "description": "Payment received"
    },
    {
      "id": 202,
      "account": {
        "code": "2100",
        "name": "Merchant Payable - Pending",
        "type": "liability"
      },
      "debit": "0.00",
      "credit": "97.50",
      "description": "Net amount due to merchant"
    },
    {
      "id": 203,
      "account": {
        "code": "4000",
        "name": "Platform Revenue - Fees",
        "type": "revenue"
      },
      "debit": "0.00",
      "credit": "2.50",
      "description": "Commission charged"
    }
  ]
}
```

---

### Get Order Payment Allocation

**Endpoint:** `GET /api/wallet/stores/{store_id}/wallet/orders/{order_id}/allocation/`

**Description:** Fee breakdown for a specific order.

**Response (200 OK):**
```json
{
  "order_id": "ORD-12345",
  "gross_amount": "100.00",
  "fee_amount": "2.50",
  "net_amount": "97.50",
  "fee_policy": {
    "name": "Standard 2.5% Commission",
    "fee_type": "percentage",
    "fee_value": "2.50"
  },
  "allocation_data": {
    "product": "Widget",
    "qty": 2,
    "subtotal": "100.00",
    "shipping": "0.00",
    "tax": "0.00"
  }
}
```

---

### Request Withdrawal

**Endpoint:** `POST /api/wallet/stores/{store_id}/wallet/withdrawals/`

**Description:** Create a new withdrawal request.

**Request Body:**
```json
{
  "amount": "500.00",
  "note": "Monthly payout"
}
```

**Response (201 Created):**
```json
{
  "id": 45,
  "reference_code": "WD-2026-00045",
  "store_id": 1,
  "amount": "500.00",
  "status": "pending",
  "requested_at": "2026-02-25T14:30:00Z",
  "requested_by": "merchant@test.com",
  "note": "Monthly payout",
  "processed_at": null
}
```

**Validation Errors (400 Bad Request):**
```json
{
  "amount": [
    "Amount cannot exceed available balance (Available: 1000.00)"
  ]
}
```

---

### Get Withdrawals List

**Endpoint:** `GET /api/wallet/stores/{store_id}/wallet/withdrawals/`

**Description:** List all withdrawal requests for merchant.

**Query Parameters:**
- `status` - Filter: pending, approved, paid, rejected
- `page` - Pagination
- `page_size` - Items per page

**Request:**
```bash
GET /api/wallet/stores/1/wallet/withdrawals/?status=pending
```

**Response (200 OK):**
```json
{
  "count": 12,
  "results": [
    {
      "id": 45,
      "reference_code": "WD-2026-00045",
      "amount": "500.00",
      "status": "pending",
      "requested_at": "2026-02-25T14:30:00Z",
      "processed_at": null
    }
  ]
}
```

---

## Admin APIs

### Approve Withdrawal

**Endpoint:** `POST /api/wallet/admin/wallet/withdrawals/{withdrawal_id}/approve/`

**Description:** Admin approves a pending withdrawal.

**Request:** (empty body)

**Response (200 OK):**
```json
{
  "id": 45,
  "status": "approved",
  "approved_at": "2026-02-25T15:00:00Z",
  "approved_by": "admin@test.com"
}
```

**Error Responses:**
- `400 Bad Request` - Withdrawal not in pending state
- `403 Forbidden` - Not an admin
- `404 Not Found` - Withdrawal not found

---

### Reject Withdrawal

**Endpoint:** `POST /api/wallet/admin/wallet/withdrawals/{withdrawal_id}/reject/`

**Description:** Admin rejects a pending withdrawal with reason.

**Request Body:**
```json
{
  "rejection_reason": "Pending KYC verification - please resubmit documents"
}
```

**Response (200 OK):**
```json
{
  "id": 45,
  "status": "rejected",
  "rejection_reason": "Pending KYC verification - please resubmit documents",
  "rejected_at": "2026-02-25T15:00:00Z"
}
```

---

### Mark Withdrawal as Paid

**Endpoint:** `POST /api/wallet/admin/wallet/withdrawals/{withdrawal_id}/paid/`

**Description:** Admin confirms withdrawal has been paid out.

**Request Body:**
```json
{
  "payout_reference": "WIRE-12345678-ACH"
}
```

**Response (200 OK):**
```json
{
  "id": 45,
  "status": "paid",
  "payout_reference": "WIRE-12345678-ACH",
  "paid_at": "2026-02-25T16:00:00Z"
}
```

---

### List Fee Policies

**Endpoint:** `GET /api/wallet/admin/wallet/fee-policies/`

**Description:** List all fee policies (global, plan, store-level).

**Query Parameters:**
- `scope` - Filter: global, plan, store
- `is_active` - Filter: true, false
- `page` - Pagination

**Response (200 OK):**
```json
{
  "count": 8,
  "results": [
    {
      "id": 1,
      "name": "Standard 2.5% Commission",
      "fee_type": "percentage",
      "fee_value": "2.50",
      "minimum_fee": "0.50",
      "maximum_fee": "100.00",
      "scope": "global",
      "is_active": true,
      "apply_to_shipping": true,
      "apply_to_discounts": true,
      "created_at": "2026-02-01T00:00:00Z"
    }
  ]
}
```

---

### Create Fee Policy

**Endpoint:** `POST /api/wallet/admin/wallet/fee-policies/`

**Description:** Create a new fee policy.

**Request Body:**
```json
{
  "name": "Premium Store Rate",
  "fee_type": "percentage",
  "fee_value": "1.50",
  "minimum_fee": "0.50",
  "maximum_fee": null,
  "scope": "store",
  "store_id": 5,
  "apply_to_shipping": true,
  "apply_to_discounts": false,
  "is_active": true
}
```

**Response (201 Created):**
```json
{
  "id": 9,
  "name": "Premium Store Rate",
  "fee_type": "percentage",
  "fee_value": "1.50",
  "minimum_fee": "0.50",
  "maximum_fee": null,
  "scope": "store",
  "store": {
    "id": 5,
    "name": "Premium Store"
  },
  "is_active": true
}
```

---

### Update Fee Policy

**Endpoint:** `PATCH /api/wallet/admin/wallet/fee-policies/{policy_id}/`

**Description:** Update an existing fee policy.

**Request Body:** (any fields to update)
```json
{
  "fee_value": "1.75",
  "is_active": false
}
```

**Response (200 OK):**
```json
{
  "id": 9,
  "fee_value": "1.75",
  "is_active": false
}
```

---

### Delete Fee Policy

**Endpoint:** `DELETE /api/wallet/admin/wallet/fee-policies/{policy_id}/`

**Description:** Deactivate a fee policy (soft delete).

**Response (204 No Content)**

---

### Ledger Integrity Check

**Endpoint:** `GET /api/wallet/admin/wallet/ledger-integrity/{store_id}/`

**Description:** Verify that journal ledger is balanced and reconciles with wallet balance.

**Response (200 OK):**
```json
{
  "store_id": 1,
  "status": "healthy",
  "checks": {
    "all_entries_balanced": true,
    "total_debits": "10500.00",
    "total_credits": "10500.00",
    "wallet_available": "1500.50",
    "wallet_pending": "250.00",
    "journal_available": "1500.50",
    "journal_pending": "250.00",
    "reconciliation_ok": true
  },
  "unbalanced_entries": [],
  "last_check": "2026-02-25T16:00:00Z"
}
```

**Response (200 with issues):**
```json
{
  "store_id": 1,
  "status": "error",
  "checks": {
    "all_entries_balanced": false,
    "reconciliation_ok": false
  },
  "unbalanced_entries": [98, 105],
  "discrepancies": [
    {
      "type": "balance_mismatch",
      "expected": "1500.50",
      "actual": "1450.00"
    }
  ]
}
```

---

## Error Handling

### Common Error Responses

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**404 Not Found:**
```json
{
  "detail": "Not found."
}
```

**400 Bad Request:**
```json
{
  "field_name": [
    "Error message describing validation issue"
  ]
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error. Please contact support."
}
```

---

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- **Authenticated users:** 1000 requests / hour
- **Unauthenticated:** 100 requests / hour

Rate limit headers in response:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1645795200
```

---

## Pagination

List endpoints support pagination:

```bash
# Default (20 items per page)
GET /api/wallet/stores/1/wallet/ledger/

# Custom page size
GET /api/wallet/stores/1/wallet/ledger/?page_size=50

# Next page
GET /api/wallet/stores/1/wallet/ledger/?page=2
```

Response includes:
- `count` - Total items
- `next` - URL to next page (null if last page)
- `previous` - URL to previous page (null if first page)
- `results` - Array of items

---

## Examples

### JavaScript/Fetch

```javascript
// Get wallet summary
const response = await fetch(
  'https://api.wasla.local/api/wallet/stores/1/wallet/summary/',
  {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  }
);

const data = await response.json();
console.log(`Available: ${data.available_balance}`);
console.log(`Pending: ${data.pending_balance}`);
```

### Python/Requests

```python
import requests

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# Get ledger
response = requests.get(
    'https://api.wasla.local/api/wallet/stores/1/wallet/ledger/',
    headers=headers,
    params={'entry_type': 'payment_captured', 'page_size': 50}
)

for entry in response.json()['results']:
    print(f"{entry['entry_date']} - {entry['reference_id']}: {entry['description']}")
```

### cURL

```bash
# Create withdrawal request
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "500.00",
    "note": "Monthly settlement"
  }' \
  https://api.wasla.local/api/wallet/stores/1/wallet/withdrawals/
```

---

## Changelog

### v1.0 (2026-02-25) - Initial Release
- ✓ Merchant wallet APIs (balance, ledger, withdrawals)
- ✓ Admin withdrawal management APIs
- ✓ Admin fee policy management APIs
- ✓ Ledger integrity checks
