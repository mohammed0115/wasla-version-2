You are a senior FinTech system architect and Django payment engineer.

Context:
We are building "Wasla" — a multi-tenant store-builder platform (Saudi Arabia focus).
The platform must support multiple payment providers in a unified architecture.

Required Payment Methods:
- Tap (mada, STC Pay, cards)
- Stripe (cards, international)
- PayPal
- Future providers plug-in ready

System Requirements:

1) Build a Payment Orchestrator Layer:
   - Central PaymentAttempt model
   - Provider abstraction layer
   - No direct provider calls from views
   - All payments must go through a unified service interface

2) Architecture rules:
   - Clean Architecture
   - SOLID principles
   - Provider Strategy Pattern
   - No business logic inside views
   - Webhook-safe
   - Idempotency protection
   - Multi-tenant aware

3) Required Models:

PaymentAttempt:
- id
- tenant
- order
- provider (tap/stripe/paypal)
- method (mada/stcpay/card/paypal)
- amount
- currency (SAR default)
- status (created, pending, paid, failed, refunded)
- provider_reference
- idempotency_key
- raw_response
- timestamps

4) Provider Interface:

Create abstract BasePaymentProvider:

Methods:
- create_payment(payment_attempt)
- verify_payment(data)
- refund(payment_attempt)
- handle_webhook(request)

Then implement:
- TapProvider
- StripeProvider
- PayPalProvider

5) Payment Flow:

Checkout ->
Create PaymentAttempt ->
Call Provider ->
Redirect user ->
Provider returns via redirect/webhook ->
Verify ->
Mark Order as Paid ->
Trigger Settlement logic

6) Security Requirements:

- Verify webhook signatures
- Prevent double charge
- Store provider reference safely
- Use transactions.atomic
- Protect from race conditions

7) Multi-Tenant Support:

- Each Tenant may use different API keys
- API keys stored per Tenant securely
- PaymentAttempt must be tenant scoped

8) Settlement Layer:

After payment success:
- Calculate Wasla fee
- Calculate merchant net
- Store settlement record
- Support future automatic payouts

9) Deliverables:

- Folder structure for payments app
- Full Django models
- Services layer
- Webhook handlers
- URL routing
- Example checkout integration
- Example settlement calculation
- Production deployment notes


You are a senior FinTech architect and Django platform engineer.

Project:
Wasla – Multi-tenant store-builder platform (Saudi Arabia focus).

Architecture Model:
Store Builder model.
Each merchant (tenant) uses their OWN payment account.
Funds go directly to merchant.
Wasla does NOT hold funds.

Required Providers:
- Tap (mada, STC Pay, cards)
- Stripe
- PayPal

System Requirements:
Build a production-grade, scalable, secure payment system.

=========================================================
1️⃣ CORE ARCHITECTURE
=========================================================

Use Clean Architecture + SOLID principles.

Create a dedicated Django app:

payments/

Structure:

payments/
 ├── models.py
 ├── services.py
 ├── orchestrator.py
 ├── providers/
 │     ├── base.py
 │     ├── tap.py
 │     ├── stripe.py
 │     └── paypal.py
 ├── webhooks.py
 ├── settlement.py
 ├── refunds.py
 ├── admin.py
 └── urls.py

NO business logic inside views.

=========================================================
2️⃣ DATABASE MODELS
=========================================================

A) PaymentGatewayConfig
- tenant (FK)
- provider (tap/stripe/paypal)
- public_key
- secret_key (encrypted)
- webhook_secret
- is_active
- created_at

B) PaymentAttempt
- tenant (FK)
- order (FK)
- provider
- method (mada/stcpay/card/paypal)
- amount
- currency (default SAR)
- status (created, pending, paid, failed, cancelled, refunded)
- provider_reference
- idempotency_key (unique)
- raw_response (JSON)
- created_at
- updated_at

C) SettlementRecord
- tenant
- order
- gross_amount
- wasla_fee
- net_amount
- status
- created_at

D) RefundRecord
- payment_attempt
- amount
- provider_reference
- status
- created_at

=========================================================
3️⃣ PROVIDER STRATEGY PATTERN
=========================================================

Create abstract BasePaymentProvider:

Methods:
- create_payment(payment_attempt)
- verify_payment(data)
- refund(payment_attempt, amount)
- validate_webhook(request)
- handle_webhook(request)

