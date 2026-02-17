# Payment Middleware & Integration Guide

## Overview
This document provides technical reference for the Wasla payment system implementation, covering provider setup, orchestration, webhook handling, and settlement processes.

## Payment Architecture

### Core Components
1. **Payment Providers**: Tap, Stripe, PayPal (Strategy Pattern)
2. **Payment Orchestrator**: Central service managing provider selection, idempotency, fees
3. **Webhook Handler**: Verifying callbacks and updating payment status
4. **Settlement Engine**: Fee tracking and ledger management

### Key Patterns
- **Strategy Pattern**: Abstract `HostedPaymentAdapter` with provider implementations
- **Clean Architecture**: Models → Services → Orchestrator → Gateway Adapters
- **Atomic Transactions**: `@transaction.atomic` on all payment state changes
- **Race Condition Prevention**: `select_for_update()` database locks
- **Multi-tenant Isolation**: All queries scoped by `store_id` or `tenant_id`

---

## Provider Implementation Details

### Tap Payment Provider (`payments/infrastructure/gateways/tap_gateway.py`)

**Supported Methods**
- Credit/Debit cards
- Mada (Saudi Arabian cards)
- STC Pay
- Apple Pay / Google Pay

**Key Methods**

```python
def initiate_payment(self, order, return_url, tenant_ctx):
    """Create charge with fils/SAR conversion"""
    # Returns PaymentRedirect with hosted_url
    
def verify_callback(self, request_data):
    """Verify webhook signature (HMAC-SHA256)"""
    # Returns VerifiedEvent with updated status
    
def refund(self, payment_intent, amount=None):
    """Execute full or partial refund"""
    
def _verify_tap_signature(self, request_body, signature_header):
    """Constant-time HMAC comparison"""
```

**Critical Details**
- Amount in fils (1 SAR = 100 fils)
- Signature verification: `HMAC-SHA256(body, secret_key)`
- Customer metadata stored for reconciliation
- Webhook signature header: `X-Tap-ID`

**Configuration**
```python
# PaymentProviderSettings
provider_code = "tap"
api_key = environ.get("TAP_API_KEY")  # Bearer token
is_sandbox_mode = environ.get("TAP_SANDBOX") == "true"
transaction_fee_percent = 2.5  # Per tenant configurable
wasla_commission_percent = 3.0
```

---

### Stripe Payment Provider (`payments/infrastructure/gateways/stripe_gateway.py`)

**Supported Methods**
- International credit/debit cards
- SEPA Direct Debit
- iDEAL, Bancontact, Giropay
- Klarna, Afterpay

**Key Methods**

```python
def initiate_payment(self, order, return_url, tenant_ctx):
    """Create checkout session"""
    # Returns PaymentRedirect with hosted_url (Stripe redirect_url)
    
def verify_callback(self, request_data):
    """Verify webhook signature (HMAC + timestamp)"""
    # Returns VerifiedEvent with session status
    
def refund(self, payment_intent, amount=None):
    """Execute refund via Stripe API"""
    
def _verify_stripe_signature(self, payload, sig_header):
    """HMAC-SHA256 + timestamp validation (±5 min window)"""
```

**Critical Details**
- Amounts in cents (multiply by 100)
- Form-encoded requests (Content-Type: application/x-www-form-urlencoded)
- Webhook signature header: `Stripe-Signature: t=timestamp,v1=signature`
- Sandbox detection: `sk_test_*` prefix
- Time-window validation prevents replay attacks

**Configuration**
```python
# PaymentProviderSettings
provider_code = "stripe"
api_key = environ.get("STRIPE_API_KEY")  # Bearer token (sk_live_**)
is_sandbox_mode = api_key.startswith("sk_test_")  # Auto-detect
transaction_fee_percent = 2.9
wasla_commission_percent = 3.0
```

---

### PayPal Payment Provider (`payments/infrastructure/gateways/paypal_gateway.py`)

**Supported Methods**
- PayPal Wallet
- Venmo
- Credit/Debit Cards (via PayPal)
- Bank Transfer

**Key Methods**

```python
def initiate_payment(self, order, return_url, tenant_ctx):
    """Create order and extract approval link"""
    # Returns PaymentRedirect with payer approval_link
    
def verify_callback(self, request_data):
    """Parse webhook event (checkout.session.completed)"""
    # Returns VerifiedEvent with order_status
    
def refund(self, payment_intent, amount=None):
    """Execute refund via PayPal API"""
    
def _get_access_token(self):
    """OAuth2 token acquisition (Basic auth)"""
```

