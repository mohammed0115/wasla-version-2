# BNPL Integration Guide

**Buy Now Pay Later (BNPL)** integration for Wasla enables customers to purchase items with payment installments through Saudi Arabia's leading BNPL providers: **Tabby** and **Tamara**.

## Overview

### Supported Providers

- **Tabby** - 4 interest-free installments
- **Tamara** - 3-12 flexible payment plans

### Key Features

- ✅ Multi-provider support (can enable both simultaneously)
- ✅ Sandbox/production mode switching per provider
- ✅ Webhook signature verification
- ✅ Order state management
- ✅ Payment status tracking
- ✅ Refund support
- ✅ Audit trail (webhook logs)
- ✅ Multi-store configuration

## Architecture

### Data Models

#### BnplProvider
Stores provider credentials and configuration per store.

```python
BnplProvider(
    store=Store,                 # Which store
    provider='tabby'|'tamara',   # Provider type
    api_key=str,                 # API credential
    secret_key=str,              # Optional secret
    merchant_id=str,             # Merchant ID
    is_active=bool,              # Enable/disable provider
    is_sandbox=bool,             # Sandbox vs production
    webhook_secret=str,          # For signature verification
)
```

**Admin Interface**: Manage providers, toggle active status, switch sandbox mode

#### BnplTransaction
Tracks payment state for each BNPL order.

```python
BnplTransaction(
    order=Order,                           # Related order (unique per provider)
    provider='tabby'|'tamara',             # Payment provider
    provider_order_id=str,                 # ID from provider (unique)
    provider_reference=str,                # Additional reference
    amount=Decimal,                        # Payment amount (SAR)
    currency='SAR',                        # Currency
    status='pending'|'approved'|'paid'..., # Payment state
    installment_count=int,                 # Number of installments
    installment_amount=Decimal,            # Per-installment amount
    customer_email=str,                    # Customer contact
    customer_phone=str,                    # Customer contact
    payment_url=str,                       # URL to provider checkout
    checkout_id=str,                       # Session ID from provider
    response_data=dict,                    # Full API response
)
```

**Status Values**:
- `PENDING` - Checkout session created, awaiting customer action
- `AUTHORIZED` - Payment authorized, awaiting approval
- `APPROVED` - Payment approved by provider
- `REJECTED` - Payment rejected by provider
- `CANCELLED` - Order cancelled before payment
- `PAID` - Payment completed and settled
- `REFUNDED` - Full or partial refund processed

**Admin Interface**: View transactions, see webhook logs, check provider responses

#### BnplWebhookLog
Audit trail for all webhook events from providers.

```python
BnplWebhookLog(
    transaction=BnplTransaction,      # Payment reference
    event_type=str,                   # e.g., 'payment.approved'
    status=str,                       # Status from webhook
    payload=dict,                     # Full webhook data
    signature_verified=bool,          # Cryptographic validation
    processed=bool,                   # Idempotency check
    error_message=str,                # Error details if failed
)
```

### Service Layer

#### BnplPaymentOrchestrator
Routes operations to correct provider adapter.

```python
# Create payment session
result = BnplPaymentOrchestrator.create_payment_session(
    order=order_instance,
    provider='tabby'  # or 'tamara'
)
# Returns: {
#     "status": "success",
#     "checkout_url": "https://provider.com/...",
#     "session_id": "...",
# }

# Process webhook event
result = BnplPaymentOrchestrator.process_webhook(
    provider='tabby',
    payload=webhook_payload,
    signature=request_signature
)

# Get current status
result = get_bnpl_transaction_status(transaction_id)

# Refund payment
result = refund_bnpl_payment(transaction_id, amount=Decimal('500.00'))
```

#### Provider Adapters

**TabbyAdapter** & **TamaraAdapter** implement the **BnplProviderInterface**:

```python
class BnplProviderInterface:
    def create_session(order: Order) -> dict
    def get_payment_status(provider_order_id: str) -> dict
    def verify_webhook_signature(payload: str, signature: str) -> bool
    def refund(provider_order_id: str, amount: Decimal) -> dict
```

