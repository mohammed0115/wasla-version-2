# SaaS Recurring Billing System - API Quick Reference

## Authentication

All API requests require Bearer token authentication:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" https://api.yourdomain.com/api/billing/subscriptions/
```

## Base URL

```
https://api.yourdomain.com/api/billing
```

---

## Subscriptions

### List Subscriptions

```bash
GET /subscriptions/
```

**Query Parameters**:
- `state`: active | past_due | grace | suspended | cancelled
- `plan_id`: Filter by plan UUID
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

**Example**:
```bash
curl -H "Authorization: Bearer TOKEN" \
  "https://api.yourdomain.com/api/billing/subscriptions/?state=active&page_size=50"
```

**Response** (200 OK):
```json
{
  "count": 42,
  "next": "https://api.yourdomain.com/api/billing/subscriptions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "state": "active",
      "plan": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Professional",
        "price": "299.00",
        "billing_cycle": "monthly"
      },
      "next_billing_date": "2024-03-01",
      "currency": "SAR",
      "created_at": "2024-01-15T10:30:00Z",
      "tenant": "Acme Store"
    }
  ]
}
```

### Create Subscription

```bash
POST /subscriptions/
```

**Request Body**:
```json
{
  "plan_id": "550e8400-e29b-41d4-a716-446655440001",
  "billing_cycle_anchor": 1,
  "currency": "SAR"
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "active",
  "plan": {...},
  "next_billing_date": "2024-02-28",
  "created_at": "2024-01-16T08:15:00Z",
  "message": "Subscription created successfully"
}
```

### Get Subscription Details

```bash
GET /subscriptions/{id}/
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "active",
  "plan": {...},
  "payment_method": {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "method_type": "card",
    "display_name": "Visa ending in 4242",
    "status": "active"
  },
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440003",
      "name": "Monthly Subscription",
      "price": "299.00",
      "billing_type": "fixed"
    }
  ],
  "next_billing_date": "2024-02-28",
  "currency": "SAR",
  "started_at": "2024-01-15T10:30:00Z",
  "suspended_at": null,
  "cancelled_at": null
}
```

### Change Subscription Plan

```bash
POST /subscriptions/{id}/change_plan/
```

**Request Body**:
```json
{
  "plan_id": "550e8400-e29b-41d4-a716-446655440004",
  "effective_date": "2024-02-20"
}
```

**Response** (200 OK):
```json
{
  "subscription": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "plan": {
      "id": "550e8400-e29b-41d4-a716-446655440004",
      "name": "Enterprise",
      "price": "999.00"
    },
    "state": "active"
  },
  "proration": {
    "current_plan_cost": "299.00",
    "new_plan_cost": "999.00",
    "days_remaining": 10,
    "daily_rate_current": "9.97",
    "daily_rate_new": "33.30",
    "credit": "99.70",
    "charge": "333.00",
    "net_proration": 233.30,
    "description": "Upgrade from Professional to Enterprise"
  },
  "message": "Plan changed successfully. Proration of SAR 233.30 will be applied."
}
```

### Cancel Subscription

```bash
POST /subscriptions/{id}/cancel/
```

**Request Body**:
```json
{
  "reason": "Too expensive",
  "immediately": false
}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "cancelled",
  "cancelled_at": "2024-02-20T10:30:00Z",
  "cancellation_reason": "Too expensive",
  "message": "Subscription cancelled successfully"
}
```

### Suspend Subscription (Admin Only)

```bash
POST /subscriptions/{id}/suspend/
```

**Request Body**:
```json
{
  "reason": "Non-payment"
}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "suspended",
  "suspended_at": "2024-02-20T10:30:00Z",
  "suspension_reason": "Non-payment",
  "message": "Subscription suspended"
}
```

### Reactivate Subscription (Admin Only)

```bash
POST /subscriptions/{id}/reactivate/
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "active",
  "suspended_at": null,
  "suspension_reason": null,
  "message": "Subscription reactivated"
}
```

### Add Grace Period

```bash
POST /subscriptions/{id}/add_grace_period/
```

**Request Body**:
```json
{
  "days": 7
}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "grace",
  "grace_until": "2024-02-27T00:00:00Z",
  "message": "Grace period added until 2024-02-27"
}
```

### Get Billing Status

```bash
GET /subscriptions/{id}/billing_status/
```

**Response** (200 OK):
```json
{
  "state": "active",
  "next_billing_date": "2024-02-28",
  "outstanding_balance": 0.00,
  "currency": "SAR",
  "payment_method_status": "valid",
  "days_until_next_billing": 5,
  "is_overdue": false,
  "grace_period_active": false,
  "outstanding_invoices": [],
  "recent_payment": {
    "date": "2024-01-28",
    "amount": "299.00"
  }
}
```

---

## Invoices

### List Invoices

```bash
GET /invoices/
```

**Query Parameters**:
- `subscription_id`: Filter by subscription UUID
- `status`: issued | overdue | paid | partial | draft | void
- `issued_after`: ISO date (2024-01-01)
- `issued_before`: ISO date (2024-02-01)
- `overdue_only`: true | false

**Example**:
```bash
curl -H "Authorization: Bearer TOKEN" \
  "https://api.yourdomain.com/api/billing/invoices/?status=overdue"