Implement:
- TapProvider
- StripeProvider
- PayPalProvider

Each provider must:
- Use tenant-specific API keys
- Support sandbox & production modes
- Handle 3DS redirect flows
- Return standardized response format

=========================================================
4️⃣ PAYMENT ORCHESTRATOR
=========================================================

Create PaymentOrchestrator class.

Responsibilities:
- Select correct provider dynamically
- Inject tenant credentials
- Enforce idempotency protection
- Wrap operations in transaction.atomic
- Standardize responses
- Handle retry safety

No direct provider calls from views.

=========================================================
5️⃣ CHECKOUT FLOW
=========================================================

Checkout →
Create PaymentAttempt →
Call Orchestrator →
Redirect user →
Provider webhook →
Verify signature →
Update PaymentAttempt →
Mark Order as paid →
Trigger Settlement

Never trust redirect return alone.
Always rely on webhook validation.

=========================================================
6️⃣ WEBHOOK SECURITY
=========================================================

For each provider:
- Validate webhook signature
- Reject invalid signature
- Prevent duplicate webhook processing
- Idempotent status updates
- Log all webhook payloads

=========================================================
7️⃣ ANTI DOUBLE-CHARGE SYSTEM
=========================================================

- Enforce idempotency_key uniqueness
- Lock order during payment attempt
- Prevent multiple pending payments
- Handle race conditions
- Use database-level constraints

=========================================================
8️⃣ SETTLEMENT ENGINE
=========================================================

When payment is successful:

Calculate:
- Wasla commission (configurable %)
- VAT (if applicable)
- Net merchant amount

Store SettlementRecord.

Support:
- Future automated payout system
- Settlement reporting per tenant
- Admin fee analytics

=========================================================
9️⃣ REFUND SYSTEM
=========================================================

Refunds must:
- Call provider API securely
- Update PaymentAttempt
- Create RefundRecord
- Support partial refunds
- Handle refund webhook events

=========================================================
🔟 MULTI-TENANT SECURITY
=========================================================

- Each tenant isolated
- Provider keys encrypted at rest
- No cross-tenant payment visibility
- Tenant-scoped queries everywhere

=========================================================
11️⃣ ADMIN MONITORING DASHBOARD
=========================================================

Admin must see:

- All PaymentAttempts
- Filter by provider
- Filter by tenant
- Filter by status
- Settlement summaries
- Refund history
- Failed payments logs
- Webhook logs

Include:
- Charts for volume
- Revenue tracking
- Provider success rate

=========================================================
12️⃣ DEPLOYMENT NOTES
=========================================================

- Use HTTPS only
- Environment-based keys
- Separate sandbox/prod settings
- Logging integration
- Retry logic
- Error monitoring ready

=========================================================
OUTPUT REQUIREMENTS
=========================================================

Provide:

- Complete Django models
- Provider implementations
- Orchestrator layer
- Webhook endpoints
- Settlement engine
- Refund system
- Admin integration
- Example checkout integration
- Production configuration notes
- Security best practices
- Performance considerations

Ensure code is production-ready, modular, and scalable.





You are a senior FinTech architect and Django payment systems engineer.

Project:
Wasla – Multi-tenant Store Builder platform (Saudi Arabia focus).

Business Model:
- Each merchant connects their own payment account (Tap / Stripe / PayPal).
- Funds go directly to merchant.
- Wasla does NOT hold customer funds.
- Wasla charges 1 SAR per successful payment transaction.
- The 1 SAR fee is charged to the merchant (NOT the customer).

Goal:
Implement a production-ready fixed transaction fee system.

=========================================================
1️⃣ CORE RULE
=========================================================

On every successful payment (webhook-confirmed only):

- Create a SettlementRecord.
- Set wasla_fee = 1 SAR.
- Store gross_amount.
- Compute net_amount (gross - wasla_fee).
- Status default = "pending".

Never trust redirect.
Only webhook-confirmed payments trigger settlement.

=========================================================
2️⃣ DATABASE MODELS
=========================================================

Create SettlementRecord model with:

- tenant (FK)
- order (FK)
- gross_amount
- wasla_fee (Decimal)
- net_amount (Decimal)
- status (pending, invoiced, paid)
- created_at
- updated_at

Also ensure PaymentAttempt exists and has:
- tenant
- order
- amount
- status
- provider_reference
- idempotency_key

