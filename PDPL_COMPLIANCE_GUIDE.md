# PDPL Compliance Implementation

**PDPL** (Personal Data Protection Law) is Saudi Arabia's data protection regulation requiring explicit consent, user control, and data transparency.

## Overview

### Key Principles

- ✅ **Consent-Based**: Users grant explicit consent for data processing
- ✅ **Right to Access**: Users can request and download their data
- ✅ **Right to Deletion**: Users can request account and data deletion
- ✅ **Right to Correction**: Users can update their personal data
- ✅ **Audit Trail**: All data access logged and auditable
- ✅ **Data Minimization**: Collect only necessary data
- ✅ **Transparency**: Clear privacy policy and data usage

### Implemented Features

1. **Data Export** (Article 6) - Download all personal data
2. **Account Deletion** (Article 5) - Right to be forgotten with grace period
3. **Consent Management** - Track and manage user consents
4. **Access Logging** - Audit trail of all data operations
5. **Data Retention** - Implement deletion policies

## Architecture

### Data Models

#### DataExportRequest
Tracks user data export requests.

```python
DataExportRequest(
    user=User,                           # Who requested
    request_id='DER-20240115-ABCD',     # Unique ID
    status='pending'|'processing'|...,   # Current state
    format_type='json'|'csv'|'xml',      # Export format
    requested_at=datetime,               # When requested
    processed_at=datetime,               # When generated
    expires_at=datetime,                 # Link expires after 30 days
    download_count=int,                  # How many times downloaded
    data_file=FileField,                 # Generated export file
    file_size=int,                       # Bytes
    included_data=[],                    # What was exported
)
```

**Status Flow**:
```
PENDING → PROCESSING → COMPLETED (or FAILED)
```

**Data Included**:
- Profile (email, name)
- Contact information
- Addresses
- Order history
- Payments
- Shopping cart
- Reviews
- Preferences
- Consent records
- Activity logs

#### AccountDeletionRequest
Tracks account deletion requests with grace period.

```python
AccountDeletionRequest(
    user=User,                            # Whose account
    request_id='ADR-20240115-ABCD',      # Unique ID
    status='pending'|'confirmed'|'...',   # Current state
    reason='no_longer_needed'|...,        # Why deleting
    is_confirmed=bool,                    # Email confirmation
    confirmation_code=str,                # Sent to email
    requested_at=datetime,                # When requested
    confirmed_at=datetime,                # When confirmed
    processed_at=datetime,                # When deleted
    grace_period_ends_at=datetime,        # 14 days for reconsideration
    data_backup=FileField,                # JSON backup before deletion
    is_irreversible=bool,                 # Fully deleted
)
```

**Status Flow**:
```
PENDING → CONFIRMED → PROCESSING → COMPLETED
           ↓
         (GRACE PERIOD - can still cancel)
```

**Grace Period**: 14 days to reconsider before irreversible deletion

#### DataAccessLog
Audit trail for all data access.

```python
DataAccessLog(
    user=User,                      # Whose data
    action='view'|'export'|...,     # What action
    accessed_by=str,                # Who (user/admin/system)
    ip_address=str,                 # Where (IP)
    user_agent=str,                 # Device info
    data_categories=[],             # What data accessed
    purpose=str,                    # Why accessed
    timestamp=datetime,             # When
)
```

**Actions**:
- VIEW - User viewing own data
- EXPORT - Data export request
- DOWNLOAD - Downloading export file
- DELETE - Account deletion
- RESTORE - Account undelete
- CONSENT_GRANT - Consent given
- CONSENT_REVOKE - Consent withdrawn
- LOGIN - User login
- PASSWORD_CHANGE - Password changed
- EMAIL_CHANGE - Email updated

#### ConsentRecord
Records user consent preferences.

```python
ConsentRecord(
    user=User,                          # Who consented
    consent_type='marketing'|...,       # Type of consent
    is_granted=bool,                    # Current status
    granted_at=datetime,                # When granted
    revoked_at=datetime,                # When revoked
    version='1.0',                      # Policy version
    method='checkbox'|'explicit'|...,   # How consent given
)
```

**Consent Types**:
- MARKETING - Email/SMS marketing
- ANALYTICS - Tracking & analytics
- THIRD_PARTY - Share with partners
- PROFILING - Personalization
- COOKIES - Cookie tracking

### Service Layer

#### DataExportService
Handles data export requests.

```python
# Request export
export_request = DataExportService.request_export(user, format_type='json')
# → Creates request, sends confirmation email

# Process export (can run async)
success = DataExportService.process_export(export_request)
# → Generates JSON/CSV/XML file, sends download link

# File is available for 30 days, then auto-deleted
```

**Export Formats**:
- **JSON**: Structured, easy to parse
- **CSV**: Spreadsheet-compatible
- **XML**: Standard data format

#### AccountDeletionService
Manages account deletion with safeguards.

