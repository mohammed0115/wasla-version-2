"""ZATCA e-invoicing services."""

import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
import hashlib
import requests
from typing import Dict, Optional
import base64

from django.conf import settings
from django.utils import timezone
from lxml import etree
import qrcode
from io import BytesIO
from PIL import Image

from apps.zatca.models import ZatcaInvoice, ZatcaInvoiceLog, ZatcaCertificate
from apps.orders.models import Order


class ZatcaInvoiceGenerator:
    """Generate ZATCA-compliant UBL XML invoices."""

    namespace = {
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "ublext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    @staticmethod
    def generate_xml(order: Order, invoice: ZatcaInvoice) -> str:
        """
        Generate ZATCA-compliant UBL XML invoice.

        Returns:
            XML string
        """
        # Create root element
        root = ET.Element("Invoice")
        root.set("xmlns", "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2")

        for prefix, uri in ZatcaInvoiceGenerator.namespace.items():
            root.set(f"xmlns:{prefix}", uri)

        # Add invoice header
        ZatcaInvoiceGenerator._add_header(root, order, invoice)

        # Add supplier/seller info
        ZatcaInvoiceGenerator._add_seller(root, order)

        # Add customer/buyer info
        ZatcaInvoiceGenerator._add_buyer(root, order)

        # Add payment terms
        ZatcaInvoiceGenerator._add_payment_terms(root, order)

        # Add tax totals
        ZatcaInvoiceGenerator._add_tax_totals(root, order)

        # Add items
        ZatcaInvoiceGenerator._add_items(root, order)

        # Add note
        ZatcaInvoiceGenerator._add_note(root, order)

        # Convert to string
        return ET.tostring(root, encoding="unicode")

    @staticmethod
    def _add_header(root, order: Order, invoice: ZatcaInvoice):
        """Add invoice header elements."""
        el = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}UBLVersionID")
        el.text = "2.1"

        el = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CustomizationID")
        el.text = "urn:cefact:ubl:ph:sinv:2.1"

        el = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID"
        )
        el.text = invoice.invoice_number

        el = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueDate"
        )
        el.text = invoice.invoice_date.isoformat()

        el = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueTime"
        )
        el.text = datetime.now().time().isoformat()

        el = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoiceTypeCode"
        )
        el.text = "388"  # Standard invoice

    @staticmethod
    def _add_seller(root, order: Order):
        """Add seller/supplier info."""
        seller = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingSupplierParty"
        )

        # Seller ID
        party = ET.SubElement(
            seller, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party"
        )
        id_el = ET.SubElement(
            party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID"
        )
        id_el.text = order.store.tax_id or "1234567890"
        id_el.set("schemeID", "TN")

        # Seller name
        name_el = ET.SubElement(
            party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name"
        )
        name_el.text = order.store.name

        # Address
        address = ET.SubElement(
            party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PostalAddress"
        )
        street = ET.SubElement(
            address, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}StreetName"
        )
        street.text = order.store.address or "Riyadh"
        country = ET.SubElement(
            address, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Country"
        )
        country_code = ET.SubElement(
            country, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IdentificationCode"
        )
        country_code.text = "SA"

    @staticmethod
    def _add_buyer(root, order: Order):
        """Add buyer/customer info."""
        buyer = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingCustomerParty"
        )

        party = ET.SubElement(
            buyer, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party"
        )

        # Customer name
        name_el = ET.SubElement(
            party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name"
        )
        if order.shipping_address:
            name_el.text = order.shipping_address.full_name
        else:
            name_el.text = order.email

        # Email
        email = ET.SubElement(
            party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ElectronicMail"
        )
        email.text = order.email

    @staticmethod
    def _add_payment_terms(root, order: Order):
        """Add payment information."""
        payment = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PaymentMeans"
        )

        code = ET.SubElement(
            payment, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PaymentMeansCode"
        )
        code.text = "42"  # Credit transfer

    @staticmethod
    def _add_tax_totals(root, order: Order):
        """Add tax summary."""
        tax_total = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxTotal"
        )

        # Tax amount
        tax_amount = ET.SubElement(
            tax_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount"
        )
        tax_amount.text = str(order.tax_amount)
        tax_amount.set("currencyID", order.currency or "SAR")

        # Tax subtotal
        tax_subtotal = ET.SubElement(
            tax_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxSubtotal"
        )

        taxable_amount = ET.SubElement(
            tax_subtotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxableAmount"
        )
        taxable_amount.text = str(order.subtotal or order.total_amount - order.tax_amount)
        taxable_amount.set("currencyID", order.currency or "SAR")

    @staticmethod
    def _add_items(root, order: Order):
        """Add line items."""
        for item in order.items.all():
            line = ET.SubElement(
                root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}InvoiceLine"
            )

            # Line ID
            line_id = ET.SubElement(
                line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID"
            )
            line_id.text = str(item.id)

            # Quantity
            qty = ET.SubElement(
                line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoicedQuantity"
            )
            qty.text = str(item.quantity)

            # Line amount
            line_amount = ET.SubElement(
                line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount"
            )
            line_amount.text = str(item.total_price)
            line_amount.set("currencyID", order.currency or "SAR")

            # Item name
            item_elem = ET.SubElement(
                line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Item"
            )
            name = ET.SubElement(
                item_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name"
            )
            name.text = item.product.name

            # Price
            price = ET.SubElement(
                line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Price"
            )
            price_amount = ET.SubElement(
                price, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PriceAmount"
            )
            price_amount.text = str(item.unit_price_snapshot)
            price_amount.set("currencyID", order.currency or "SAR")

    @staticmethod
    def _add_note(root, order: Order):
        """Add invoice note."""
        note = ET.SubElement(
            root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Note"
        )
        note.text = f"Order #{order.id} - Thank you for your purchase"


