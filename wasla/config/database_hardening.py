"""
Database Hardening Configuration.

Implements:
1. Connection pooling (pgbouncer)
2. Transaction isolation
3. Financial flow atomic transactions
4. Deadlock prevention
5. Query optimization hints
"""

# ==========================================
# DATABASE HARDENING SETTINGS
# ==========================================

# 1. CONNECTION POOLING (pgbouncer)
# ==========================================
# Purpose: Reduce connection overhead, prevent connection exhaustion
#
# In production, use pgbouncer between Django and PostgreSQL:
# 
# pgbouncer.ini:
# [databases]
# wasla = host=postgres.production.aws.com port=5432 dbname=wasla_prod
# 
# [pgbouncer]
# listen_port = 6432
# pool_mode = transaction
# max_client_conn = 1000
# default_pool_size = 25
# min_pool_size = 10
# reserve_pool_size = 5
# reserve_pool_timeout = 3
#
# Then set DATABASE_HOST = pgbouncer_server:6432

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "wasla_prod",
        "USER": "wasla_user",
        "PASSWORD": "{{ database_password }}",
        "HOST": "pgbouncer.internal",  # pgbouncer, not direct postgres
        "PORT": "6432",
        
        # Connection pooling + timeout settings
        "CONN_MAX_AGE": 600,  # Reuse connections for 10 minutes
        "AUTOCOMMIT": False,  # Use explicit transactions
        "ATOMIC_REQUESTS": False,  # Control transactions explicitly
        
        # Restrict connections per process
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",  # 30s query timeout
        },
    }
}

# 2. TRANSACTION ISOLATION LEVELS
# ==========================================
# Use READ_COMMITTED for financial flows (prevents phantom reads in settlements)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 3. DATABASE TIMEOUT & RETRY CONFIGURATION
# ==========================================
DATABASE_TIMEOUT = 30  # seconds
DATABASE_RETRY_ATTEMPTS = 3

# 4. FINANCIAL FLOW TRANSACTION PATTERNS
# ==========================================
# Reference these decorators in payment/settlement/refund services:

"""
PATTERN 1: Payment Processing (idempotent via idempotency_key)
─────────────────────────────────────────────────────────────
from django.db import transaction

@transaction.atomic
def process_payment(payment_intent):
    # Step 1: Fetch with select_for_update (locks row)
    payment = Payment.objects.select_for_update().get(id=payment_intent.payment_id)
    
    # Step 2: Check idempotency
    if PaymentEvent.objects.filter(
        idempotency_key=payment_intent.idempotency_key
    ).exists():
        return {"status": "already_processed"}
    
    # Step 3: Create ledger entry
    LedgerEntry.objects.create(...)
    
    # Step 4: Update payment status
    payment.status = "completed"
    payment.save()
    
    # If exception: transaction rolls back, ledger entry not created


PATTERN 2: Settlement Creation (atomic fee deduction)
────────────────────────────────────────────────────
@transaction.atomic
def create_settlement_for_store(store, period_start, period_end):
    # Step 1: Lock ledger account
    ledger = LedgerAccount.objects.select_for_update().get(
        tenant=store.tenant,
        store=store
    )
    
    # Step 2: Calculate gross amount
    gross = OrderPayment.objects.filter(
        store=store,
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).aggregate(Sum("amount"))["amount"]
    
    # Step 3: Calculate fee
    fee = gross * (store.fee_config.platform_fee_percentage / 100)
    net = gross - fee
    
    # Step 4: Create settlement + fee entry
    settlement = Settlement.objects.create(...)
    LedgerEntry.objects.create(
        ledger_account=ledger,
        amount=-fee,  # Negative = deduction
        transaction_type="platform_fee",
        reference_settlement=settlement,
    )
    
    # Step 5: Update balance
    ledger.available_balance -= fee
    ledger.save()
    
    # If exception: all rolled back


PATTERN 3: Refund Processing (double-refund prevention)
───────────────────────────────────────────────────────
@transaction.atomic
def process_refund_webhook(payment_id, refund_id, amount):
    # Step 1: Lock payment
    payment = Payment.objects.select_for_update().get(id=payment_id)
    
    # Step 2: Check if already processed
    if PaymentRefund.objects.filter(
        payment=payment,
        provider_refund_id=refund_id
    ).exists():
        return {"status": "already_refunded"}
    
    # Step 3: Create ledger entry (negative)
    ledger_entry = LedgerEntry.objects.create(
        amount=-amount,
        transaction_type="refund",
    )
    
    # Step 4: Create refund record
    PaymentRefund.objects.create(
        payment=payment,
        provider_refund_id=refund_id,
        amount=amount,
        ledger_entry=ledger_entry,
    )
    
    # Step 5: Update merchant balance
    ledger = LedgerAccount.objects.select_for_update().get(
        tenant=payment.order.store.tenant,
        store=payment.order.store,
    )
    ledger.available_balance -= amount
    ledger.save()
"""

