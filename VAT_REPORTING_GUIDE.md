# VAT Reporting Implementation

**VAT** (Value Added Tax) at 15% is mandatory in Saudi Arabia. Businesses must report monthly or quarterly and remit collected tax to ZATCA.

## Overview

### Requirements

- ✅ Monthly VAT calculation
- ✅ CSV/Excel export for accountants
- ✅ Submission to ZATCA
- ✅ Detailed transaction tracking
- ✅ Tax exemption support
- ✅ Audit trail and history

### Saudi Arabia VAT

- **Rate**: 15% (standard)
- **Reporting**: Monthly to ZATCA
- **Deadline**: 5th of following month
- **Exemptions**: Export sales, government, non-profits
- **Registration**: Businesses with SAR 375k+ annual revenue

## Architecture

### Data Models

#### VATReport
Monthly aggregated VAT report.

```python
VATReport(
    store=Store,                        # Which store
    report_number='VAT-2024-01',        # YYYY-MM format
    period_start=date(2024,1,1),        # Month start
    period_end=date(2024,1,31),         # Month end
    status='draft'|'finalized'|...,     # Current state
    total_sales=Decimal,                # All sales in period
    total_vat_collected=Decimal,        # VAT from sales
    total_vat_paid=Decimal,             # VAT on expenses
    vat_payable=Decimal,                # To remit (collected-paid)
    total_refunds=Decimal,              # Customer refunds
    refund_vat=Decimal,                 # VAT on refunds
)
```

**Status Flow**:
```
DRAFT → FINALIZED → SUBMITTED → ACCEPTED|REJECTED
```

#### VATTransactionLog
Detailed transaction records for audit.

```python
VATTransactionLog(
    report=VATReport,                   # Which report
    invoice_number='ORD-123',           # Linked invoice
    transaction_type='sale'|'refund'|..., # Type
    transaction_date=date,              # When
    amount_ex_vat=Decimal,              # Before tax
    vat_amount=Decimal,                 # Tax (15%)
    amount_inc_vat=Decimal,             # Total
    customer_type='b2c'|'b2b',          # Business or consumer
)
```

#### TaxExemption
Track exempt transactions.

```python
TaxExemption(
    store=Store,
    exemption_type='export'|'nonprofit'|..., # Type
    document_number='INV-456',          # Exempt transaction
    amount=Decimal,                     # Exempt amount
    reason=str,                         # Why exempt
)
```

### Service Layer

#### VATReportService
Generate monthly reports.

```python
# Generate report for January 2024
report = VATReportService.generate_monthly_report(store, 2024, 1)
# → Collects all transactions from period
# → Calculates VAT figures
# → Creates draft report

# Finalize (lock from editing)
VATReportService.finalize_report(report)

# Export formats
csv_data = VATReportService.export_to_csv(report)
excel_bytes = VATReportService.export_to_excel(report)

# Submit to ZATCA
result = VATReportService.submit_report(report)
# → Status changes to SUBMITTED
# → Backed by ZATCA submission ID

# Get summary
summary = VATReportService.get_monthly_summary(store, 2024, 1)
# → Quick overview: total_sales, vat_payable, status
```

## Setup & Configuration

### 1. Database Migration

```bash
python manage.py makemigrations reporting
python manage.py migrate reporting
```

### 2. Configure Store Tax ID

Update your **Store**  with:
- **tax_id**: VAT registration number (e.g., 300012345600003)
- **tax_registered**: True if VAT registered

```python
from apps.stores.models import Store

store = Store.objects.get(name="Your Store")
store.tax_id = "300012345600003"  # From ZATCA
store.tax_registered = True
store.save()
```

### 3. Set Up Scheduled Report Generation

Create management command to auto-generate monthly reports:

```python
# apps/reporting/management/commands/generate_vat_reports.py

from django.core.management.base import BaseCommand
from apps.reporting.services import VATReportService
from apps.stores.models import Store
from datetime import datetime, timedelta

class Command(BaseCommand):
    def handle(self, *args, **options):
        today = datetime.today()
        # Generate for last month
        if today.day == 1:
            target_month = today.month - 1
            target_year = today.year
        else:
            # If mid-month, generate for previous month
            target_month = today.month - 1 if today.day < 5 else today.month
            target_year = today.year

        for store in Store.objects.all():
            report = VATReportService.generate_monthly_report(
                store,
                target_year,
                target_month
            )
            self.stdout.write(f"Generated {report.report_number}")
```

Schedule with Celery Beat:

```python
# config/celery.py

from celery.schedules import crontab

app.conf.beat_schedule = {
    'generate-vat-reports': {
        'task': 'apps.reporting.tasks.generate_monthly_reports',
        'schedule': crontab(hour=0, minute=0, day_of_month=2),  # 2nd of each month
    },
}
```

## Monthly Workflow

### Step 1: Auto-Generate (1st of month)

System automatically creates draft report for previous month.

**Contains**:
- All sales transactions from period
- All refunds from period
- Tax exemptions
- Calculated VAT figures

### Step 2: Review (1st-4th of month)

Accountant reviews in Admin:

1. Navigate to **Reporting → VAT Reports**
2. Click draft report for previous month
3. Review summary:
   - Total sales
   - VAT collected
   - VAT paid (on expenses)
   - VAT payable
4. Review transactions (can drill down per invoice)
5. Check for any issues

### Step 3: Finalize (4th of month)

Admin finalizes report:

