# Wallet Admin Guide

Complete procedures for wallet system administrators and support staff.

---

## Dashboard Access

### Admin Portal URL
```
https://wasla.local/admin_portal/wallet/
```

### Required Permissions
- Staff account (is_staff=True)
- Superuser OR Wallet Manager role

---

## Withdrawal Management

### Viewing Pending Withdrawals

1. **Navigate** to Admin Portal → Wallet → Withdrawal Queue
2. **View all pending withdrawals** across all merchants
3. **Filter by:**
   - Status (Pending, Approved, In Transit, Paid, Rejected)
   - Store/Merchant name
   - Date range
   - Amount range (optional)

**Column Layout:**
| Column | Description |
|--------|-------------|
| Reference | Unique withdrawal ID (e.g., WD-2026-00045) |
| Store | Merchant's store name |
| Merchant | Owner name and email |
| Amount | Withdrawal amount in USD |
| Status | Current state (Pending, Approved, etc.) |
| Requested | Date/time merchant requested |
| Processed | Date/time admin processed |
| Actions | Details, Approve, Reject buttons |

---

### Processing a Withdrawal Request

#### Step 1: Review Request
1. Click **"Details"** button for withdrawal
2. Verify:
   - ✓ Merchant account is KYC verified
   - ✓ Available balance covers amount
   - ✓ No suspicious activity flags
   - ✓ Withdrawal reason (if provided)

#### Step 2: Approve Withdrawal
1. Click **"Approve Withdrawal"** button
2. System confirms:
   - Balance will be deducted from merchant's available balance
   - Amount reserved from platform cash
3. Status changes to **"Approved"**
4. Merchant receives notification email

#### Step 3: Process Payment
1. For **approved** withdrawals, initiate bank transfer:
   - Get payout reference from bank (ACH, Wire, etc.)
   - Verify recipient bank account
   - Initiate transfer in payment system
2. Once bank confirms transfer:
   - Click **"Mark as Paid"**
   - Enter payout reference (e.g., "WIRE-123456" or "ACH-789")
3. System:
   - Deducts amount from merchant's available balance
   - Posts journal entry (Merchant Payment × Bank Clearing)
   - Marks withdrawal as "Paid"
   - Sends confirmation email to merchant

**Timeline:**
- Pending → Approved: Immediate
- Approved → Paid: 1-3 business days (bank processing)

---

### Rejecting a Withdrawal

1. For withdrawals in **"Pending"** status only
2. Click **"Reject Withdrawal"**
3. Provide mandatory rejection reason:
   - "KYC verification pending"
   - "Insufficient balance"
   - "Account flagged for review"
   - "Invalid bank account information"
   - Custom reason (max 500 chars)
4. System:
   - Marks as "Rejected"
   - Notifies merchant with reason
   - Balance remains in merchant's account
   - Merchant can re-submit later

**Common Rejection Scenarios:**
| Reason | Action | Next Step |
|--------|--------|-----------|
| KYC not verified | Reject | Merchant must complete KYC |
| Account suspended | Reject | Admin must lift suspension |
| Duplicate request | Approve first, reject duplicate | Contact merchant |
| Incorrect bank info | Reject | Merchant updates account |

---

### Bulk Withdrawal Processing

For daily settlement runs (>10 withdrawals):

```bash
# Django shell
python manage.py shell

from apps.wallet.models import WithdrawalRequest
from apps.wallet.services.wallet_service import WalletService

# Get pending withdrawals for approval
pending = WithdrawalRequest.objects.filter(
    status='pending',
    created_at__lte=timezone.now() - timedelta(hours=24)
)

# Approve all (after manual verification)
for wd in pending:
    WalletService.approve_withdrawal(wd.id, approved_by=request.user)

print(f"Approved {pending.count()} withdrawals")
```

---

## Fee Policy Management

### Viewing Fee Policies

1. **Navigate** to Admin Portal → Wallet → Fee Policies
2. **View policies grouped by scope:**
   - 🌍 **Global** - Base policy for all merchants
   - 📊 **Plan-Level** - Specific to subscription plan
   - 🏪 **Store-Specific** - Custom rate for single merchant

**Display Format:**
- Card-based for global/plan
- Table format for store-specific
- Shows: Name, Type, Rate, Scope, Status
- Buttons: Edit, Deactivate

---

### Creating a New Fee Policy

#### Global Policy (Default Rate)