class ZatcaDigitalSignature:
    """Generate digital signatures for ZATCA invoices."""

    @staticmethod
    def sign_invoice(xml_content: str, certificate: ZatcaCertificate) -> str:
        """
        Sign XML invoice with ZATCA certificate.

        Args:
            xml_content: XML invoice string
            certificate: ZatcaCertificate instance

        Returns:
            Digital signature (base64)
        """
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            import base64

            # Load certificate and private key
            cert_obj = x509.load_pem_x509_certificate(
                certificate.certificate_content.encode(),
                default_backend(),
            )

            from cryptography.hazmat.primitives import serialization

            private_key = serialization.load_pem_private_key(
                certificate.private_key_content.encode(),
                password=None,
                backend=default_backend(),
            )

            # Sign XML
            signature = private_key.sign(
                xml_content.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )

            return base64.b64encode(signature).decode()

        except Exception as e:
            raise Exception(f"Failed to sign invoice: {str(e)}")

    @staticmethod
    def compute_xml_hash(xml_content: str) -> str:
        """Compute SHA256 hash of XML content."""
        return hashlib.sha256(xml_content.encode()).hexdigest()


class ZatcaQRCodeGenerator:
    """Generate ZATCA-compliant QR codes."""

    @staticmethod
    def generate_qr(invoice: ZatcaInvoice, signature: str) -> str:
        """
        Generate QR code data string for TLV encoding.

        ZATCA QR includes:
        1. Seller name (1)
        2. Seller VAT ID (2)
        3. Timestamp (3)
        4. Invoice total (4)
        5. Invoice tax (5)
        6. Hash of XML (6)
        7. Digital signature (7)

        Returns:
            TLV-encoded string for QR code
        """
        order = invoice.order

        data = {
            "01": order.store.name or "Store",  # Seller name
            "02": order.store.tax_id or "1234567890",  # Seller VAT
            "03": datetime.now().isoformat(),  # Timestamp
            "04": str(order.total_amount),  # Total
            "05": str(order.tax_amount or Decimal(0)),  # Tax
            "06": invoice.xml_hash or "0" * 64,  # XML hash
            "07": signature[:64],  # Signature (truncated for size)
        }

        # Build TLV string
        tlv = ""
        for tag, value in data.items():
            tlv += f"{tag.encode('utf-8').hex()}{len(value.encode()).to_bytes(1, 'big').hex()}{value.encode('utf-8').hex()}"

        return tlv

    @staticmethod
    def render_qr_image(qr_data: str) -> Image.Image:
        """
        Render QR code as PIL Image.

        Args:
            qr_data: QR data string

        Returns:
            PIL Image object
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        return qr.make_image(fill_color="black", back_color="white")


class ZatcaInvoiceService:
    """Main service for ZATCA invoice lifecycle."""

    @staticmethod
    def generate_invoice(order: Order) -> ZatcaInvoice:
        """
        Generate ZATCA invoice for order.

        Creates:
        1. ZatcaInvoice record
        2. XML content
        3. Digital signature
        4. QR code
        5. Audit log

        Returns:
            ZatcaInvoice instance
        """
        # Get or create invoice
        invoice, created = ZatcaInvoice.objects.get_or_create(
            order=order,
            defaults={"status": ZatcaInvoice.STATUS_DRAFT},
        )

        if not created and invoice.status != ZatcaInvoice.STATUS_DRAFT:
            raise Exception(f"Invoice already generated: {invoice.invoice_number}")

        # Get certificate
        try:
            certificate = ZatcaCertificate.objects.get(
                store=order.store,
                status=ZatcaCertificate.CERTIFICATE_STATUS_ACTIVE,
            )
        except ZatcaCertificate.DoesNotExist:
            raise Exception("ZATCA certificate not configured for this store")

        if not certificate.is_valid():
            raise Exception("ZATCA certificate is invalid or expired")

        # Generate invoice number
        invoice.generate_invoice_number()
        invoice.save()

        # Generate XML
        xml_content = ZatcaInvoiceGenerator.generate_xml(order, invoice)
        invoice.xml_content = xml_content

        # Compute XML hash
        xml_hash = ZatcaDigitalSignature.compute_xml_hash(xml_content)
        invoice.xml_hash = xml_hash

        # Sign XML
        signature = ZatcaDigitalSignature.sign_invoice(xml_content, certificate)
        invoice.digital_signature = signature

        # Generate QR code
        qr_data = ZatcaQRCodeGenerator.generate_qr(invoice, signature)
        invoice.qr_code_content = qr_data

        # Generate QR image
        qr_image = ZatcaQRCodeGenerator.render_qr_image(qr_data)
        from django.core.files.base import ContentFile

        qr_bytes = BytesIO()
        qr_image.save(qr_bytes, format="PNG")
        qr_bytes.seek(0)

        from django.utils.text import slugify

        invoice.qr_code_image.save(
            f"{slugify(invoice.invoice_number)}.png",
            ContentFile(qr_bytes.getvalue()),
            save=False,
        )

        # Update status
        invoice.status = ZatcaInvoice.STATUS_ISSUED
        invoice.save()

        # Log action
        ZatcaInvoiceLog.objects.create(
            invoice=invoice,
            action=ZatcaInvoiceLog.ACTION_GENERATED,
            message=f"Invoice {invoice.invoice_number} generated and signed",
            details={
                "xml_hash": xml_hash,
                "certificate_serial": certificate.certificate_serial,
            },
        )

        return invoice

    @staticmethod
    def submit_invoice(invoice: ZatcaInvoice) -> Dict:
        """
        Submit invoice to ZATCA API.

        Integration with ZATCA e-invoicing portal:
        - POST XML + signature to ZATCA API
        - Get submission UUID
        - Get clearance status

        Returns:
            {"status": "success|error", "uuid": "...", ...}
        """
        if not invoice.xml_content or not invoice.digital_signature:
            return {"status": "error", "error": "Invoice not properly signed"}

        try:
            certificate = ZatcaCertificate.objects.get(store=invoice.order.store)

            # ZATCA API endpoint (sandbox vs production)
            api_url = ZatcaInvoiceService._get_zatca_api_url(certificate.is_valid())

            # Prepare payload
            payload = {
                "invoice": base64.b64encode(invoice.xml_content.encode()).decode(),
                "signature": invoice.digital_signature,
                "qr_code": invoice.qr_code_content,
            }

            # Submit to ZATCA
            headers = {
                "Authorization": f"Bearer {certificate.auth_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            data = response.json()

            if response.status_code == 200:
                invoice.status = ZatcaInvoice.STATUS_SUBMITTED
                invoice.submission_uuid = data.get("uuid")
                invoice.submission_timestamp = timezone.now()
                invoice.response_data = data
                invoice.save()

                ZatcaInvoiceLog.objects.create(
                    invoice=invoice,
                    action=ZatcaInvoiceLog.ACTION_SUBMITTED,
                    status_code=str(response.status_code),
                    message="Invoice submitted to ZATCA",
                    details=data,
                )

                return {
                    "status": "success",
                    "uuid": data.get("uuid"),
                }
            else:
                invoice.status = ZatcaInvoice.STATUS_REJECTED
                invoice.error_message = data.get("error", "Unknown error")
                invoice.response_data = data
                invoice.save()

                ZatcaInvoiceLog.objects.create(
                    invoice=invoice,
                    action=ZatcaInvoiceLog.ACTION_REJECTED,
                    status_code=str(response.status_code),
                    message=data.get("error", "Submission failed"),
                    details=data,
                )

                return {
                    "status": "error",
                    "error": data.get("error", "Submission failed"),
                }

        except Exception as e:
            ZatcaInvoiceLog.objects.create(
                invoice=invoice,
                action=ZatcaInvoiceLog.ACTION_REJECTED,
                message=f"Submission exception: {str(e)}",
            )

            return {
                "status": "error",
                "error": str(e),
            }

    @staticmethod
    def clear_invoice(invoice: ZatcaInvoice) -> Dict:
        """
        Request clearance for submitted invoice.

        Reporting to ZATCA for VAT compliance.

        Returns:
            {"status": "success|error", ...}
        """
        if invoice.status not in [
            ZatcaInvoice.STATUS_SUBMITTED,
            ZatcaInvoice.STATUS_REPORTED,
        ]:
            return {
                "status": "error",
                "error": "Invoice must be submitted before clearing",
            }

        try:
            certificate = ZatcaCertificate.objects.get(store=invoice.order.store)

            # Clearance API endpoint
            api_url = f"{ZatcaInvoiceService._get_zatca_api_base()}/clearance"

            payload = {
                "uuid": invoice.submission_uuid,
                "xml_hash": invoice.xml_hash,
            }

            headers = {
                "Authorization": f"Bearer {certificate.auth_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            data = response.json()

            if response.status_code == 200:
                invoice.status = ZatcaInvoice.STATUS_CLEARED
                invoice.clearance_number = data.get("clearance_id")
                invoice.clearance_timestamp = timezone.now()
                invoice.response_data = data
                invoice.save()

                ZatcaInvoiceLog.objects.create(
                    invoice=invoice,
                    action=ZatcaInvoiceLog.ACTION_CLEARED,
                    status_code=str(response.status_code),
                    message="Invoice cleared by ZATCA",
                    details=data,
                )

                return {
                    "status": "success",
                    "clearance_id": data.get("clearance_id"),
                }
            else:
                return {
                    "status": "error",
                    "error": data.get("error", "Clearance failed"),
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    @staticmethod
    def _get_zatca_api_url(production: bool = False) -> str:
        """Get ZATCA API endpoint."""
        base = ZatcaInvoiceService._get_zatca_api_base(production)
        return f"{base}/invoices"

    @staticmethod
    def _get_zatca_api_base(production: bool = False) -> str:
        """Get ZATCA API base URL."""
        if production:
            return "https://api.zatca.gov.sa/v1"
        else:
            return "https://sandbox.zatca.gov.sa/v1"