## Setup & Configuration

### 1. Enable BNPL App

The BNPL app is automatically enabled in `settings.py`:

```python
INSTALLED_APPS = [
    ...
    "apps.bnpl.apps.BnplConfig",  # ← Added
]
```

### 2. Add Provider Credentials

Via Django Admin:

1. Navigate to **BNPL → BNPL Providers**
2. Click **Add Provider**
3. Fill in:
   - **Store**: Select your store
   - **Provider**: Choose Tabby or Tamara
   - **API Key**: From provider dashboard
   - **Merchant ID**: From provider dashboard
   - **Secret Key** (optional): Additional credential
   - **Webhook Secret**: For signature verification
   - **Is Sandbox**: Toggle for sandbox/production mode

### 3. Test Credentials

Use provider's sandbox credentials initially:

```python
# Example Tabby Sandbox
BNPL_PROVIDER = BnplProvider.objects.create(
    store=store,
    provider='tabby',
    api_key='pk_test_...',
    merchant_id='wasla_sa',
    webhook_secret='webhook_secret_key',
    is_sandbox=True,  # ← Sandbox mode
)
```

## Payment Flow

### Step 1: Initiate Payment

**Endpoint**: `GET /checkout/bnpl/initiate/<order_id>/?provider=tabby|tamara`

**Authentication**: User must own the order

**Process**:
1. Verify provider is configured for the store
2. Create checkout session with provider API
3. Create `BnplTransaction` record
4. Redirect customer to provider's checkout URL

**Response**: Redirect to provider or error

```python
# Example
from apps.bnpl.services import BnplPaymentOrchestrator

result = BnplPaymentOrchestrator.create_payment_session(order, 'tabby')
if result['status'] == 'success':
    return redirect(result['checkout_url'])
```

### Step 2: Customer Payment

Customer completes payment on provider's platform.

### Step 3: Return Redirect

Provider redirects customer to one of:
- Success: `/checkout/bnpl-success/?checkout_id=...`
- Failure: `/checkout/bnpl-failure/?checkout_id=...&reason=...`
- Cancel: `/checkout/bnpl-cancel/?checkout_id=...`

**Status updated** in `BnplTransaction` automatically.

### Step 4: Webhook Notification

Provider sends webhook to your server:
- **Tabby**: `POST /api/webhooks/tabby/`
- **Tamara**: `POST /api/webhooks/tamara/`

**Headers**:
- `X-Tabby-Signature` or `X-Tamara-Signature` for signature verification
- `Content-Type: application/json`

**Webhook Processing**:
1. Verify cryptographic signature
2. Find transaction by `order_reference_id`
3. Update transaction status
4. Log webhook event
5. Update order status if payment approved

**Status Mapping**:

| Webhook Status | BnplTransaction Status |
|---|---|
| CREATED | PENDING |
| APPROVED | APPROVED |
| REJECTED | REJECTED |
| CLOSED | PAID |
| EXPIRED | CANCELLED |

### Step 5: Order Confirmation

Once payment is `PAID`, order is marked as `processing` and:
- Order confirmation email sent
- Inventory updated
- Fulfillment begins

## Integration Examples

### For Customer Checkout Flow

```html
<!-- Checkout page with BNPL option -->
<div class="payment-methods">
    <h2>Choose Payment Method</h2>
    
    <!-- BNPL Options -->
    {% if available_bnpl_providers %}
        {% if 'tabby' in available_bnpl_providers %}
            <button onclick="payWithBnpl('tabby')">
                💳 Pay with Tabby (4 installments)
            </button>
        {% endif %}
        
        {% if 'tamara' in available_bnpl_providers %}
            <button onclick="payWithBnpl('tamara')">
                💳 Pay with Tamara (flexible plans)
            </button>
        {% endif %}
    {% endif %}
</div>

<script>
function payWithBnpl(provider) {
    const orderId = "{{ order.id }}";
    window.location.href = `/checkout/bnpl/initiate/${orderId}/?provider=${provider}`;
}
</script>
```

### For Order Status Check