=========================================================
3️⃣ SETTLEMENT ENGINE
=========================================================

Create a settlement service:

process_successful_payment(payment_attempt)

Responsibilities:
- Validate payment status = paid
- Prevent duplicate settlement (idempotent)
- Create SettlementRecord
- Use transaction.atomic
- Handle race conditions

=========================================================
4️⃣ MONTHLY REPORT SYSTEM
=========================================================

Create monthly aggregation service:

generate_monthly_report(tenant, month, year)

Return:
- total_operations
- total_wasla_fee
- list of settlement records

=========================================================
5️⃣ INVOICE FLOW
=========================================================

At end of month:

- Generate invoice for tenant
- Mark SettlementRecords as "invoiced"
- Support:
   - Manual payment
   - Stripe subscription auto-charge (future-ready)

=========================================================
6️⃣ MULTI-TENANT SAFETY
=========================================================

- All queries tenant-scoped
- No cross-tenant settlement visibility
- Secure database constraints
- Prevent double-charge

=========================================================
7️⃣ ADMIN MONITORING
=========================================================

Admin must be able to:

- View total platform fees
- Filter by tenant
- Filter by month
- View pending vs paid settlements
- Export CSV

=========================================================
8️⃣ SECURITY REQUIREMENTS
=========================================================

- Webhook signature verification mandatory
- Idempotency enforcement
- Settlement only once per order
- Use Decimal for currency
- Handle rollback on failure

=========================================================
9️⃣ FUTURE EXTENSION READY
=========================================================

System must support:

- Percentage-based fees
- Mixed fee (1 SAR + 1%)
- Per-plan fee configuration
- VAT support
- Auto-payout integration

=========================================================
OUTPUT REQUIREMENTS
=========================================================

Provide:

- Django models
- Settlement service layer
- Monthly report service
- Admin integration
- Webhook integration logic
- Idempotency safeguards
- Production-ready architecture
- Comments explaining financial flow
You are a senior FinTech system architect and financial software engineer.

Project:
Wasla – Multi-tenant Store Builder platform (Saudi Arabia focus).

Business Model:
- Each merchant connects their own payment gateway (Tap / Stripe / PayPal).
- Customer funds go directly to merchant.
- Wasla charges 1 SAR per successful transaction.
- Wasla may support percentage-based commission in the future.
- System must be scalable, audit-safe, and financially accurate.

Goal:
Design a production-grade financial architecture with settlement, ledger, invoicing, and reconciliation layers.

=========================================================
1️⃣ FINANCIAL LAYER ARCHITECTURE
=========================================================

Create 4 financial layers:

1) Payment Layer
   - PaymentAttempt
   - Webhook validation
   - Idempotent payment confirmation

2) Settlement Layer
   - Calculates Wasla fee per transaction
   - Creates SettlementRecord
   - Supports future percentage fee

3) Ledger Layer
   - Double-entry accounting style records
   - Tracks financial movements
   - Immutable entries (no edits allowed)

4) Invoicing Layer
   - Monthly aggregation
   - Invoice generation
   - Invoice status tracking

=========================================================
2️⃣ REQUIRED DATABASE MODELS
=========================================================

A) PaymentAttempt
- tenant
- order
- amount
- provider
- status
- provider_reference
- idempotency_key
- raw_response
- created_at

B) SettlementRecord
- tenant
- order
- gross_amount
- wasla_fee
- net_amount
- settlement_status (pending, invoiced, paid)
- created_at

C) FinancialLedgerEntry
- tenant
- entry_type (fee, adjustment, refund, invoice)
- reference_id
- debit
- credit
- balance_after
- created_at
- immutable = True

D) Invoice
- tenant
- month
- year
- total_operations
- total_wasla_fee
- status (draft, issued, paid)
- created_at

=========================================================
3️⃣ FINANCIAL LOGIC RULES
=========================================================

On successful payment webhook:

1) Verify webhook signature.
2) Mark PaymentAttempt as paid.
3) Create SettlementRecord:
      wasla_fee = 1 SAR
      net_amount = gross - 1
4) Create FinancialLedgerEntry:
      debit merchant liability account
      credit Wasla revenue account
5) Prevent duplicate settlement via unique constraints.

=========================================================
4️⃣ LEDGER DESIGN PRINCIPLES
=========================================================