1. Click **"Create Policy"** button
2. Fill in details:
   - **Name:** e.g., "Standard 2.5% Commission"
   - **Fee Type:** 
     - Percentage (e.g., 2.5%)
     - Fixed (e.g., $0.50 per order)
   - **Fee Value:** The rate amount
   - **Minimum Fee:** Optional (e.g., $0.50)
   - **Maximum Fee:** Optional cap
   - **Scope:** Select "Global"
   - **Status:** Check "Active"
3. Click **"Save"**
4. Policy applies to all new transactions

Example:
```
Name: Standard 2.5% Commission
Type: Percentage
Value: 2.50%
Min: $0.50
Max: (none)
Applies to: Shipping and Discounts
Active: Yes
```

#### Plan-Level Policy

For a specific subscription plan (e.g., "Premium Plan"):

1. Click **"Create Policy"**
2. Select **Scope:** "Plan"
3. Choose **Subscription Plan:** "Premium" (dropdown)
4. Set fee rate and parameters
5. Click **"Save"**

Plan policies **override global** for merchants on that plan.

#### Store-Specific Policy

For a single merchant (negotiated rate):

1. Click **"Create Policy"**
2. Select **Scope:** "Store"
3. Choose **Store:** Search and select merchant's store
4. Set custom fee rate
5. Click **"Save"**

Store policies have **highest priority** (override plan & global).

---

### Editing an Existing Policy

1. Click **"Edit"** on the policy card/row
2. Modify fields:
   - Rate/value
   - Min/max fees
   - Application rules
   - Active status
3. Click **"Save"**

⚠️ **Warning:** Changes apply to **new orders only**. Existing orders retain original fee.

---

### Deactivating a Policy

1. Click **"Deactivate"** button on policy
2. Policy marked as **Inactive**
3. System falls back to next policy in hierarchy:
   - If store policy inactive → use plan policy
   - If plan policy inactive → use global policy
   - If global inactive → ERROR (must have at least one active policy)

**You cannot delete policies** - only deactivate them (for audit trail).

---

### Policy Hierarchy

When calculating fees, policies are evaluated in priority order:

```
1. Store-Specific Policies (if active)
   ↓ (not found or inactive)
2. Plan-Level Policies (if active)
   ↓ (not found or inactive)
3. Global Default Policy (must be active)
```

Example:
```
Order for "Premium Store" (plan: Premium)

Check 1: Is store "Premium Store" in storage table?
  → Found "1% Premium Store Custom"
  → APPLY 1% fee

(If store policy inactive, check plan next)
```

---

## Monitoring & Reporting

### Wallet Health Dashboard

Track system metrics:

```
Dashboard → Wallet → Metrics

- Total Merchant Wallets: 1,234
- Total Available Balance: $45,230.50
- Total Pending Balance: $12,340.00
- Outstanding Withdrawals: 45
  - Pending Approval: 12
  - Approved: 8
  - Paid: 25
- % Withdrawal Approval Rate: 94%
- Avg Processing Time: 1.2 days
```

---

### Ledger Reconciliation

Verify accounting is correct:

1. **Navigate** to Wallet → Ledger Integrity
2. Select **Store** to check
3. System validates:
   - All journal entries are balanced (debit = credit)
   - Wallet balance matches ledger total
   - No orphaned transactions
4. **Results:**
   - ✓ Green = All checks passed
   - ⚠️ Yellow = Minor issues
   - ✗ Red = Critical errors (contact engineering)

---

### Transaction Reports

Export data for accounting:

```bash
# Django management command
python manage.py wallet_export_transactions \
  --store=all \
  --date_from=2026-01-01 \
  --date_to=2026-02-28 \
  --format=csv \
  --output=wallet_transactions_feb2026.csv
```

Report includes:
- Entry date, type, reference, description
- Account debits and credits
- Running balance
- Merchant name and store

---

## Troubleshooting

### Issue: Merchant Balance Mismatch

**Symptoms:**
- Merchant says balance is wrong
- Transaction doesn't appear in ledger

**Resolution:**
1. Check journal entries:
   ```bash
   python manage.py shell
   from apps.wallet.models import JournalEntry, Wallet
   
   store = Store.objects.get(id=STORE_ID)
   wallet = store.wallet
   entries = JournalEntry.objects.filter(store=store).order_by('-created_at')
   
   # Print last 20 entries
   for e in entries[:20]:
     print(f"{e.created_at} {e.entry_type}: {e.reference_id}")
   ```

