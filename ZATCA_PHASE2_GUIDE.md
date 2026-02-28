# ZATCA Phase 2 E-Invoicing Integration

**ZATCA** (Zakat, Tax and Customs Authority) Phase 2 mandates electronic invoicing with digital signatures and QR codes for all businesses in Saudi Arabia.

## Overview

### Requirements

- ✅ XML invoice generation (UBL 2.1 format)
- ✅ Digital signatures (SHA256 + RSA)
- ✅ QR code generation (TLV encoding)
- ✅ Certificate management
- ✅ API submission to ZATCA
- ✅ Clearance/reporting workflow
- ✅ Audit trail

### Supported Features

- **File Formats**: UBL XML 2.1 (ZATCA-compliant)
- **Encryption**: RSA-2048 with SHA256
- **Digital Signature**: PKCS#1 v1.5
- **QR Codes**: TLV (Tag-Length-Value) encoded
- **API**: ZATCA e-invoicing REST API

## Architecture

### Data Models

#### ZatcaCertificate
Stores X.509 certificate and private key for digital signing.

```python
ZatcaCertificate(
    store=Store,                            # One per store
    certificate_content=str,                # PEM-encoded X.509 certificate
    private_key_content=str,                # PEM-encoded private key (encrypted)
    certificate_serial=str,                 # Unique certificate identifier
    common_name=str,                        # Certificate CN (company name)
    organization=str,                       # Organization name
    expires_at=datetime,                    # Certificate expiration
    issued_at=datetime,                     # Issue date
    status='active'|'expired'|'revoked',    # Current status
    approval_id=str,                        # ZATCA approval ID
    auth_token=str,                         # ZATCA authentication token
)
```

**Security Notes**:
- Private keys encrypted at rest (use Django encryption)
- Certificates validated before signing
- Expiration checked automatically

#### ZatcaInvoice
Tracks e-invoice state throughout its lifecycle.

```python
ZatcaInvoice(
    order=Order,                          # One invoice per order
    invoice_number=str,                   # Unique invoice ID (INV-YYYYMM-XXXXX)
    invoice_date=date,                    # Date of supply
    status='draft'|'issued'|'submitted'..., # Current status
    xml_content=str,                      # Generated UBL XML
    xml_hash=str,                         # SHA256 hash of XML
    digital_signature=str,                # Base64-encoded signature
    qr_code_content=str,                  # TLV-encoded QR data
    qr_code_image=ImageField,             # PNG image of QR code  
    submission_uuid=str,                  # UUID from ZATCA submission
    submission_timestamp=datetime,        # When submitted to ZATCA
    clearance_number=str,                 # ZATCA clearance ID
    clearance_timestamp=datetime,         # When cleared
    response_data=dict,                   # Full ZATCA API responses
    error_message=str,                    # If rejected
)
```

**Status Flow**:
```
DRAFT → ISSUED → SUBMITTED → (REPORTED → CLEARED) | REJECTED
```

#### ZatcaInvoiceLog
Audit trail for all invoice operations.

```python
ZatcaInvoiceLog(
    invoice=ZatcaInvoice,           # Reference to invoice
    action='generated'|'signed'|...  # Operation performed
    status_code=str,                # HTTP/API status
    message=str,                    # Operation details
    details=dict,                   # Full response data
)
```

**Actions Tracked**:
- GENERATED - XML invoice created
- SIGNED - Digital signature applied
- SUBMITTED - Sent to ZATCA API
- REPORTED - Reported for VAT
- CLEARED - Aproved by ZATCA
- REJECTED - Failed validation

### Service Layer

#### ZatcaInvoiceGenerator
Generates UBL 2.1 XML invoices.

```python
# Generate XML from order
xml_content = ZatcaInvoiceGenerator.generate_xml(order, invoice)

# Output:
# <?xml version="1.0"?>
# <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
#   <UBLVersionID>2.1</UBLVersionID>
#   <ID>INV-202401-ABC123</ID>
#   <IssueDate>2024-01-15</IssueDate>
#   ...
#   <InvoiceLine>...</InvoiceLine>
# </Invoice>
```

**XML Structure**:
- Invoice header (version, ID, dates)
- Seller/supplier info (name, VAT ID, address)
- Buyer/customer info (name, email)
- Line items (products, quantities, prices)
- Totals (subtotal, tax, total)
- Payment terms

#### ZatcaDigitalSignature
Signs XML with certificate private key.

```python
# Sign invoice
signature = ZatcaDigitalSignature.sign_invoice(
    xml_content,
    certificate
)
# Output: Base64-encoded signature

# Compute XML hash
xml_hash = ZatcaDigitalSignature.compute_xml_hash(xml_content)
# Output: SHA256 hex string
```