```python
from apps.bnpl.services import get_bnpl_transaction_status

# In order admin or customer portal
if hasattr(order, 'bnpltransaction'):
    result = get_bnpl_transaction_status(order.bnpltransaction.id)
    status = result.get('status')
    provider_status = result.get('provider_status')
```

### For Refund Processing

```python
from apps.bnpl.services import refund_bnpl_payment
from decimal import Decimal

if hasattr(order, 'bnpltransaction'):
    # Full refund
    result = refund_bnpl_payment(order.bnpltransaction.id)
    
    # Partial refund
    result = refund_bnpl_payment(
        order.bnpltransaction.id,
        amount=Decimal('250.00')  # Refund 250 SAR
    )
```

## Webhook Signature Verification

Each provider signs webhooks with their secret key.

**Example (HMAC-SHA256)**:

```python
import hmac
import hashlib

# From BnplProvider.webhook_secret
secret = provider_config.webhook_secret

# Request body as received
payload = request.body  # bytes

# Signature from header
signature = request.META['HTTP_X_TABBY_SIGNATURE']

# Compute expected signature
expected = hmac.new(
    secret.encode(),
    payload,
    hashlib.sha256
).hexdigest()

# Verify
is_valid = hmac.compare_digest(expected, signature)
```

**Automatic Verification**: The `BnplPaymentOrchestrator.process_webhook()` method handles this.

## Admin Interface

### BNPL Providers

**Path**: `/admin/bnpl/bnplprovider/`

**Actions**:
- ✅ View all configured providers
- ✅ Add new provider
- ✅ Edit credentials
- ✅ Toggle active status
- ✅ Switch sandbox mode
- ✅ Manage webhook secrets

**Filters**:
- By provider (Tabby/Tamara)
- By status (Active/Inactive)
- By mode (Sandbox/Production)

### BNPL Transactions

**Path**: `/admin/bnpl/bnpltransaction/`

**Features**:
- View all payment transactions
- See current status with color coding
- View provider's full API response
- View related webhook logs
- Search by order ID, email, phone
- Filter by status, provider, date

**Status Colors**:
- 🟡 PENDING (yellow)
- 🔵 AUTHORIZED (cyan)
- 🟢 APPROVED (green)
- 🔴 REJECTED (red)
- ⚫ CANCELLED (gray)
- 🟢 PAID (light green)
- 🟣 REFUNDED (purple)

### Webhook Logs

**Path**: `/admin/bnpl/bnplwebhooklog/`

**Purpose**: Audit trail for all webhooks

**Details**:
- Event type (payment.approved, payment.rejected, etc.)
- Event status from webhook
- Full payload logged
- Signature verification status (✓/✗)
- Processing status (✓/⏳)
- Error messages if failed
- Timestamp

## Testing

### Unit Tests

```bash
cd /home/mohamed/Desktop/wasla-version-2/wasla

# Run all BNPL tests
python manage.py test apps.bnpl

# Run specific test class
python manage.py test apps.bnpl.tests.TabbyAdapterTest

# Run with coverage
coverage run --source='apps.bnpl' manage.py test apps.bnpl
coverage report
```

### Manual Testing

1. **Create test provider** (sandbox mode):
   ```python
   from apps.bnpl.models import BnplProvider
   
   BnplProvider.objects.create(
       store=store,
       provider='tabby',
       api_key='pk_test_...',
       is_sandbox=True,
   )
   ```

2. **Create test order** and initiate BNPL payment

3. **Capture webhooks** using webhook testing tools:
   - ngrok for local testing
   - RequestBin/Webhook.cool for payload inspection

4. **Verify** webhook logs in admin

### Webhook Testing with curl

```bash
# Send test webhook to your local server
curl -X POST http://localhost:8000/api/webhooks/tabby/ \
  -H "Content-Type: application/json" \
  -H "X-Tabby-Signature: signature_here" \
  -d '{
    "order": {"reference_id": "123"},
    "status": "APPROVED"
  }'
```

## Security Considerations

### 1. Credential Storage