```

**Response** (200 OK):
```json
{
  "count": 3,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440010",
      "number": "INV-202402-001",
      "status": "overdue",
      "subscription_id": "550e8400-e29b-41d4-a716-446655440000",
      "total": "299.00",
      "amount_paid": "0.00",
      "amount_due": "299.00",
      "currency": "SAR",
      "issued_date": "2024-01-01",
      "due_date": "2024-01-15",
      "paid_date": null,
      "days_overdue": 36
    }
  ]
}
```

### Get Invoice Details

```bash
GET /invoices/{id}/
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440010",
  "number": "INV-202402-001",
  "status": "overdue",
  "subscriptionId": "550e8400-e29b-41d4-a716-446655440000",
  "billing_cycle": {
    "id": "550e8400-e29b-41d4-a716-446655440020",
    "period_start": "2024-01-01",
    "period_end": "2024-01-31"
  },
  "subtotal": "299.00",
  "tax": "44.85",
  "discount": "0.00",
  "total": "343.85",
  "amount_paid": "0.00",
  "amount_due": "343.85",
  "currency": "SAR",
  "issued_date": "2024-01-01",
  "due_date": "2024-01-15",
  "paid_date": null,
  "dunning_attempts": [
    {
      "attempt_number": 1,
      "status": "failed",
      "scheduled_for": "2024-01-18",
      "error_message": "Card declined"
    }
  ]
}
```

---

## Payment Methods

### Get Payment Method

```bash
GET /payment-methods/
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "method_type": "card",
  "display_name": "Visa ending in 4242",
  "status": "active",
  "added_at": "2024-01-15T10:30:00Z",
  "expires_at": "2026-12-31T23:59:59Z",
  "last_used_at": "2024-02-01T08:15:00Z"
}
```

### Create/Update Payment Method

```bash
POST /payment-methods/
```

**Request Body** (Stripe):
```json
{
  "method_type": "card",
  "payment_method_id": "pm_test_1234567890",
  "provider": "stripe"
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "method_type": "card",
  "display_name": "Visa ending in 4242",
  "status": "active",
  "message": "Payment method updated successfully"
}
```

---

## Webhooks

### Receive Webhook Event

```bash
POST /webhooks/
```

**Headers**:
```
Content-Type: application/json
X-Webhook-Signature: hmac-sha256=abcd1234...
```

**Request Body** (Stripe):
```json
{
  "id": "evt_1234567890",
  "type": "payment_intent.succeeded",
  "creation_date": "2024-02-20T10:30:00Z",
  "data": {
    "object": {
      "id": "pi_1234567890",
      "amount": "29900",
      "currency": "sar",
      "customer": "cus_1234567890",
      "status": "succeeded"
    }
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "event_id": "evt_1234567890",
  "message": "Webhook processed successfully"
}
```

---

## Dunning Management

### Get Dunning Status

```bash
GET /dunning/{subscription_id}/
```

**Response** (200 OK):
```json
{
  "subscription_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ongoing",
  "attempts": [
    {
      "attempt_number": 1,
      "status": "failed",
      "scheduled_for": "2024-01-18",
      "attempted_at": "2024-01-18T03:00:00Z",
      "error_message": "Card declined",
      "next_retry_at": "2024-01-21"
    },
    {
      "attempt_number": 2,
      "status": "pending",
      "scheduled_for": "2024-01-21",
      "attempted_at": null,
      "error_message": null,
      "next_retry_at": "2024-01-26"
    }
  ],
  "outstanding_invoice": {
    "number": "INV-202402-001",
    "amount_due": "343.85",
    "days_overdue": 36
  }
}
```

### Retry Dunning Attempt

```bash
POST /dunning/{attempt_id}/retry/
```

**Response** (200 OK):
```json
{
  "attempt_number": 2,
  "status": "pending",
  "scheduled_for": "2024-02-20T03:00:00Z",
  "message": "Dunning attempt scheduled for retry"
}
```

---

## Billing Cycles

### List Billing Cycles

```bash
GET /billing-cycles/
```

**Query Parameters**:
- `subscription_id`: Filter by subscription
- `status`: pending | billed | paid | failed
- `period_after`: ISO date

**Response** (200 OK):
```json
{
  "count": 5,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440020",
      "period_start": "2024-02-01",
      "period_end": "2024-02-29",
      "status": "billed",
      "subtotal": "299.00",
      "tax": "44.85",
      "total": "343.85",
      "invoice_date": "2024-02-01",
      "due_date": "2024-02-15"
    }
  ]
}
```

---

## Error Codes

| Status | Code | Message | Action |
|--------|------|---------|--------|
| 400 | INVALID_PLAN | Plan not found | Verify plan_id exists |
| 400 | INVALID_STATE_TRANSITION | Cannot transition from X to Y | Check subscription state |
| 402 | PAYMENT_REQUIRED | Payment method needed | Update payment method |
| 404 | NOT_FOUND | Subscription not found | Verify subscription ID |
| 409 | CONFLICT | Subscription already exists | Check idempotency key |
| 500 | INTERNAL_ERROR | Unexpected error | Try again or contact support |

---

## Rate Limits

- Standard endpoints: 1000 req/hour per user
- Webhook endpoints: 10000 req/hour per IP
- Burst: Max 10 requests per second

When rate limited, response includes:

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
```