**Algorithm**: RSA-2048 + SHA256 (PKCS#1 v1.5)

#### ZatcaQRCodeGenerator
Generates ZATCA-compliant QR codes.

```python
# Generate QR data string
qr_data = ZatcaQRCodeGenerator.generate_qr(invoice, signature)

# Generate QR image
qr_image = ZatcaQRCodeGenerator.render_qr_image(qr_data)
# Output: PIL Image (PNG format)
```

**QR Contents (TLV-Encoded)**:
1. **Tag 01**: Seller name (VAT-registered name)
2. **Tag 02**: Seller VAT ID
3. **Tag 03**: Invoice date/time (ISO 8601)
4. **Tag 04**: Invoice total amount
5. **Tag 05**: Invoice total tax
6. **Tag 06**: Hash of invoice XML (SHA256)
7. **Tag 07**: Invoice digital signature

#### ZatcaInvoiceService
Main orchestration service.

```python
# Generate complete invoice
invoice = ZatcaInvoiceService.generate_invoice(order)
# Generates: XML, signature, QR code, stores in DB

# Submit to ZATCA API
result = ZatcaInvoiceService.submit_invoice(invoice)
# Response: {"status": "success", "uuid": "..."}

# Request clearance
result = ZatcaInvoiceService.clear_invoice(invoice)
# Response: {"status": "success", "clearance_id": "..."}
```

## Setup & Configuration

### 1. Obtain ZATCA Certificate

1. **Register** with ZATCA (https://zatca.gov.sa)
2. **Generate CSR** (Certificate Signing Request) using your company details
3. **Submit CSR** to ZATCA
4. **Receive** signed X.509 certificate + private key

### 2. Configure Certificate in Django Admin

Navigate to **ZATCA → ZATCA Certificates**

1. Click **Add Certificate**
2. Fill in:
   - **Store**: Your store
   - **Certificate Content**: PEM format certificate
   - **Private Key Content**: PEM format private key
   - **Certificate Serial**: From ZATCA (e.g., `12345678901234567890`)
   - **Common Name**: Company name from certificate
   - **Organization**: Organization name
   - **Issued At**: Certificate issue date
   - **Expires At**: Certificate expiration date
   - **Approval ID**: From ZATCA
   - **Auth Token**: ZATCA authentication token
   - **Webhook Secret**: For webhook verification
3. Click **Save**

### 3. Test Certificate Validity

The admin interface shows:
- ✓ Valid for Signing (green check if valid and active)
- Expiration date (auto-disabled when expired)

## Invoice Generation Flow

### Automatic Generation (Recommended)

Set up signals to auto-generate invoices when order is confirmed:

```python
from django.db.models.signals import post_save
from apps.orders.models import Order
from apps.zatca.services import ZatcaInvoiceService

def auto_generate_zatca_invoice(sender, instance, created, **kwargs):
    """Auto-generate ZATCA invoice when order confirmed."""
    if instance.status == 'processing':  # Order confirmed
        try:
            ZatcaInvoiceService.generate_invoice(instance)
        except Exception as e:
            # Log error but don't block order processing
            print(f"ZATCA invoice generation failed: {e}")

post_save.connect(auto_generate_zatca_invoice, sender=Order)
```

### Manual Generation (via Admin or API)

```python
from apps.zatca.services import ZatcaInvoiceService

# API endpoint (if implemented)
POST /api/zatca/invoices/

# Django code
order = Order.objects.get(id=1)
invoice = ZatcaInvoiceService.generate_invoice(order)
```

### Generation Process

1. **Validate**: Certificate is active and not expired
2. **Generate XML**: UBL 2.1 format with order details
3. **Compute Hash**: SHA256 of XML content
4. **Sign**: RSA-2048 signature using private key
5. **Generate QR**: TLV-encoded QR code with invoice details
6. **Render Image**: PNG image of QR code
7. **Save**: All to `ZatcaInvoice` record
8. **Log**: Action recorded in `ZatcaInvoiceLog`

**Status**: DRAFT → ISSUED

## Invoice Submission Flow

### Step 1: Submit to ZATCA API

```python
from apps.zatca.services import ZatcaInvoiceService

invoice = ZatcaInvoice.objects.get(id=1)
result = ZatcaInvoiceService.submit_invoice(invoice)

# Success: {"status": "success", "uuid": "xxxxx"}
# Failure: {"status": "error", "error": "..."}
```

**Process**:
1. Prepare payload (Base64-encoded XML + signature + QR)
2. POST to ZATCA API endpoint
3. Receive submission UUID
4. Update invoice status to SUBMITTED
5. Log action with response

**Status**: ISSUED → SUBMITTED

### Step 2: Get Clearance

```python
result = ZatcaInvoiceService.clear_invoice(invoice)

# Success: {"status": "success", "clearance_id": "xxxxx"}
# Failure: {"status": "error", "error": "..."}
```

**Process**:
1. Use submission UUID from previous step
2. POST clearance request with XML hash
3. Receive clearance number from ZATCA
4. Update invoice status to CLEARED
5. Log action

**Status**: SUBMITTED → CLEARED

## Admin Interface

### ZATCA Certificates

**Path**: `/admin/zatca/zatcacertificate/`

**Features**:
- View all certificates with status badges
- Expiration dates (color-coded)
- Validity check (green ✓ or red ✗)
- Certificate details (serial, CN, organization)
- Edit credentials and tokens
- Encrypt private keys at rest

**Status Colors**:
- 🟢 ACTIVE (green) - Ready for signing
- 🟡 EXPIRED (yellow) - No longer usable
- 🔴 REVOKED (red) - Disabled

### ZATCA Invoices

**Path**: `/admin/zatca/zatcainvoice/`

**Features**:
- View all invoices with status
- Search by invoice number or order ID
- Filter by status and date range
- View generated XML, signature, QR code
- Check ZATCA responses and error messages
- Activity logs for each invoice

**Status Badges**:
- ⚫ DRAFT (gray) - Not yet issued
- 🔵 ISSUED (blue) - Ready to submit
- 🟠 SUBMITTED (orange) - Awaiting ZATCA response
- 🔷 REPORTED (cyan) - Submitted, awaiting clearance
- 🟢 CLEARED (green) - Approved by ZATCA
- 🔴 REJECTED (red) - Failed validation

### Invoice Activity Logs

**Path**: `/admin/zatca/zatcainvoicelog/`

**Features**:
- Complete audit trail of all operations
- Search by invoice number
- Filter by action type and date
- View full API responses and error details
- Track status codes and timestamps

## Integration Examples

### For Order Confirmation Page

```html
{% if order.zatca_invoice %}
    <div class="invoice-info">
        <h3>📄 E-Invoice</h3>
        <p>
            Invoice #: <strong>{{ order.zatca_invoice.invoice_number }}</strong>
        </p>
        <p>
            Status: 
            {% if order.zatca_invoice.is_cleared %}
                <span class="badge badge-success">✓ Cleared by ZATCA</span>
            {% elif order.zatca_invoice.is_submitted %}
                <span class="badge badge-info">Submitted to ZATCA</span>
            {% else %}
                <span class="badge badge-secondary">{{ order.zatca_invoice.get_status_display }}</span>
            {% endif %}
        </p>
        
        {% if order.zatca_invoice.qr_code_image %}
            <div class="qr-code">
                <img src="{{ order.zatca_invoice.qr_code_image.url }}" 
                     alt="ZATCA QR Code" 
                     style="max-width: 200px;">
            </div>
        {% endif %}
    </div>
{% endif %}
```

### For Invoice Download

```python
from django.http import FileResponse
from apps.zatca.models import ZatcaInvoice

def download_invoice(request, invoice_id):
    """Download invoice XML."""
    invoice = ZatcaInvoice.objects.get(id=invoice_id)
    
    # Check permission (user owns this order)
    if invoice.order.customer != request.user:
        return HttpForbidden()
    
    # Return XML file
    response = FileResponse(invoice.xml_content.encode())
    response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}.xml"'
    return response
```

### For VAT Reporting

```python
from apps.zatca.models import ZatcaInvoice

# Monthly VAT summary
invoices = ZatcaInvoice.objects.filter(
    status='cleared',
    clearance_timestamp__month=1,
    clearance_timestamp__year=2024,
)

total_sales = sum(inv.order.total_amount for inv in invoices)
total_tax = sum(inv.order.tax_amount for inv in invoices)

print(f"January 2024 VAT Report:")
print(f"  Total Sales: {total_sales} SAR")
print(f"  Total Tax: {total_tax} SAR")
print(f"  Tax Rate: {(total_tax/total_sales)*100:.1f}%")
```

## Testing

### Unit Tests

```bash
python manage.py test apps.zatca
```

### Sandbox Testing

1. **Use Sandbox Certificate**:
   - ZATCA provides test certificate for sandbox
   - Certificates issued to `sandbox.zatca.gov.sa`

2. **Configure Sandbox**:
   ```python
   # Certificate marked as is_sandbox=True (optional)
   # API endpoints auto-select based on this
   ```

3. **Test Invoice Generation**:
   ```python
   from apps.zatca.services import ZatcaInvoiceService
   from apps.orders.models import Order
   
   order = Order.objects.first()
   invoice = ZatcaInvoiceService.generate_invoice(order)
   assert invoice.xml_content  # XML generated
   assert invoice.digital_signature  # Signed
   assert invoice.qr_code_image  # QR code exists
   ```

4. **Test ZATCA Submission** (if API available):
   ```python
   result = ZatcaInvoiceService.submit_invoice(invoice)
   assert result['status'] == 'success'
   ```

### Manual Testing Steps

1. Add test certificate in admin
2. Create test order
3. Navigate to `/admin/zatca/zatcainvoice/`
4. Manually create invoice (if not auto-generated)
5. View generated XML, signature, QR code
6. Check audit logs

## Security Considerations

### 1. Certificate Management

✅ **Secure Storage**:
- Private keys encrypted at rest (use Django encryption)
- Never log private key contents
- Rotate certificates before expiration
- Revoke compromised certificates immediately

✅ **Access Control**:
- Only admins can manage certificates
- Separate read-only view for staff
- Audit all certificate operations

### 2. Signature Validation

✅ **Automatic**:
- Signature computed using SHA256 + RSA-2048
- Uses PKCS#1 v1.5 standard
- Verified before submission

### 3. QR Code Security

✅ **Tamper-Evident**:
- QR code contains invoice hash
- ZATCA validates QR code when scanning
- Modification detected immediately

### 4. API Communication

✅ **TLS/SSL**:
- All API calls use HTTPS
- Certificate validation (no self-signed)
- Request/response logging (no sensitive data)

## Performance Optimization

### Asynchronous Processing

For production with high invoice volume:

```python
from celery import shared_task

@shared_task
def submit_invoice_task(invoice_id):
    """Async submission to ZATCA."""
    invoice = ZatcaInvoice.objects.get(id=invoice_id)
    return ZatcaInvoiceService.submit_invoice(invoice)

@shared_task
def clear_invoice_task(invoice_id):
    """Async clearance request."""
    invoice = ZatcaInvoice.objects.get(id=invoice_id)
    return ZatcaInvoiceService.clear_invoice(invoice)

# Usage in order processing
post_payment.connect(
    lambda sender, order, **kw: submit_invoice_task.delay(order.id),
    sender=Order
)
```

### Caching

```python
from django.views.decorators.cache import cache_page

@cache_page(60 * 60)  # Cache for 1 hour
def get_invoice_pdf(request, invoice_id):
    """Cached PDF generation."""
    invoice = ZatcaInvoice.objects.get(id=invoice_id)
    return render_invoice_pdf(invoice)
```

## Compliance

- ✅ **ZATCA Phase 2**: Full e-invoicing compliance
- ✅ **UBL 2.1**: Standard XML format
- ✅ **Digital Signatures**: RSA-2048 + SHA256
- ✅ **QR Codes**: TLV-encoded with integrity check
- ✅ **VAT Reporting**: Ready for monthly/quarterly reports
- ✅ **Audit Trail**: Complete operation history

## Troubleshooting

### Issue: "Certificate not valid"

**Cause**: Certificate expired or status not ACTIVE

**Solution**:
1. Check expiration date in admin
2. Ensure status is "Active"
3. Generate new certificate from ZATCA

### Issue: "Digital signature verification failed"

**Cause**: Private key mismatch or encoding issue

**Solution**:
1. Verify private key is correct PEM format
2. Test signature with openssl
3. Re-upload certificate pair

### Issue: "ZATCA submission failed"

**Cause**: API error, network issue, or invalid XML

**Solution**:
1. Check `ZatcaInvoiceLog` for detailed error
2. Verify API endpoint is reachable
3. Check auth token is valid
4. Test with sandbox first

### Issue: "QR code not scannable"

**Cause**: TLV encoding error or truncated signature

**Solution**:
1. Verify signature length (should be ~256 chars)
2. Check TLV format matches ZATCA spec
3. Test QR code with ZATCA's QR validator

## Future Enhancements

- [ ] Credit/debit note support
- [ ] Simplified/B2C invoices
- [ ] Cancel/refund handling
- [ ] Real-time ZATCA API status monitoring
- [ ] Invoice PDF generation with QR embed
- [ ] Monthly VAT report auto-generation
- [ ] Webhook for ZATCA status updates
- [ ] Multi-language invoice templates

## API Reference

### Service Functions

```python
ZatcaInvoiceService.generate_invoice(order: Order) -> ZatcaInvoice
ZatcaInvoiceService.submit_invoice(invoice: ZatcaInvoice) -> dict
ZatcaInvoiceService.clear_invoice(invoice: ZatcaInvoice) -> dict
```

### Model Methods

```python
ZatcaCertificate.is_valid() -> bool
ZatcaInvoice.is_submitted() -> bool
ZatcaInvoice.is_cleared() -> bool
```

### Admin Interface

- Certificates: `/admin/zatca/zatcacertificate/`
- Invoices: `/admin/zatca/zatcainvoice/`
- Logs: `/admin/zatca/zatcainvoicelog/`