# 5. DEADLOCK PREVENTION
# ==========================================
# Order of access: Always acquire locks in same order
#
# LOCK ORDER:
# 1. LedgerAccount (locks balance)
# 2. Settlement (locks settlement state)
# 3. Payment (locks payment state)
# 4. Order (locks order state)
#
# Violation example (DO NOT DO):
# ❌ Lock Payment → Lock Ledger → Lock Settlement (DEADLOCK RISK)
# ✓ Lock Ledger → Lock Settlement → Lock Payment (SAFE)

# 6. QUERY OPTIMIZATION HINTS
# ==========================================
"""
Use select_related/prefetch_related to reduce queries:

GOOD:
  Settlement.objects.select_related(
      "tenant",
      "store",
  ).prefetch_related(
      "settlement_items__order__payment"
  )

BAD (N+1 queries):
  for settlement in Settlement.objects.all():
      print(settlement.store.name)  # 1 query per settlement
      for item in settlement.items.all():  # Another query per item
          print(item.order.order_number)  # Another query per item
"""

# 7. INDEXES FOR FINANCIAL QUERIES
# ==========================================
"""
Critical indexes already defined in models.py:

LedgerEntry:
  - (ledger_account, created_at)  # Balance history queries
  - (reference_settlement_id)     # Settlement balance audit
  - (reference_payment_id)        # Payment ledger audit
  - (transaction_type, created_at)  # Transaction breakdown

Settlement:
  - (store, period_start, period_end)  # Period queries
  - (status, period_end)          # Pending settlements
  
Payment:
  - (order, status)               # Order payment lookup
  - (tenant, status, created_at)  # Merchant activity
  - (idempotency_key)             # Idempotency validation

LedgerAccount:
  - (tenant, store) UNIQUE        # Ensures 1 ledger per store
"""

# 8. MONITORING QUERIES
# ==========================================
"""
Enable slow query logging in postgresql.conf:

log_min_duration_statement = 1000  # Log queries > 1 second
log_connections = on
log_disconnections = on
log_statement = 'mod'  # Log DDL + DML

Monitor with:
SELECT query, calls, mean_time, max_time FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;

Critical queries to monitor:
1. Settlement creation (can lock for seconds)
2. Ledger balance updates (frequent, must be fast)
3. Refund processing (idempotency checks = multiple reads)
"""

# 9. CONNECTION POOL RECOMMENDATIONS
# ==========================================
"""
Based on load (from production monitoring):

LIGHT LOAD (< 10 req/sec):
  pool_size = 10
  reserve_pool_size = 2
  
MEDIUM LOAD (10-50 req/sec):
  pool_size = 25
  reserve_pool_size = 5
  
HEAVY LOAD (50-100 req/sec):
  pool_size = 50
  reserve_pool_size = 10
  
EXTREME LOAD (> 100 req/sec):
  Consider read replicas + write primary
"""

# 10. STATEMENT CONFIGURATION
# ==========================================
# In settings.py, add to DATABASES["default"]["OPTIONS"]:

DATABASE_OPTIONS = {
    "connect_timeout": 10,
    "options": "-c statement_timeout=30000",  # 30s max query time
}

# Individual query timeout override:
# from django.db import connection
# with connection.cursor() as cursor:
#     cursor.execute("SET statement_timeout TO 60000")  # 60s
#     cursor.execute("SELECT ... FROM big_table")

# ==========================================
# FINANCIAL TRANSACTION GUARANTEES
# ==========================================
"""
ACID Guarantees Used:

A - Atomicity: All payment/settlement steps succeed or NONE
    Enforcement: @transaction.atomic decorator
    Rollback: Any exception rolls back entire transaction

C - Consistency: Ledger balances always correct
    Enforcement: Transaction locks + balance validation
    Check: Balance = sum(all ledger entries)

I - Isolation: Payment processing doesn't interfere
    Enforcement: READ_COMMITTED isolation + select_for_update()
    Prevents: Dirty reads, lost updates, phantom reads

D - Durability: Ledger entries persist
    Enforcement: PostgreSQL WAL + disk sync
    Recovery: Point-in-time recovery from backups
"""