---

## Pagination

All list endpoints support pagination:

```json
{
  "count": 100,
  "next": "https://api.yourdomain.com/api/billing/invoices/?page=2",
  "previous": null,
  "results": [...]
}
```

**Parameters**:
- `page`: Page number (1-based)
- `page_size`: Items per page (1-100, default: 20)

---

## Date Format

All dates are in ISO 8601 format (UTC):

```
2024-02-20T10:30:00Z
```

---

## Example Workflows

### Onboard New Customer

```bash
# 1. Create subscription
curl -X POST https://api.yourdomain.com/api/billing/subscriptions/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "pro-plan-uuid",
    "billing_cycle_anchor": 1,
    "currency": "SAR"
  }'

# Response includes subscription ID

# 2. Add payment method
curl -X POST https://api.yourdomain.com/api/billing/payment-methods/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "method_type": "card",
    "payment_method_id": "pm_xxxxx",
    "provider": "stripe"
  }'

# 3. Monitor billing status
curl https://api.yourdomain.com/api/billing/subscriptions/{id}/billing_status/ \
  -H "Authorization: Bearer TOKEN"
```

### Handle Payment Failure

```bash
# 1. Your system receives webhook notification
# POST /webhooks/ with payment.failed event

# 2. Check dunning status
curl https://api.yourdomain.com/api/billing/dunning/{subscription_id}/ \
  -H "Authorization: Bearer TOKEN"

# 3. Notify customer (manually if needed)
# or system automatically sends notification

# 4. Add grace period (admin)
curl -X POST https://api.yourdomain.com/api/billing/subscriptions/{id}/add_grace_period/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{"days": 7}'
```

---

For more details, see [BILLING_DEPLOYMENT_GUIDE.md](./BILLING_DEPLOYMENT_GUIDE.md)
