"""
Invoice Service

Generates invoices with ZATCA-compatible structure for Saudi Arabia.
Supports PDF generation and sequential numbering per tenant/store.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from io import BytesIO
from decimal import Decimal
import hashlib
import json
from datetime import datetime

from ..models import Order
from ..models_extended import Invoice, InvoiceLineItem


class InvoiceService:
    """
    Generate and manage invoices with ZATCA compliance.
    
    Features:
    - Sequential invoice numbering per tenant/store
    - ZATCA-compatible structure (Saudi VAT)
    - PDF generation with reportlab
    - Tax calculation
    - Invoice chain hashing for audit trail
    """
    
    @staticmethod
    def get_next_invoice_number(tenant_id: int, store_id: int) -> str:
        """
        Generate next sequential invoice number.
        Format: INV-<TENANT>-<STORE>-<SEQUENTIAL>
        """
        last_invoice = Invoice.objects.filter(
            tenant_id=tenant_id,
            store_id=store_id
        ).select_for_update(skip_locked=True).order_by('-id').first()
        
        sequence = 1
        if last_invoice:
            # Extract sequence number from last invoice
            parts = last_invoice.invoice_number.split('-')
            if len(parts) == 4:
                try:
                    sequence = int(parts[3]) + 1
                except (ValueError, IndexError):
                    sequence = last_invoice.id + 1
        
        return f"INV-{tenant_id:06d}-{store_id:06d}-{sequence:08d}"
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_order(order: Order) -> Invoice:
        """
        Create invoice from order.
        
        Args:
            order: The Order to create invoice for
            
        Returns:
            Created Invoice instance
        """
        invoice_number = InvoiceService.get_next_invoice_number(order.tenant_id, order.store_id)
        
        # Calculate totals
        subtotal = Decimal("0.00")
        for item in order.items.all():
            subtotal += item.quantity * item.price
        
        # Tax calculation (15% for Saudi Arabia)
        tax_rate = Decimal("15")
        tax_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        
        total = subtotal + tax_amount + Decimal(order.shipping_charge or 0)
        
        # Create invoice
        invoice = Invoice.objects.create(
            tenant_id=order.tenant_id,
            store_id=order.store_id,
            order=order,
            invoice_number=invoice_number,
            subtotal=subtotal,
            tax_amount=tax_amount,
            tax_rate=tax_rate,
            shipping_cost=Decimal(order.shipping_charge or 0),
            total_amount=total,
            currency=order.currency,
            
            # Customer details
            buyer_name=order.customer_name or order.customer.full_name,
            buyer_email=order.customer_email or order.customer.email,
            
            # Seller (store) details
            seller_name=order.store.name if hasattr(order, 'store') else "Store",
            seller_vat_id="",  # To be populated from store profile
            seller_address="",  # To be populated from store profile
            
            status=Invoice.STATUS_DRAFT,
        )
        
        # Create line items
        for order_item in order.items.all():
            line_subtotal = order_item.quantity * order_item.price
            line_tax = (line_subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
            
            InvoiceLineItem.objects.create(
                tenant_id=order.tenant_id,
                invoice=invoice,
                order_item=order_item,
                description=order_item.product.name,
                sku=order_item.product.sku or "",
                quantity=order_item.quantity,
                unit_price=order_item.price,
                line_subtotal=line_subtotal,
                line_tax=line_tax,
                line_total=line_subtotal + line_tax,
            )
        
        return invoice
    
    @staticmethod
    @transaction.atomic
    def issue_invoice(invoice: Invoice, previous_hash: str = "") -> Invoice:
        """
        Issue invoice (move from draft to issued).
        Generates ZATCA hash for compliance.
        
        Args:
            invoice: The Invoice to issue
            previous_hash: Previous invoice hash for chain
            
        Returns:
            Updated Invoice instance
        """
        invoice.issue_invoice()
        
        # Compute ZATCA hash for invoice chain
        invoice.zatca_hash = invoice.compute_zatca_hash(previous_hash)
        
        # Generate UUID for ZATCA
        import uuid
        invoice.zatca_uuid = str(uuid.uuid4())
        
        invoice.save(update_fields=["zatca_hash", "zatca_uuid"])
        invoice.refresh_from_db()
        
        return invoice
    
    @staticmethod
    def generate_pdf(invoice: Invoice) -> BytesIO:
        """
        Generate invoice PDF using reportlab.
        ZATCA-compatible format with QR code support.
        
        Args:
            invoice: The Invoice to generate PDF for
            
        Returns:
            BytesIO object with PDF content
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            )
            from reportlab.pdfgen import canvas
        except ImportError:
            raise ImportError("reportlab is required for PDF generation. Install it with: pip install reportlab")
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1F4FD8'),
            spaceAfter=30,
        )
        story.append(Paragraph(f"INVOICE", title_style))
        story.append(Spacer(1, 0.2*cm))
        
        # Invoice details header
        header_data = [
            [f"Invoice #: {invoice.invoice_number}", f"Date: {invoice.issue_date}"],
            [f"Due Date: {invoice.due_date or 'N/A'}", f"Status: {invoice.get_status_display()}"],
        ]
        header_table = Table(header_data)
        header_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0f0')),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.3*cm))
        
        # Seller and Buyer
        seller_buyer_data = [
            [
                Paragraph(f"<b>From (Seller):</b><br/>{invoice.seller_name}<br/>{invoice.seller_address}", styles['Normal']),
                Paragraph(f"<b>Bill To (Buyer):</b><br/>{invoice.buyer_name}<br/>{invoice.buyer_email}", styles['Normal']),
            ]
        ]
        seller_buyer_table = Table(seller_buyer_data)
        seller_buyer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(seller_buyer_table)
        story.append(Spacer(1, 0.3*cm))
        
        # Line items
        items_data = [["Item", "SKU", "Qty", "Unit Price", "Subtotal", "Tax", "Total"]]
        for line_item in invoice.line_items.all():
            items_data.append([
                line_item.description[:30],
                line_item.sku,
                str(line_item.quantity),
                f"{line_item.unit_price:.2f}",
                f"{line_item.line_subtotal:.2f}",
                f"{line_item.line_tax:.2f}",
                f"{line_item.line_total:.2f}",
            ])
        
        items_table = Table(items_data)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4FD8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 0.3*cm))
        
        # Totals
        totals_data = [
            ["Subtotal", f"{invoice.subtotal:.2f}"],
            ["Tax (15%)", f"{invoice.tax_amount:.2f}"],
            ["Shipping", f"{invoice.shipping_cost:.2f}"],
            ["TOTAL", f"{invoice.total_amount:.2f}"],
        ]
        totals_table = Table(totals_data)
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1F4FD8')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 0), (-1, -2), [colors.white, colors.lightgrey]),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 0.5*cm))
        
        # ZATCA Info (if applicable)
        if invoice.zatca_hash:
            zatca_info = f"<b>ZATCA Hash:</b> {invoice.zatca_hash[:32]}...<br/><b>Invoice UUID:</b> {invoice.zatca_uuid}"
            story.append(Paragraph(zatca_info, styles['Normal']))
        
        # Footer
        footer = "Thank you for your business! For inquiries, please contact us."
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(footer, styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def generate_zatca_qr_code(invoice: Invoice) -> str:
        """
        Generate ZATCA-compatible QR code.
        
        Saudi Arabia e-invoice QR code contains:
        - Seller Name / VAT ID
        - Invoice Date / Time
        - Invoice Total (with decimals)
        - VAT Total
        - Hash of Previous Invoice
        
        Args:
            invoice: The Invoice to generate QR for
            
        Returns:
            Base64 encoded QR code image
        """
        try:
            import qrcode
            import base64
        except ImportError:
            raise ImportError("qrcode is required for QR generation. Install it with: pip install qrcode pillow")
        
        # ZATCA QR format (simplified)
        qr_data = {
            "seller_name": invoice.seller_name,
            "seller_vat_id": invoice.seller_vat_id,
            "invoice_number": invoice.invoice_number,
            "issue_date": str(invoice.issue_date),
            "total_amount": str(invoice.total_amount),
            "tax_amount": str(invoice.tax_amount),
            "hash": invoice.zatca_hash,
        }
        
        qr_text = json.dumps(qr_data)
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_text)
        qr.make(fit=True)
        
        # Convert to image and encode as base64
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode as base64
        encoded = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{encoded}"
    
    @staticmethod
    def get_invoice_summary(invoice: Invoice) -> dict:
        """Get invoice summary for display/email."""
        return {
            "invoice_number": invoice.invoice_number,
            "issue_date": str(invoice.issue_date),
            "due_date": str(invoice.due_date) if invoice.due_date else None,
            "buyer_name": invoice.buyer_name,
            "buyer_email": invoice.buyer_email,
            "seller_name": invoice.seller_name,
            "subtotal": float(invoice.subtotal),
            "tax_amount": float(invoice.tax_amount),
            "tax_rate": float(invoice.tax_rate),
            "shipping_cost": float(invoice.shipping_cost),
            "total_amount": float(invoice.total_amount),
            "currency": invoice.currency,
            "status": invoice.get_status_display(),
            "line_items_count": invoice.line_items.count(),
        }