```python
from apps.reporting.models import VATReport
from apps.reporting.services import VATReportService

report = VATReport.objects.get(report_number="VAT-2024-01")
VATReportService.finalize_report(report)
# Status → FINALIZED (locked)
```

### Step 4: Export & Submit (by 5th)

Submit to ZATCA:

```python
# Export to file
csv = VATReportService.export_to_csv(report)
excel = VATReportService.export_to_excel(report)

# Submit to ZATCA API
result = VATReportService.submit_report(report)
# Status → SUBMITTED
```

## Admin Interface

### VAT Reports

**Path**: `/admin/reporting/vatreport/`

**List View**:
- Report number (VAT-YYYY-MM)
- Period (start-end date)
- VAT payable (highlighted)
- Status (color-coded)
- Submission date

**Detail View**:
- Financial summary (sales, vat, payable)
- Transaction list (all invoices included)
- Export buttons (CSV, Excel)
- Submission status and ID
- Notes/comments

**Actions**:
- Finalize draft
- Export to CSV/Excel
- Submit to ZATCA
- Download submission proof

### Transaction Logs

**Path**: `/admin/reporting/vattransactionlog/`

View all transactions in each report:
- Invoice/order number
- Transaction date
- Type (sale, refund, adjustment)
- Amounts (ex-VAT, VAT, inc-VAT)
- Customer type (B2C vs B2B)

### Tax Exemptions

**Path**: `/admin/reporting/taxexemption/`

Track exempt transactions:
- Exemption type (export, non-profit, government, other)
- Document number (invoice/order)
- Exempt amount
- Supporting documentation
- Date

## CSV/Excel Exports

### CSV Format

```csv
VAT Report,VAT-2024-01
Period,2024-01-01 to 2024-01-31
Store,Your Store

Summary
Total Sales (including VAT),125000.00
Total VAT Collected,16250.00
Total VAT Paid (Input),5000.00
VAT Payable,11250.00
Total Refunds,5000.00
Refund VAT,650.00

Detailed Transactions
Invoice,Date,Type,Amount (ex-VAT),VAT,Amount (inc-VAT),Customer,Payment
ORD-1001,2024-01-15,Sale,50000,7500,57500,B2C,Card
ORD-1002,2024-01-16,Sale,45000,6750,51750,B2B,Bank
REF-1001,2024-01-20,Refund,-5000,-750,-5750,B2C,Card
```

### Excel Format

Formatted workbook with:
- Summary sheet (VAT figures)
- Transactions sheet (detailed records)
- Professional formatting
- Charts (optional)

## Integration Examples

### Automated Report Email

```python
from django.core.mail import send_mail
from apps.reporting.models import VATReport
from apps.reporting.services import VATReportService

def send_vat_report_email(report):
    """Email finalized report to accountant."""
    csv_data = VATReportService.export_to_csv(report)
    excel_data = VATReportService.export_to_excel(report)
    
    email = send_mail(
        subject=f"VAT Report {report.report_number}",
        message="See attachments",
        from_email="noreply@store.com",
        recipient_list=["accountant@store.com"],
        attachments=[
            (f"{report.report_number}.csv", csv_data, 'text/csv'),
            (f"{report.report_number}.xlsx", excel_data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        ]
    )
```

### Dashboard Widget

```python
# Show current month VAT on dashboard

from django.db.models import Sum
from apps.reporting.models import VATReport
from apps.reporting.services import VATReportService

store = request.user.store
today = date.today()

summary = VATReportService.get_monthly_summary(
    store,
    today.year,
    today.month
)

context = {
    'vat_report': summary,
    'vat_due': summary['vat_payable'],
    'vat_status': summary['status'],
}
```

## Compliance

- ✅ **ZATCA Compliance**: 15% VAT rate
- ✅ **Monthly Reporting**: Required by law
- ✅ **Transaction Tracking**: 3-year retention
- ✅ **Exemption Documentation**: Supporting files
- ✅ **Audit Trail**: All changes logged
- ✅ **Financial Records**: Reconcilable with accounting

## FAQ

**Q: When are reports due?**
A: By the 5th of the following month in Saudi Arabia.

**Q: Can I amend a submitted report?**
A: No, submit amended next month or contact ZATCA directly.

**Q: How are refunds handled?**
A: Reduction in VAT liabilities in the refund month.

**Q: What about export sales?**
A: Zero-VAT (0%). Track in tax exemptions.

**Q: How long to keep records?**
A: Minimum 3 years (ZATCA requirement).

**Q: Can I use electronic invoicing?**
A: Yes, ZATCA phase 2 e-invoicing required.

## Tax Rates

| Category | Rate | Example |
|---|---|---|
| Standard | 15% | Most sales |
| Export | 0% | Goods shipped abroad |
| Government | Exempt | Govt contracts |
| Non-profit | Exempt | Registered NGO |

## Export Preparation Checklist

- [ ] All transactions recorded
- [ ] Refunds properly categorized
- [ ] Exemptions documented
- [ ] VAT paid receipts attached
- [ ] Report finalized
- [ ] CSV/Excel generated
- [ ] Submitted to ZATCA
- [ ] Proof of submission archived

## Future Enhancements

- [ ] Quarterly reports (for lower volume)
- [ ] 3-monthly remittance option
- [ ] Real-time ZATCA API integration
- [ ] Automatic exemption detection
- [ ] Intra-GCC B2B VAT rules
- [ ] E-invoice auto-submission
- [ ] Tax authority audit reports
