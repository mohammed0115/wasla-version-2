# Payment Security Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PAYMENT PROCESSING FLOW                           │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────────┐
         │ 1. IDEMPOTENCY LAYER      │
         │ Generate/Check Key        │
         │ ├─ store_id               │
         │ ├─ order_id               │
         │ └─ client_token           │
         │                           │
         │ DB Constraint:            │
         │ UNIQUE(store, order, key) │
         │                           │
         │ Result: ✓✓ NO DUPLICATES │
         └────────┬──────────────────┘
                  │
         ┌────────▼──────────────────┐
         │ 2. WEBHOOK SECURITY       │
         │ ├─ HMAC-SHA256 Validate   │
         │ ├─ Check Signature        │
         │ ├─ Timing-attack safe     │
         │ └─ Constant-time compare  │
         │                           │
         │ Result: ✓✓ VERIFIED      │
         └────────┬──────────────────┘
                  │
         ┌────────▼──────────────────┐
         │ 3. REPLAY PROTECTION      │
         │ ├─ Validate timestamp     │
         │ ├─ Check time window      │
         │ │  (5 min tolerance)      │
         │ ├─ Event deduplication    │
         │ └─ UNIQUE(provider,       │
         │    event_id)              │
         │                           │
         │ Result: ✓✓ FRESH         │
         └────────┬──────────────────┘
                  │
         ┌────────▼──────────────────┐
         │ 4. FRAUD DETECTION        │
         │ Risk Score (0-100):       │
         │ ├─ New customer (+10)     │
         │ ├─ IP velocity 5m (+20)   │
         │ ├─ IP velocity 1h (+15)   │
         │ ├─ Unusual amount (+15)   │
         │ └─ Failed attempts (+5-20)│
         │                           │
         │ Flag: score > 75 ?        │
         │ ├─ YES → Manual review    │
         │ └─ NO → Proceed           │
         │                           │
         │ Result: ✓✓ SCORED        │
         └────────┬──────────────────┘
                  │
         ┌────────▼──────────────────┐
         │ 5. RETRY STRATEGY         │
         │ Exponential Backoff:      │
         │ ├─ Attempt 1: 1s          │
         │ ├─ Attempt 2: 2s          │
         │ ├─ Attempt 3: 4s          │
         │ └─ Max: 60s               │
         │                           │
         │ Jitter: ±10%              │
         │ Max: 3 attempts           │
         │                           │
         │ Result: ✓✓ RESILIENT    │
         └────────┬──────────────────┘
                  │
         ┌────────▼──────────────────┐
         │ 6. AUDIT LOGGING          │
         │ Structured JSON:          │
         │ ├─ timestamp              │
         │ ├─ event_type             │
         │ ├─ provider               │
         │ ├─ status                 │
         │ ├─ duration_ms            │
         │ ├─ risk_score             │
         │ └─ metadata               │
         │                           │
         │ Result: ✓✓ LOGGED       │
         └────────┬──────────────────┘
                  │
         ┌────────▼──────────────────┐
         │  PAYMENT RESULT           │
         │  ├─ Success (paid)        │
         │  ├─ Pending review        │
         │  ├─ Failed                │
         │  └─ Retrying              │
         └───────────────────────────┘
```

## Component Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       REQUEST HANDLING                            │
│                   (Django View/Webhook Handler)                   │
└─────────────────────┬────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
   ┌────▼────────────┐      ┌──────▼──────────────┐
   │ MIDDLEWARE      │      │  WEBHOOK RECEIVER   │
   │ (Optional)      │      │  (CSRF Exempt)      │
   │ ├─ Signature    │      │  ├─ Parse JSON     │
   │ ├─ Timestamp    │      │  ├─ Extract headers│
   │ └─ IP filter    │      │  └─ Build context  │
   └────┬────────────┘      └──────┬──────────────┘
        │                           │
        └───────────────┬───────────┘
                        │
            ┌───────────▼──────────────┐
            │ WebhookSecurityHandler   │
            │ .process_webhook()       │
            │                          │
            │ Returns: (event, risk)   │
            └───────────┬──────────────┘
                        │
            ┌───────────▼──────────────────────┐
            │ Security Module Integration       │
            │ (apps/payments/security.py)       │
            │                                   │
            │ ├─ IDempotencyValidator           │
            │ ├─ RetryStrategy                  │
            │ ├─ RiskScoringEngine              │
            │ └─ Logging utilities              │
            └───────────┬──────────────────────┘
                        │
            ┌───────────▼──────────────┐
            │ DATA MODELS              │
            │ (apps/payments/models.py)│
            │                          │
            │ ├─ PaymentAttempt       │
            │ ├─ WebhookEvent         │
            │ ├─ PaymentRisk          │
            │ └─ PaymentProviderSettings
            └───────────┬──────────────┘
                        │
            ┌───────────▼──────────────┐
            │ DATABASE PERSISTENCE     │
            │                          │
            │ ├─ Create records        │
            │ ├─ Update status         │
            │ ├─ Log events            │
            │ └─ Enforce constraints   │
            └──────────────────────────┘
```