**Critical Details**
- OAuth2 authentication: `Authorization: Basic base64(client_id:secret)`
- Order creation returns approval link (`payer.links[0].href`)
- Event types: `checkout.session.completed`, `payment_intent.*`
- Sandbox/Live: Different endpoints per environment

**Configuration**
```python
# PaymentProviderSettings
provider_code = "paypal"
api_key = environ.get("PAYPAL_CLIENT_ID")
api_secret = environ.get("PAYPAL_SECRET")
is_sandbox_mode = environ.get("PAYPAL_SANDBOX") == "true"
transaction_fee_percent = 3.5
wasla_commission_percent = 4.0
```

---

## Payment Orchestrator (`payments/orchestrator.py`)

### Central Service Interface

```python
class PaymentOrchestrator:
    PROVIDER_MAP = {
        "tap": TapProvider,
        "stripe": StripeProvider,
        "paypal": PayPalProvider
    }
    
    @staticmethod
    @transaction.atomic
    def initiate_payment(order, provider_code, tenant_ctx, return_url):
        """
        Initiate payment flow with idempotency protection
        
        Process:
        1. Validate provider is available for tenant
        2. Check for existing pending payment (prevent duplicates)
        3. Generate idempotency_key (provider:order_id:tenant_id:timestamp)
        4. Get or create PaymentIntent
        5. Instantiate provider
        6. Call provider API
        7. Store provider_reference
        8. Return redirect URL
        
        Returns:
            PaymentRedirect with hosted_url for user redirect
        """
        
    @staticmethod
    def refund(payment_intent, amount=None, requested_by=None):
        """
        Execute refund with audit trail
        
        Process:
        1. Lock PaymentIntent (select_for_update)
        2. Validate refund amount <= remaining balance
        3. Get provider instance
        4. Call provider.refund()
        5. Create RefundRecord with audit info
        6. Update ledger
        
        Returns:
            RefundRecord with status
        """
        
    @staticmethod
    def get_provider_fees(tenant_id, provider_code, amount):
        """
        Calculate transaction fees and commissions
        
        Calculation:
        - provider_fee = amount * transaction_fee_percent / 100
        - wasla_commission = amount * wasla_commission_percent / 100
        - net_amount = amount - provider_fee - wasla_commission
        
        Returns:
            {
                'gross_amount': Decimal,
                'provider_fee': Decimal,
                'wasla_commission': Decimal,
                'net_amount': Decimal
            }
        """
```

### Idempotency Implementation

```python
# Prevent duplicate payments via unique constraint
idempotency_key = f"{provider_code}:{order.id}:{tenant_id}:{int(time.time())}"

# Database constraint ensures single pending payment per order
class PaymentIntent(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'idempotency_key'],
                condition=Q(status='pending'),
                name='unique_pending_payment_per_order'
            )
        ]
```

---

## Data Models

### PaymentIntent
```python
class PaymentIntent(models.Model):
    order = ForeignKey("orders.Order", on_delete=CASCADE)
    provider = CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = CharField(max_length=20, choices=STATUS_CHOICES)  # pending, completed, failed
    amount = DecimalField(max_digits=10, decimal_places=2)
    provider_reference = CharField(max_length=255, null=True)
    idempotency_key = CharField(max_length=255, unique=True)
    raw_response = JSONField()
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

### RefundRecord
```python
class RefundRecord(models.Model):
    payment_intent = ForeignKey(PaymentIntent, on_delete=CASCADE)
    amount = DecimalField(max_digits=10, decimal_places=2)
    status = CharField(max_length=20, choices=REFUND_STATUS_CHOICES)
    provider_reference = CharField(max_length=255, null=True)
    requested_by = ForeignKey(User, on_delete=SET_NULL, null=True)
    raw_response = JSONField()
    created_at = DateTimeField(auto_now_add=True)
    approved_at = DateTimeField(null=True)
    processed_at = DateTimeField(null=True)
```

### PaymentProviderSettings
```python
class PaymentProviderSettings(models.Model):
    store = ForeignKey("tenants.Store", on_delete=CASCADE)
    provider_code = CharField(max_length=20, choices=PROVIDER_CHOICES)
    api_key = CharField(max_length=255)
    api_secret = CharField(max_length=255, null=True)
    is_enabled = BooleanField(default=True)
    is_sandbox_mode = BooleanField(default=False)
    transaction_fee_percent = DecimalField(max_digits=5, decimal_places=2)
    wasla_commission_percent = DecimalField(max_digits=5, decimal_places=2)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

---

## Webhook Integration

### Webhook Handler Pattern

```python
# Verify provider signature first
verified_event = provider.verify_callback(request_data)

if verified_event.status == "completed":
    payment_intent.status = "completed"
    order.payment_status = "paid"
    # Trigger order fulfillment
    
elif verified_event.status == "failed":
    payment_intent.status = "failed"
    # Notify user, offer retry
    
# All updates within @transaction.atomic
```