2. Verify wallet balance reconciliation:
   ```bash
   # In Wallet → Ledger Integrity, run check
   # Should show: "Reconciliation OK"
   ```

3. If unbalanced entry found:
   - **Do not manually edit**
   - Contact engineering with entry ID
   - May need to post reversing entry

---

### Issue: Withdrawal Stuck in "Approved"

**Symptoms:**
- Admin approved withdrawal 5+ days ago
- Still showing as "Approved" not "Paid"
- Merchant following up

**Resolution:**
1. Check bank transfer status:
   - Look up payout reference in bank system
   - Confirm transfer actually sent
2. If not sent:
   - Initiate transfer now
   - Get confirmation from bank
3. Mark as Paid:
   - Click "Mark as Paid"
   - Enter correct payout reference
   - Merchant receives confirmation

---

### Issue: Double Charging

**Symptoms:**
- Merchant charged twice for same order
- Journal shows duplicate entries

**Resolution:**
1. Verify idempotency key:
   ```bash
   from apps.wallet.models import JournalEntry
   entries = JournalEntry.objects.filter(
     reference_id='ORD-12345'
   )
   print(f"Found {entries.count()} entries")
   ```

2. If multiple entries for same order:
   - Check idempotency keys
   - Should be: payment-ORD-12345, delivery-ORD-12345, etc.
   - If duplicate, contact engineering

3. If fee charged but not adjusted:
   - Post reversing entry:
   ```bash
   WalletService.on_refund(
     store=store,
     order_id='ORD-12345',
     amount=Decimal('2.50'),  # fee only
     reverse_full_fee=True,
     idempotency_key='reversal-manual-123'
   )
   ```

---

### Issue: Settlement Batch Failed

**Symptoms:**
- Daily settlement task failed
- Withdrawals not auto-created

**Resolution:**
1. Check Celery logs:
   ```bash
   tail -f /var/log/celery/worker.log
   ```

2. Retry settlement:
   ```bash
   python manage.py run_settlement_batch --force
   ```

3. If recurring issue:
   - Check available balance
   - Check KYC status
   - Check bank connection
   - Escalate to engineering

---

## Best Practices

### ✓ DO:
- ✓ Approve withdrawals within 24 hours
- ✓ Verify KYC before approval
- ✓ Use descriptive rejection reasons
- ✓ Check ledger integrity daily
- ✓ Keep detailed notes for disputed charges
- ✓ Test policy changes on store-specific rates first
- ✓ Use bulk operations for batch processing

### ✗ DON'T:
- ✗ Manually edit JournalEntry records
- ✗ Approve withdrawals without KYC
- ✗ Mark as Paid without bank confirmation
- ✗ Deactivate global fee policy
- ✗ Create duplicate withdrawals
- ✗ Share admin credentials
- ✗ Process withdrawals without audit trail

---

## Escalation

### When to Contact Engineering

- ✗ Unbalanced journal entries
- ✗ Wallet balance doesn't match ledger
- ✗ Withdrawal stuck in system
- ✗ API returning errors (500)
- ✗ Duplicate transactions not resolved
- ✗ Performance issues with large reports

**Contact:**
```
Slack: #wallet-team
Email: wallet-support@wasla.local
Jira: Project WALLET
```

**Include:**
- Store ID / Merchant name
- Transaction date and reference
- Steps to reproduce
- Screenshots of issue
- Any error messages

---

## Appendix: Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Insufficient balance" | Withdrawal > available | Approve for less or ask merchant to add funds |
| "Account not verified" | KYC pending | Reject and ask merchant to complete KYC |
| "Invalid bank account" | Account number wrong | Reject, ask merchant to update account info |
| "Duplicate entry" | Same payment processed twice | Contact engineering, may need reversal |
| "Ledger unbalanced" | Accounting error | Contact engineering immediately |

---

## System Limits

| Limit | Value |
|-------|-------|
| Max withdrawal amount | $100,000 |
| Min withdrawal amount | $10.00 |
| Max fee percentage | 50% |
| Min fee percentage | 0% |
| Settlement batch size | 1,000 withdrawals |
| Journal entry storage | Unlimited |
| API rate limit | 1000/hour |

---

## Contacts

**Support Level 1:** Payment support team (withdrawals, balance issues)
**Support Level 2:** Accounting team (ledger, reconciliation)
**Support Level 3:** Engineering team (bugs, system issues)

---

Last Updated: 2026-02-25
Version: 1.0