## Data Flow - Complete Payment Lifecycle

```
Customer Payment Request
        │
        ├─ Create PaymentAttempt
        │  ├─ status: 'created'
        │  ├─ idempotency_key: GENERATED
        │  ├─ ip_address: CAPTURED
        │  └─ Save to DB
        │
        ├─ Call Payment Provider
        │  └─ Stripe/PayPal/Square
        │
        │ (Provider processing...)
        │
        ├─ Receive Webhook
        │  ├─ Extract signature
        │  ├─ Extract timestamp
        │  ├─ Extract payload
        │  └─ Build WebhookContext
        │
        ├─ Security Validation
        │  ├─ HMAC-SHA256 validate ──→ reject if bad
        │  ├─ Timestamp check ───────→ reject if old
        │  ├─ Event deduplication ──→ return if duplicate
        │  └─ Save WebhookEvent
        │
        ├─ Create PaymentRisk
        │  ├─ Calculate risk_score (0-100)
        │  ├─ Determine risk_level
        │  ├─ Identify triggered_rules
        │  └─ Flag if score > 75
        │
        ├─ Update PaymentAttempt
        │  ├─ status: 'confirmed'
        │  ├─ webhook_verified: true
        │  ├─ webhook_event: FK link
        │  └─ confirmed_at: timestamp
        │
        ├─ Risk Review Decision
        │  │
        │  ├─ If low risk → Auto-confirm
        │  │  └─ status: 'paid'
        │  │
        │  ├─ If high risk → Flag for review
        │  │  └─ PaymentRisk.flagged: true
        │  │     Notify risk team
        │  │
        │  └─ Admin decides
        │     ├─ Approve → proceed
        │     └─ Reject → mark failed
        │
        ├─ Retry Logic (if failed)
        │  │
        │  ├─ Check should_retry()
        │  │  └─ Retryable statuses: created, pending, retry_pending
        │  │
        │  ├─ Calculate backoff
        │  │  ├─ 1st retry: 1s
        │  │  ├─ 2nd retry: 2s
        │  │  ├─ 3rd retry: 4s
        │  │  └─ Plus jitter: ±10%
        │  │
        │  └─ Schedule next_retry_after
        │     Update PaymentAttempt.retry_pending = true
        │
        └─ Audit Log
           Store structured JSON event:
           {
             "timestamp": "2024-01-15T10:15:00Z",
             "event_type": "webhook_processed",
             "provider": "stripe",
             "order_id": 456,
             "amount": 100.00,
             "risk_score": 35,
             "idempotency_key": "xyz...abc"
           }
```

## Database Schema - Key Tables