```python
# Step 1: Request deletion (requires reason)
deletion_request = AccountDeletionService.request_deletion(
    user=user,
    reason='privacy_concerns',
    reason_details='Want to protect my data'
)
# → Sends confirmation email with code

# Step 2: User clicks email link to confirm
confirmed = AccountDeletionService.confirm_deletion(
    user=user,
    confirmation_code=code_from_email
)
# → 14-day grace period starts

# Step 3: After grace period, process deletion
success = AccountDeletionService.process_deletion(deletion_request)
# → Backs up data, deactivates user, logs deletion

# Option: Cancel during grace period
cancelled = AccountDeletionService.cancel_deletion(deletion_request)
# → Restores account
```

**Safety Measures**:
1. Email confirmation (prevent accidental deletion)
2. 14-day grace period before irreversible deletion
3. Data backup before deletion
4. Deactivate user (soft delete) initially
5. Audit trail of all steps

#### ConsentService
Manage consent preferences.

```python
# Grant consent
consent = ConsentService.grant_consent(user, 'marketing')
# → Records when cconquent was given, logs action

# Revoke consent
consent = ConsentService.revoke_consent(user, 'marketing')
# → Records revocation, logs action

# Check consent
has_consent = ConsentService.has_consent(user, 'marketing')
# → Returns True/False for active consent (after grant, before revoke)
```

## Setup & Configuration

### 1. Database Migrations

```bash
python manage.py makemigrations privacy
python manage.py migrate privacy
```

### 2. Email Templates (Optional)

Create these email templates for notifications:

**`templates/privacy/emails/export_request.html`**
```html
<h2>Data Export Request Received</h2>
<p>Your data export will be processed within 24 hours.</p>
<p>Request ID: {{ request_id }}</p>
```

**`templates/privacy/emails/export_complete.html`**
```html
<h2>Your Data Export is Ready</h2>
<p>Download your data: <a href="{{ download_url }}">Download Now</a></p>
<p>Expires: {{ expires_at }}</p>
```

**`templates/privacy/emails/deletion_confirmation.html`**
```html
<h2>Confirm Account Deletion</h2>
<p>Click link below to confirm deletion. You'll have 14 days to change your mind.</p>
<p><a href="{{ confirm_url }}">Confirm Deletion</a></p>
<p><a href="{{ cancel_url }}">Cancel Request</a></p>
```

### 3. Configure Privacy Policy Page

Add to your website:

```html
<!-- privacy-policy.html -->
<section id="data-protection">
    <h2>Your Data Rights</h2>
    
    <h3>Right to Access (Article 6)</h3>
    <p><a href="/api/privacy/exports/request/">Request Your Data</a></p>
    
    <h3>Right to Deletion (Article 5)</h3>
    <p><a href="/api/privacy/deletion/request/">Delete Your Account</a></p>
    
    <h3>Manage Consent</h3>
    <form method="POST" action="/api/privacy/consent/">
        <label><input type="checkbox" name="marketing"> Marketing</label>
        <label><input type="checkbox" name="analytics"> Analytics</label>
        <button>Save Preferences</button>
    </form>
</section>
```

## User-Facing Workflows

### Data Export Workflow

1. **User Initiates Export**
   - Navigate to `/privacy/export`
   - Click "Request My Data"
   - Choose format (JSON/CSV/XML)
   - Submit request

2. **Confirmation Email**
   - "Data export request received"
   - Processing happens within 24 hours

3. **Download Email**
   - "Your data export is ready"
   - Click link to download
   - File valid for 30 days

4. **User Downloads**
   - ZIP file with all personal data
   - Can open in any spreadsheet or JSON viewer

### Account Deletion Workflow

1. **User Requests Deletion**
   - Account Settings → "Delete Account"
   - Select reason from dropdown
   - (Optional) Add additional details
   - Click "Request Deletion"

2. **Confirmation Email**
   - "Confirm your account deletion"
   - Click link in email to confirm
   - Important: 14-day grace period begins

3. **Grace Period (14 days)**
   - Account shows "Deletion Pending"
   - Can still log in
   - Can cancel deletion via email link

4. **After Grace Period**
   - Account automatically deactivated
   - Data remains in backups (legal hold)
   - Cannot reactivate

5. **After 90 days (retention policy)**
   - Data permanently deleted from backups
   - Fully unrecoverable

## Admin Interface

Create admin classes for privacy models:

```python
from django.contrib import admin
from apps.privacy.models import (
    DataExportRequest,
    AccountDeletionRequest,
    DataAccessLog,
    ConsentRecord,
)

@admin.register(DataExportRequest)
class DataExportRequestAdmin(admin.ModelAdmin):
    list_display = ['request_id', 'user', 'status', 'requested_at']
    list_filter = ['status', 'format_type']
    search_fields = ['user__email', 'request_id']

@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ['request_id', 'user', 'status', 'requested_at']
    list_filter = ['status', 'reason']
    search_fields = ['user__email', 'request_id']

@admin.register(DataAccessLog)
class DataAccessLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'accessed_by', 'timestamp']
    list_filter = ['action', 'accessed_by']
    search_fields = ['user__email']
    readonly_fields = ['user', 'action', 'timestamp']
```

## Integration Examples

### Auto-Logging Data Access