- All financial movements must create ledger entries.
- Ledger entries are immutable.
- No record updates — only reversal entries.
- Use Decimal for all money fields.
- All financial operations wrapped in transaction.atomic.
- Enforce tenant isolation at database level.

=========================================================
5️⃣ MONTHLY RECONCILIATION SYSTEM
=========================================================

At end of month:

1) Aggregate all pending SettlementRecords.
2) Generate Invoice.
3) Lock those settlements (mark as invoiced).
4) Create Ledger entry for invoice issuance.
5) Allow payment via:
     - Stripe Subscription
     - Manual payment
6) On invoice payment:
     - Mark Invoice as paid
     - Create ledger entry
     - Mark settlements as paid

=========================================================
6️⃣ REFUND HANDLING
=========================================================

If refund occurs:

1) Verify refund webhook.
2) Reverse SettlementRecord.
3) Create negative Ledger entry.
4) Adjust invoice totals if not yet issued.
5) Maintain full audit trail.

=========================================================
7️⃣ FUTURE-READY EXTENSIONS
=========================================================

System must support:

- Percentage-based fees
- Hybrid fee (1 SAR + X%)
- Per-plan commission configuration
- VAT calculation
- Tax reporting
- Auto-payout tracking
- Merchant revenue analytics

=========================================================
8️⃣ SECURITY & COMPLIANCE
=========================================================

- Webhook signature validation mandatory.
- Encrypted provider keys.
- Idempotency enforcement.
- Audit logging for financial actions.
- No cross-tenant financial visibility.
- GDPR and data minimization ready.
- Immutable financial ledger.

=========================================================
9️⃣ ADMIN DASHBOARD REQUIREMENTS
=========================================================

Admin must see:

- Total platform revenue
- Revenue per month
- Revenue per tenant
- Pending settlements
- Paid invoices
- Refund statistics
- Provider success rate
- Exportable CSV reports

=========================================================
10️⃣ OUTPUT REQUIREMENTS
=========================================================

Provide:

- Django models
- Settlement service layer
- Ledger engine
- Invoice generator
- Webhook integration logic
- Idempotency safeguards
- Admin configuration
- Financial flow explanation
- Scalability considerations
- Production deployment notes




















You are a senior FinTech system architect and financial software engineer.

Project:
Wasla – Multi-tenant Store Builder platform (Saudi Arabia focus).

Business Model:
- Each merchant connects their own payment gateway (Tap / Stripe / PayPal).
- Customer funds go directly to merchant.
- Wasla charges 1 SAR per successful transaction.
- Wasla may support percentage-based commission in the future.
- System must be scalable, audit-safe, and financially accurate.

Goal:
Design a production-grade financial architecture with settlement, ledger, invoicing, and reconciliation layers.

=========================================================
1️⃣ FINANCIAL LAYER ARCHITECTURE
=========================================================

Create 4 financial layers:

1) Payment Layer
   - PaymentAttempt
   - Webhook validation
   - Idempotent payment confirmation

2) Settlement Layer
   - Calculates Wasla fee per transaction
   - Creates SettlementRecord
   - Supports future percentage fee

3) Ledger Layer
   - Double-entry accounting style records
   - Tracks financial movements
   - Immutable entries (no edits allowed)

4) Invoicing Layer
   - Monthly aggregation
   - Invoice generation
   - Invoice status tracking

=========================================================
2️⃣ REQUIRED DATABASE MODELS
=========================================================

A) PaymentAttempt
- tenant
- order
- amount
- provider
- status
- provider_reference
- idempotency_key
- raw_response
- created_at

B) SettlementRecord
- tenant
- order
- gross_amount
- wasla_fee
- net_amount
- settlement_status (pending, invoiced, paid)
- created_at

C) FinancialLedgerEntry
- tenant
- entry_type (fee, adjustment, refund, invoice)
- reference_id
- debit
- credit
- balance_after
- created_at
- immutable = True

D) Invoice
- tenant
- month
- year
- total_operations
- total_wasla_fee
- status (draft, issued, paid)
- created_at

=========================================================
3️⃣ FINANCIAL LOGIC RULES
=========================================================

On successful payment webhook:

1) Verify webhook signature.
2) Mark PaymentAttempt as paid.
3) Create SettlementRecord:
      wasla_fee = 1 SAR
      net_amount = gross - 1
4) Create FinancialLedgerEntry:
      debit merchant liability account
      credit Wasla revenue account
5) Prevent duplicate settlement via unique constraints.