```
┌─────────────────────────────────────┐
│       PAYMENT_ATTEMPT               │
├─────────────────────────────────────┤
│ id (PK)                             │
│ order_id (FK)                       │
│ store_id (FK) ◄─ Multi-tenant       │
│ provider                            │
│ amount                              │
│ currency                            │
│ status ◄─ [created, pending, paid...] │
│ idempotency_key ◄─ UNIQUE + INDEX   │
│ provider_reference                  │
│ ip_address ◄─ Security               │
│ user_agent ◄─ Security               │
│ webhook_event_id (FK)               │
│ webhook_verified ◄─ INDEX            │
│ retry_count                         │
│ retry_pending ◄─ INDEX               │
│ next_retry_after ◄─ Scheduler        │
│ raw_response (JSON)                 │
│ created_at                          │
│ confirmed_at                        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      WEBHOOK_EVENT                  │
├─────────────────────────────────────┤
│ id (PK)                             │
│ provider                            │
│ event_id ◄─ Provider webhook ID     │
│ store_id (FK) ◄─ Multi-tenant       │
│ payload_json                        │
│ payload_hash ◄─ SHA256              │
│ signature_verified ◄─ INDEX         │
│ timestamp_tolerance...              │
│ webhook_timestamp ◄─ Replay check   │
│ idempotency_key ◄─ Replay preven.   │
│ status ◄─ [pending, processed...]   │
│ retry_count                         │
│ last_error                          │
│ idempotency_checked                 │
│ CONSTRAINT: UNIQUE(provider,        │
│             event_id)               │
│ created_at                          │
│ processed_at                        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      PAYMENT_RISK                   │
├─────────────────────────────────────┤
│ id (PK)                             │
│ order_id (FK)                       │
│ store_id (FK) ◄─ Multi-tenant       │
│ payment_attempt_id (FK)             │
│ risk_score (0-100) ◄─ Threshold:75  │
│ risk_level ◄─ [low, medium, high..] │
│ flagged ◄─ INDEX + Manual review    │
│ ip_address                          │
│ velocity_count_5min ◄─ Attack det.  │
│ velocity_count_1hour                │
│ velocity_amount_5min                │
│ refund_rate_percent                 │
│ previous_failed_attempts            │
│ is_new_customer                     │
│ unusual_amount ◄─ Anomaly detect.   │
│ triggered_rules (JSON array)        │
│ reviewed ◄─ Workflow                │
│ reviewed_by (FK: User)              │
│ reviewed_at                         │
│ review_decision ◄─ [approved, ...]  │
│ review_notes (Text)                 │
│ created_at                          │
│ updated_at                          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  PAYMENT_PROVIDER_SETTINGS          │
├─────────────────────────────────────┤
│ id (PK)                             │
│ provider_code (UNIQUE)              │
│ webhook_secret (ENCRYPTED)          │
│ webhook_timeout_seconds             │
│ retry_max_attempts                  │
│ idempotency_key_required            │
│ is_active                           │
│ created_at                          │
│ updated_at                          │
└─────────────────────────────────────┘
```

## Database Indexes

```
PAYMENT_ATTEMPT
├─ idempotency_key (UNIQUE) ◄─ Idempotency enforcement
├─ (order_id, status) ◄─ Payment lookup
├─ (store_id, created_at) ◄─ Tenant-scoped queries
├─ (webhook_verified, status) ◄─ Verification checks
└─ retry_pending ◄─ Retry scheduler

WEBHOOK_EVENT
├─ (provider, event_id) (UNIQUE) ◄─ Replay prevention
├─ (store_id, status) ◄─ Status queries
├─ signature_verified ◄─ Validation checks
└─ created_at ◄─ Timeline queries

PAYMENT_RISK
├─ (order_id, store_id) ◄─ Risk lookup
├─ flagged (INDEX) ◄─ Admin review queue
├─ reviewed ◄─ Approval workflow
└─ created_at ◄─ Timeline queries
```

## API Routes

```
Admin Routes:
  GET  /api/v1/admin/payment-risk/
       └─ List flagged payments (with filters)
       └─ Query: ?risk_level=high&reviewed=false
  
  POST /api/v1/admin/payment-risk/{id}/approve/
       └─ Approve risky payment
       └─ Body: {"review_notes": "..."}
  
  POST /api/v1/admin/payment-risk/{id}/reject/
       └─ Reject risky payment
       └─ Body: {"review_notes": "..."}
  
  GET  /api/v1/admin/webhook-events/
       └─ Webhook event log
       └─ Query: ?provider=stripe&signature_verified=true
  
  GET  /api/v1/admin/payment-attempts/{id}/
       └─ Payment attempt details (with webhooks & risks)

Merchant Routes:
  GET  /api/v1/orders/{order_id}/payment-status/
       └─ Order payment timeline
       └─ Shows: attempts, webhooks, events

Configuration Routes:
  GET  /api/v1/admin/provider-settings/
       └─ List all providers
  
  GET  /api/v1/admin/provider-settings/{provider_code}/
       └─ Provider details (masked secrets)
  
  PATCH /api/v1/admin/provider-settings/{provider_code}/
       └─ Update settings
```

## Security Validation Pipeline

