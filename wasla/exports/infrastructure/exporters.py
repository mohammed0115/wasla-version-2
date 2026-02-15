from __future__ import annotations

import io
import csv
from datetime import datetime

from django.utils import timezone


class OrdersCSVExporter:
    headers = [
        "order_number",
        "status",
        "payment_status",
        "total_amount",
        "currency",
        "customer_name",
        "customer_email",
        "created_at",
    ]

    @staticmethod
    def stream(queryset):
        yield _csv_row(OrdersCSVExporter.headers)
        for order in queryset.iterator():
            yield _csv_row(
                [
                    order.order_number,
                    order.status,
                    order.payment_status,
                    str(order.total_amount),
                    order.currency,
                    order.customer_name,
                    order.customer_email,
                    order.created_at.isoformat() if order.created_at else "",
                ]
            )


class InvoicePDFExporter:
    @staticmethod
    def render(order) -> bytes:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except Exception:
            return _render_simple_pdf(order)

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        y = height - 50
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, "Invoice")
        y -= 30
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Order: {order.order_number}")
        y -= 15
        c.drawString(50, y, f"Date: {order.created_at.date() if order.created_at else ''}")
        y -= 15
        c.drawString(50, y, f"Customer: {order.customer_name} {order.customer_email}")
        y -= 25

        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Items")
        y -= 15
        c.setFont("Helvetica", 10)
        for item in order.items.all():
            line = f"{item.product.name} x{item.quantity} @ {item.price}"
            c.drawString(60, y, line)
            y -= 14
            if y < 80:
                c.showPage()
                y = height - 50

        y -= 10
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"Total: {order.total_amount} {order.currency}")
        c.showPage()
        c.save()
        return buffer.getvalue()


def _csv_row(row: list) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def _render_simple_pdf(order) -> bytes:
    lines = [
        "Invoice",
        f"Order: {order.order_number}",
        f"Date: {order.created_at.date() if order.created_at else ''}",
        f"Customer: {order.customer_name} {order.customer_email}",
        "Items:",
    ]
    for item in order.items.all():
        lines.append(f"- {item.product.name} x{item.quantity} @ {item.price}")
    lines.append(f"Total: {order.total_amount} {order.currency}")
    return _minimal_pdf(lines)


def _minimal_pdf(lines: list[str]) -> bytes:
    """
    Minimal PDF generator with a single page and basic text.
    """
    text = "\\n".join(lines)
    objects = []

    def _obj(data: str) -> int:
        objects.append(data)
        return len(objects)

    font_obj = _obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    content_stream = f"BT /F1 12 Tf 50 750 Td ({_escape_pdf(text)}) Tj ET"
    content_obj = _obj(f"<< /Length {len(content_stream)} >>\\nstream\\n{content_stream}\\nendstream")
    page_obj = _obj(f"<< /Type /Page /Parent 4 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_obj} 0 R /MediaBox [0 0 595 842] >>")
    pages_obj = _obj(f"<< /Type /Pages /Kids [{page_obj} 0 R] /Count 1 >>")
    catalog_obj = _obj(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")

    xref_positions = []
    pdf = "%PDF-1.4\\n"
    for idx, obj in enumerate(objects, start=1):
        xref_positions.append(len(pdf))
        pdf += f"{idx} 0 obj\\n{obj}\\nendobj\\n"
    xref_start = len(pdf)
    pdf += "xref\\n0 {count}\\n0000000000 65535 f \\n".format(count=len(objects) + 1)
    for pos in xref_positions:
        pdf += f"{pos:010d} 00000 n \\n"
    pdf += "trailer\\n<< /Size {size} /Root {root} 0 R >>\\nstartxref\\n{xref}\\n%%EOF".format(
        size=len(objects) + 1, root=catalog_obj, xref=xref_start
    )
    return pdf.encode("latin-1", errors="ignore")


def _escape_pdf(text: str) -> str:
    return text.replace("\\\\", "\\\\\\\\").replace("(", "\\(").replace(")", "\\)")