```python
# API keys stored in database
# Recommendations:
# - Use Django Cryptography package for encryption at rest
# - Rotate credentials regularly
# - Never log API keys
# - Use separate test/production credentials
```

### 2. Webhook Signature Verification

✅ **Automatic**: All webhooks verify `HMAC-SHA256` signature using `webhook_secret`

```python
# Signature verification is mandatory
adapter.verify_webhook_signature(payload, signature)
# → Returns False if invalid, webhook not processed
```

### 3. Idempotency

Webhook logs have `processed` flag to prevent duplicate handling:

```python
# If webhook already processed, skip
if webhook_log.processed:
    return {"status": "success", "duplicate": True}
```

### 4. Sandbox Mode

- Toggle `is_sandbox=True` for testing
- Separate URLs for sandbox vs production APIs
- Use test credentials only in sandbox

### 5. Rate Limiting

Webhook endpoints have no rate limit (to accept provider webhooks).

For payment initiation, standard checkout rate limits apply.

## Troubleshooting

### Issue: "Provider not configured"

**Cause**: No active `BnplProvider` for this store

**Solution**:
1. Go to Admin → BNPL → BNPL Providers
2. Ensure a provider exists
3. Check `is_active` is enabled
4. Verify store association

### Issue: Webhook signature verification failed

**Cause**: Mismatched webhook secret

**Solution**:
1. Verify `webhook_secret` matches provider's configuration in provider's dashboard
2. Check if provider recently rotated the secret
3. Ensure you're using the correct header field (`X-Tabby-Signature` vs `X-Tamara-Signature`)

### Issue: Transaction status not updating

**Cause**: Webhook not reaching your server

**Solution**:
1. Check `BnplWebhookLog` table for webhook events
2. Verify webhook URL is correctly configured in provider's dashboard
3. Check server logs for request errors
4. Ensure CSRF exemption: `@csrf_exempt` on webhook views

### Issue: OrderedDict or JSON serialization errors

**Cause**: Provider response has complex data types

**Solution**:
The `response_data` JSONField automatically serializes provider responses. Ensure your JSON encoder handles all types.

## Performance Considerations

### Database Queries

- BnplTransaction has indexes on: `order`, `provider_order_id`, `status`, `created_at`
- BnplWebhookLog has indexes on: `transaction`, `event_type`, `created_at`

### API Calls

- Provider API calls timeout after 10 seconds
- Consider caching provider status (e.g., check status every 5 minutes, not per request)
- Implement exponential backoff for retries

### Webhook Processing

- Async webhook processing not yet implemented
- For high volume, consider Celery task queue:

```python
from celery import shared_task

@shared_task
def process_bnpl_webhook(provider, payload, signature):
    return BnplPaymentOrchestrator.process_webhook(
        provider, payload, signature
    )
```

## API Reference

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/checkout/bnpl/initiate/<order_id>/` | Initiate payment |
| POST | `/api/webhooks/tabby/` | Tabby webhook |
| POST | `/api/webhooks/tamara/` | Tamara webhook |

### Service Functions

```python
# Create payment session
BnplPaymentOrchestrator.create_payment_session(order, 'tabby')

# Process webhook
BnplPaymentOrchestrator.process_webhook('tabby', payload, signature)

# Get transaction status
get_bnpl_transaction_status(transaction_id)

# Refund payment
refund_bnpl_payment(transaction_id, amount=None)

# Get available providers
get_available_bnpl_providers(store_id)
```

## Future Enhancements

- [ ] Async webhook processing with Celery
- [ ] Payment analytics dashboard
- [ ] Installment plan customization
- [ ] Fraud detection integration
- [ ] Multi-currency support
- [ ] Recurring payment support
- [ ] Mobile SDK integration
- [ ] 3-D Secure support

## Compliance

- ✅ PCI DSS: API keys not exposed in logs
- ✅ Signature verification prevents man-in-the-middle attacks
- ✅ Webhook audit trail (BnplWebhookLog)
- ✅ Payment state tracking for reconciliation
- ✅ Order tracking for fulfillment compliance