```
Raw Webhook Request
        │
        ├─ Step 1: Extract Headers
        │  ├─ X-Webhook-Signature
        │  ├─ X-Webhook-Timestamp
        │  └─ X-Signature (alternate names)
        │
        ├─ Step 2: Signature Validation
        │  ├─ Get webhook_secret from DB
        │  ├─ Compute HMAC-SHA256(secret, raw_body)
        │  ├─ Compare with header signature
        │  │  └─ Using: hmac.compare_digest()  ◄─ Timing-attack safe
        │  └─ Result: signature_verified (bool)
        │       └─ FALSE → REJECT (403)
        │       └─ TRUE → Continue
        │
        ├─ Step 3: Timestamp Validation
        │  ├─ Parse timestamp from header
        │  ├─ Calculate age: now - timestamp
        │  ├─ Check: age < tolerance_seconds (300s default)
        │  └─ Result: timestamp_valid (bool)
        │       └─ FALSE → REJECT (403, "replay attack")
        │       └─ TRUE → Continue
        │
        ├─ Step 4: Event Deduplication
        │  ├─ Extract: provider + event_id
        │  ├─ Check: existing WebhookEvent
        │  │  └─ UNIQUE(provider, event_id) enforced
        │  └─ Result: is_duplicate (bool)
        │       └─ TRUE → Return cached result
        │       └─ FALSE → Create new event
        │
        ├─ Step 5: Risk Assessment
        │  ├─ Calculate risk_score (0-100)
        │  ├─ Identify triggered_rules
        │  ├─ Create PaymentRisk record
        │  └─ Result: risk_level
        │       └─ HIGH/CRITICAL → Flag for manual review
        │       └─ LOW/MEDIUM → Proceed automatically
        │
        ├─ Step 6: Audit Logging
        │  ├─ Structured JSON event
        │  ├─ Log to: payment_security.log
        │  ├─ Shipped to: ELK/Datadog/CloudWatch
        │  └─ Retention: 90 days
        │
        └─ Step 7: Payment Processing
           ├─ Update PaymentAttempt
           ├─ Update Order status
           └─ Trigger fulfillment workflow
```

## Retry Flow Diagram

```
Payment Attempt Fails
        │
        ├─ Check: should_retry(status, retry_count, max_retries)
        │
        ├─ Retryable Statuses? (created, pending, retry_pending)
        │  │
        │  ├─ YES ◄─ Continue to scheduling
        │  │
        │  └─ NO ◄─ TERMINAL STATE
        │     └─ Mark as 'failed' or 'cancelled'
        │
        ├─ Within max retries? (default: 3)
        │  │
        │  ├─ YES ◄─ Continue to scheduling
        │  │
        │  └─ NO ◄─ EXHAUSTED
        │     └─ Mark as 'failed'
        │
        ├─ Calculate Backoff Delay
        │  ├─ Formula: delay = min(1 * 2^retry_count, 60)
        │  ├─ Attempt 0: 2^0 = 1 second
        │  ├─ Attempt 1: 2^1 = 2 seconds
        │  ├─ Attempt 2: 2^2 = 4 seconds
        │  └─ Max: 60 seconds
        │
        ├─ Add Jitter
        │  ├─ Jitter = ±10% of delay
        │  ├─ Example: 2s ± 0.2s = [1.8s, 2.2s]
        │  └─ Purpose: Prevent thundering herd
        │
        ├─ Schedule Next Retry
        │  ├─ next_retry_after = now + delay_with_jitter
        │  ├─ Update PaymentAttempt.next_retry_after
        │  ├─ Set retry_pending = true
        │  ├─ Increment retry_count
        │  └─ Status: 'retry_pending'
        │
        └─ Background Job Scheduler
           ├─ Polls: WHERE retry_pending=true AND next_retry_after <= now
           ├─ Executes: retry_payment(attempt_id)
           └─ Repeats until success or exhaustion

Result States:
  ✓ Payment Succeeded
    └─ status: 'paid'
    └─ confirmed_at: timestamp
  
  ✗ Retries Exhausted
    └─ status: 'failed'
    └─ last_error: "Max retries exceeded"
  
  ⌛ Waiting for Retry
    └─ status: 'retry_pending'
    └─ next_retry_after: future_timestamp
```

---

**This diagram suite provides complete visual understanding of:**
- Security layer pipeline
- Component interactions
- Data flow lifecycle
- Database schema with relationships
- API route organization
- Validation pipeline details
- Retry recovery mechanism

For code details, see: [apps/payments/security.py](apps/payments/security.py)