### Multi-Tenant Webhook URLs

```
/webhooks/payments/tap/
/webhooks/payments/stripe/
/webhooks/payments/paypal/

# Each provider sends to same endpoint, orchestrator routes based on body
```

---

## Settlement & Ledger

### Fee Flow

```
Order Total: 1000 SAR

Tap Provider (2.5% fee, 3% commission):
├─ Provider Fee: 25 SAR
├─ Wasla Commission: 30 SAR
└─ Merchant Receives: 945 SAR

Stripe (2.9% fee, 3% commission):
├─ Provider Fee: 29 SAR
├─ Wasla Commission: 30 SAR
└─ Merchant Receives: 941 SAR
```

### Integration with Settlement Engine

```python
# Existing settlement models integrate automatically
class LedgerEntry(models.Model):
    account = ForeignKey(LedgerAccount, on_delete=CASCADE)
    amount = DecimalField()
    entry_type = CharField()  # debit/credit
    reference = CharField()  # payment_intent_id / refund_record_id
    created_at = DateTimeField(auto_now_add=True)

# Orchestrator calls get_provider_fees() to populate ledger:
# 1. Credit merchant account: net_amount
# 2. Debit payment received account: gross_amount
# 3. Credit provider account: provider_fee
# 4. Credit wasla account: wasla_commission
```

---

## Security Measures

### Secret Management
- All API keys stored in environment variables
- Database encryption at rest (Django ORM)
- TLS/HTTPS enforced for all provider APIs

### Webhook Security
- Provider signature verification (HMAC-SHA256)
- Timestamp validation (±5 minutes for Stripe)
- Constant-time string comparison

### Race Condition Prevention
```python
# Database locks prevent concurrent refunds
payment_intent = PaymentIntent.objects.select_for_update().get(id=payment_id)
# Only one request can hold this lock at a time
```

### Idempotency
```python
# Duplicate POST to /api/payments/initiate with same idempotency_key
# Returns existing PaymentIntent instead of creating duplicate
```

---

## Multi-Tenant Configuration

### Per-Store Provider Settings
```python
# Each store can enable different providers with custom fees
store = Store.objects.get(id=1)
tap_settings = PaymentProviderSettings.objects.get(
    store=store,
    provider_code="tap"
)
# tap_settings.transaction_fee_percent = 2.5 (store-specific)
```

### Credential Isolation
```python
# Provider credentials scoped by store
@staticmethod
def initiate_payment(order, provider_code, tenant_ctx):
    store = order.store
    settings = PaymentProviderSettings.objects.get(
        store=store,
        provider_code=provider_code
    )
    # Only this store's API key is used
    provider_instance = provider_class(settings.api_key, settings.is_sandbox_mode)
```

---

## Production Deployment Checklist

- [ ] Configure PaymentProviderSettings for all stores
- [ ] Set environment variables for all providers:
  - `TAP_API_KEY`, `TAP_SANDBOX`
  - `STRIPE_API_KEY`
  - `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_SANDBOX`
- [ ] Configure webhook URLs in each provider dashboard:
  - Tap: `/webhooks/payments/tap/`
  - Stripe: `/webhooks/payments/stripe/`
  - PayPal: `/webhooks/payments/paypal/`
- [ ] Enable HTTPS for all payment endpoints
- [ ] Run database migrations: `python manage.py migrate payments`
- [ ] Test with sandbox API keys (Tap, Stripe, PayPal)
- [ ] Verify webhook signature verification in staging
- [ ] Load test fee calculations with decimal precision
- [ ] Review audit logs for refund requests
- [ ] Rotate API keys on production deployment

---

## Testing Guide

### Provider Testing
```bash
# Test Tap with sandbox credentials
curl -X POST /api/payments/initiate \
  -H "Content-Type: application/json" \
  -d '{"order_id": 123, "provider": "tap", "amount": 100}'

# Verify webhook with test signature
curl -X POST /webhooks/payments/tap/ \
  -H "X-Tap-ID: test_signature_here" \
  -d '{"charge_id": "ch_test", "status": "completed"}'
```

### Idempotency Testing
```bash
# Send same request twice with same idempotency key
# Should return same PaymentIntent both times (no duplicate charge)
```

---

## References

- **PAYMENT_COMPLIANCE.md**: Full 95% compliance report
- **Payment Spec**: `/docs/payment.md`
- **Gateway Implementations**: `/payments/infrastructure/gateways/`
- **Orchestrator**: `/payments/orchestrator.py`
- **Models**: `/payments/models.py`