```python
from apps.privacy.models import DataAccessLog

def log_data_access(user, action, accessed_by='system', data=None):
    """Log data access for audit trail."""
    DataAccessLog.objects.create(
        user=user,
        action=action,
        accessed_by=accessed_by,
        ip_address=get_client_ip(request),
        data_categories=data or [],
    )

# Usage in views
log_data_access(
    request.user,
    'view',
    accessed_by='user',
    data=['profile', 'contact']
)
```

### Consent Checking

```python
from apps.privacy.services import ConsentService

def send_marketing_email(user):
    """Only send if user has marketing consent."""
    if ConsentService.has_consent(user, 'marketing'):
        # Send email
        pass
    else:
        # Skip email
        pass
```

### Data Deletion on Account Deletion

```python
from django.db.models.signals import post_delete
from apps.privacy.models import AccountDeletionRequest
from apps.privacy.services import AccountDeletionService

def on_deletion_complete(sender, instance, **kwargs):
    """Cleanup user data when account deleted."""
    if instance.status == 'completed':
        # Delete related data
        instance.user.orders.all().delete()  # or anonymize
        instance.user.payments.all().delete()
        instance.user.reviews.all().delete()

post_delete.connect(on_deletion_complete, sender=AccountDeletionRequest)
```

## Privacy Policy Elements

Include these in your privacy policy:

### Data Collection
- What data you collect
- How it's collected
- Why it's collected

### Data Retention
- How long you keep data
- Deletion processes
- Backup retention (90 days)

### User Rights
- Right to access (Article 6)
- Right to deletion (Article 5)
- Right to correction
- Right to withdraw consent

### Third-Party Sharing
- Who you share data with
- What data is shared
- User control over sharing

### Security
- How data is protected
- Encryption methods
- Access controls

### Contact
- Data Protection Officer contact
- How to submit requests
- How to file complaints

## Testing

### Manual Testing Checklist

- [ ] Request data export
- [ ] Confirm email receiptuction
- [ ] Download export file
- [ ] Verify all data included
- [ ] Verify JSON/CSV/XML format
- [ ] Request account deletion
- [ ] Confirm via email
- [ ] Check grace period
- [ ] Cancel deletion (should restore)
- [ ] Wait grace period, verify deletion
- [ ] Check audit logs
- [ ] Grant/revoke consents
- [ ] Verify logs updated

### Unit Tests

```python
from django.test import TestCase
from apps.privacy.services import DataExportService, AccountDeletionService

class PrivacyTest(TestCase):
    def test_data_export_request(self):
        export_req = DataExportService.request_export(self.user, 'json')
        self.assertEqual(export_req.status, 'pending')
    
    def test_account_deletion_flow(self):
        del_req = AccountDeletionService.request_deletion(self.user)
        self.assertEqual(del_req.status, 'pending')
        
        # Confirm
        confirmed = AccountDeletionService.confirm_deletion(
            self.user,
            del_req.confirmation_code
        )
        self.assertTrue(confirmed)
        self.assertTrue(del_req.is_in_grace_period())
```

## Compliance Checklist

- ✅ Data Export (Article 6)
  - [ ] Users can request data export
  - [ ] Export includes all personal data
  - [ ] Available in standard format (JSON)
  - [ ] Download link expires after 30 days

- ✅ Account Deletion (Article 5)
  - [ ] Users can request account deletion
  - [ ] Email confirmation required
  - [ ] 14-day grace period
  - [ ] Data backed up before deletion
  - [ ] Audit trail maintained

- ✅ Consent (PDPL General)
  - [ ] Track all consents
  - [ ] Users can grant/revoke
  - [ ] Consent recorded with timestamp
  - [ ] Policy version tracked

- ✅ Access Logging
  - [ ] All data access logged
  - [ ] Timestamp and user captured
  - [ ] IP address logged
  - [ ] Purpose documented
  - [ ] Accessible for audits

- ✅ Data Minimization
  - [ ] Only collect necessary data
  - [ ] Delete old/unused data
  - [ ] Anonymize when possible
  - [ ] Regular retention reviews

## FAQ

**Q: Can users recover deleted accounts?**
A: Only during the 14-day grace period. After that, deletion is irreversible.

**Q: How long are data exports available?**
A: 30 days. After that, the download link expires and a new export must be requested.

**Q: What happens to order data after account deletion?**
A: Orders are anonymized (customer reference removed) but kept for business records. Users receive backup before deletion.

**Q: Do you comply with GDPR?**
A: This implementation follows PDPL Saudi Arabia requirements, which are similar to GDPR. Additional GDPR compliance may be needed for EU customers.

**Q: What about payment card data?**
A: Card data is NOT stored (processed via Stripe/etc.). Only transaction records are kept.

## Future Enhancements

- [ ] Data Portability (PDPL Article 7)
- [ ] Automated deletion scheduler
- [ ] Data breach notification system
- [ ] Privacy impact assessments
- [ ] Consent withdrawal analytics
- [ ] GDPR/CCPA compliance templates
- [ ] Data minimization automation
- [ ] Compliance reporting dashboards