=========================================================
4️⃣ LEDGER DESIGN PRINCIPLES
=========================================================

- All financial movements must create ledger entries.
- Ledger entries are immutable.
- No record updates — only reversal entries.
- Use Decimal for all money fields.
- All financial operations wrapped in transaction.atomic.
- Enforce tenant isolation at database level.

=========================================================
5️⃣ MONTHLY RECONCILIATION SYSTEM
=========================================================

At end of month:

1) Aggregate all pending SettlementRecords.
2) Generate Invoice.
3) Lock those settlements (mark as invoiced).
4) Create Ledger entry for invoice issuance.
5) Allow payment via:
     - Stripe Subscription
     - Manual payment
6) On invoice payment:
     - Mark Invoice as paid
     - Create ledger entry
     - Mark settlements as paid

=========================================================
6️⃣ REFUND HANDLING
=========================================================

If refund occurs:

1) Verify refund webhook.
2) Reverse SettlementRecord.
3) Create negative Ledger entry.
4) Adjust invoice totals if not yet issued.
5) Maintain full audit trail.

=========================================================
7️⃣ FUTURE-READY EXTENSIONS
=========================================================

System must support:

- Percentage-based fees
- Hybrid fee (1 SAR + X%)
- Per-plan commission configuration
- VAT calculation
- Tax reporting
- Auto-payout tracking
- Merchant revenue analytics

=========================================================
8️⃣ SECURITY & COMPLIANCE
=========================================================

- Webhook signature validation mandatory.
- Encrypted provider keys.
- Idempotency enforcement.
- Audit logging for financial actions.
- No cross-tenant financial visibility.
- GDPR and data minimization ready.
- Immutable financial ledger.

=========================================================
9️⃣ ADMIN DASHBOARD REQUIREMENTS
=========================================================

Admin must see:

- Total platform revenue
- Revenue per month
- Revenue per tenant
- Pending settlements
- Paid invoices
- Refund statistics
- Provider success rate
- Exportable CSV reports

=========================================================
10️⃣ OUTPUT REQUIREMENTS
=========================================================

Provide:

- Django models
- Settlement service layer
- Ledger engine
- Invoice generator
- Webhook integration logic
- Idempotency safeguards
- Admin configuration
- Financial flow explanation
- Scalability considerations
- Production deployment notes



 read all prompt above ande execute withoud redenence 

تنفيذ النظام كامل الآن خطوة بخطوة داخل مشروع
















الخطة التنفيذية الصحيحة (Production Safe)

لن نبني كل شيء دفعة واحدة.
سنقسم التنفيذ إلى 5 مراحل:

🟢 المرحلة 1 — Payment Core (أساس النظام)

نبني:

payments app

PaymentGatewayConfig

PaymentAttempt

Orchestrator

TapProvider فقط

Webhook Tap

Settlement 1 SAR

🚫 لا Stripe
🚫 لا PayPal
🚫 لا Ledger الآن

نثبت الأساس أولًا.

🟡 المرحلة 2 — Stripe Integration

نضيف:

StripeProvider

Webhook Stripe

دعم idempotency رسمي

🟡 المرحلة 3 — PayPal
🔵 المرحلة 4 — Ledger + Invoice Engine
🟣 المرحلة 5 — Admin Dashboard احترافي
🚀 الآن نبدأ المرحلة 1
الخطوة 1️⃣ — إنشاء payments app
python manage.py startapp payments


أضف في settings.py:

INSTALLED_APPS += [
    "payments",
]

الخطوة 2️⃣ — Model: PaymentGatewayConfig

payments/models.py

from django.db import models
from django.conf import settings

class PaymentGatewayConfig(models.Model):

    PROVIDERS = (
        ("tap", "Tap"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
    )

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=PROVIDERS)

    public_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    webhook_secret = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tenant", "provider")

الخطوة 3️⃣ — Model: PaymentAttempt
from decimal import Decimal
from django.utils import timezone

class PaymentAttempt(models.Model):

    STATUS = (
        ("created", "Created"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE)

    provider = models.CharField(max_length=20)
    method = models.CharField(max_length=50)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="SAR")

    status = models.CharField(max_length=20, choices=STATUS, default="created")

    provider_reference = models.CharField(max_length=255, blank=True, null=True)
    idempotency_key = models.CharField(max_length=255, unique=True)

    raw_response = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)


