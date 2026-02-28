"""
Integration tests for production commerce order lifecycle.

Tests:
1. Stock reservation and auto-release
2. Partial shipments
3. RMA and refund flow
4. Invoice generation
5. Order lifecycle with returns
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.orders.models import Order, OrderItem, StockReservation
from apps.orders.models_extended import (
    RMA, ReturnItem, Invoice, RefundTransaction, ShipmentLineItem
)
from apps.orders.services.stock_management_service import StockManagementService
from apps.orders.services.refund_service import RefundService
from apps.orders.services.invoice_service import InvoiceService
from apps.orders.services.order_lifecycle_service import OrderLifecycleService
from apps.catalog.models import Product
from apps.customers.models import Customer
from apps.stores.models import Store
from apps.tenants.models import Tenant
from apps.shipping.models import Shipment


class StockReservationTests(TestCase):
    """Test stock reservation and auto-release functionality."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="test-tenant", name="Test Tenant")
        self.store = Store.objects.create(
            owner=get_user_model().objects.create_user(
                username="owner1", password="pass123"
            ),
            tenant=self.tenant,
            name="Test Store",
            slug="test-store",
            subdomain="test-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="TEST-001",
            name="Test Product",
            price="100.00",
            stock=10,
            is_active=True,
        )
        self.customer = Customer.objects.create(
            store_id=self.store.id,
            email="test@example.com",
            full_name="Test Customer",
        )
    
    def test_reserve_stock(self):
        """Test stock reservation creates StockReservation."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-001",
            customer=self.customer,
            status="pending",
        )
        order_item = OrderItem.objects.create(
            tenant_id=self.tenant.id,
            order=order,
            product=self.product,
            quantity=2,
            price=Decimal("100.00"),
        )
        
        reservation = StockManagementService.reserve_order_items(order_item)
        
        self.assertEqual(reservation.status, "reserved")
        self.assertEqual(reservation.quantity, 2)
        self.assertEqual(reservation.product, self.product)
        self.assertIsNotNone(reservation.expires_at)
    
    def test_insufficient_stock_raises(self):
        """Test reservation fails when stock insufficient."""
        self.product.stock = 1
        self.product.save()
        
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-002",
            customer=self.customer,
        )
        order_item = OrderItem.objects.create(
            tenant_id=self.tenant.id,
            order=order,
            product=self.product,
            quantity=5,  # More than available
            price=Decimal("100.00"),
        )
        
        with self.assertRaises(ValueError):
            StockManagementService.reserve_order_items(order_item)
    
    def test_confirm_extends_expiration(self):
        """Test confirm_reservation extends expire time."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-003",
            customer=self.customer,
        )
        order_item = OrderItem.objects.create(
            tenant_id=self.tenant.id,
            order=order,
            product=self.product,
            quantity=1,
            price=Decimal("100.00"),
        )
        
        reservation = StockManagementService.reserve_order_items(order_item, timeout_minutes=30)
        initial_expiry = reservation.expires_at
        
        StockManagementService.confirm_reservation(reservation)
        reservation.refresh_from_db()
        
        self.assertEqual(reservation.status, "confirmed")
        self.assertGreater(reservation.expires_at, initial_expiry)
    
    def test_release_reservation(self):
        """Test releasing a reservation."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-004",
            customer=self.customer,
        )
        order_item = OrderItem.objects.create(
            tenant_id=self.tenant.id,
            order=order,
            product=self.product,
            quantity=1,
            price=Decimal("100.00"),
        )
        
        reservation = StockManagementService.reserve_order_items(order_item)
        StockManagementService.release_reservation(reservation, reason="order_cancelled")
        reservation.refresh_from_db()
        
        self.assertEqual(reservation.status, "released")
        self.assertIsNotNone(reservation.released_at)


class InvoiceGenerationTests(TestCase):
    """Test invoice generation and ZATCA compliance."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            slug="test-tenant",
            name="Test Tenant",
            vat_number="123456789",
        )
        self.store = Store.objects.create(
            owner=get_user_model().objects.create_user(
                username="owner2", password="pass123"
            ),
            tenant=self.tenant,
            name="Test Store",
            slug="test-store",
            subdomain="test-store",
            status=Store.STATUS_ACTIVE,
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="INV-001",
            name="Invoice Test Product",
            price="100.00",
            is_active=True,
        )
        self.customer = Customer.objects.create(
            store_id=self.store.id,
            email="customer@example.com",
            full_name="Test Customer",
        )
    
    def test_generate_invoice(self):
        """Test invoice generation from order."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-INV-001",
            customer=self.customer,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("15.00"),
            total_amount=Decimal("115.00"),
            status="paid",
        )
        
        invoice = InvoiceService.generate_invoice(order, save_pdf=False)
        
        self.assertEqual(invoice.order, order)
        self.assertIsNotNone(invoice.invoice_number)
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.total_amount, Decimal("115.00"))
    
    def test_invoice_numbering_sequential(self):
        """Test invoice numbers are sequential per tenant."""
        order1 = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-SEQ-001",
            customer=self.customer,
            total_amount=Decimal("100.00"),
        )
        order2 = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-SEQ-002",
            customer=self.customer,
            total_amount=Decimal("200.00"),
        )
        
        inv1 = InvoiceService.generate_invoice(order1, save_pdf=False)
        inv2 = InvoiceService.generate_invoice(order2, save_pdf=False)
        
        self.assertLess(inv1.invoice_number, inv2.invoice_number)
    
    def test_mark_invoice_as_issued(self):
        """Test marking invoice as issued."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-ISS-001",
            customer=self.customer,
            total_amount=Decimal("100.00"),
        )
        invoice = InvoiceService.generate_invoice(order, save_pdf=False)
        
        InvoiceService.mark_as_issued(invoice)
        invoice.refresh_from_db()
        
        self.assertEqual(invoice.status, "issued")


class RMAAndRefundTests(TransactionTestCase):
    """Test RMA and refund flow integration."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="refund-test", name="Refund Test")
        self.store = Store.objects.create(
            owner=get_user_model().objects.create_user(
                username="owner3", password="pass123"
            ),
            tenant=self.tenant,
            name="Refund Store",
            slug="refund-store",
            subdomain="refund-store",
            status=Store.STATUS_ACTIVE,
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="RMA-001",
            name="RMA Test Product",
            price="100.00",
            is_active=True,
        )
        self.customer = Customer.objects.create(
            store_id=self.store.id,
            email="rma@example.com",
            full_name="RMA Customer",
        )
    
    def test_create_rma(self):
        """Test creating an RMA."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-RMA-001",
            customer=self.customer,
            status="delivered",
            total_amount=Decimal("100.00"),
        )
        
        rma = RMA.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order=order,
            rma_number="RMA-001",
            reason=RMA.REASON_DEFECTIVE,
        )
        
        self.assertEqual(rma.status, "requested")
        self.assertEqual(rma.order, order)
    
    def test_initiate_refund(self):
        """Test initiating a refund."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-REFUND-001",
            customer=self.customer,
            status="delivered",
            total_amount=Decimal("100.00"),
        )
        
        refund = RefundService.initiate_refund(
            order=order,
            amount=Decimal("100.00"),
            reason="Customer return",
        )
        
        self.assertEqual(refund.status, "initiated")
        self.assertEqual(refund.amount, Decimal("100.00"))
        self.assertEqual(refund.order, order)
    
    def test_refund_exceeds_order_amount(self):
        """Test refund validation prevents over-refunding."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-OVER-001",
            customer=self.customer,
            total_amount=Decimal("100.00"),
        )
        
        with self.assertRaises(ValueError):
            RefundService.initiate_refund(
                order=order,
                amount=Decimal("150.00"),  # More than order total
            )


class OrderLifecycleWithReturnsTests(TestCase):
    """Test order lifecycle with return/refund states."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            slug="lifecycle-test", name="Lifecycle Test"
        )
        self.store = Store.objects.create(
            owner=get_user_model().objects.create_user(
                username="owner4", password="pass123"
            ),
            tenant=self.tenant,
            name="Lifecycle Store",
            slug="lifecycle-store",
            subdomain="lifecycle-store",
            status=Store.STATUS_ACTIVE,
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="LC-001",
            name="Lifecycle Product",
            price="100.00",
            is_active=True,
        )
        self.customer = Customer.objects.create(
            store_id=self.store.id,
            email="lifecycle@example.com",
            full_name="Lifecycle Customer",
        )
    
    def test_order_returned_status(self):
        """Test transitioning to returned status."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-RET-001",
            customer=self.customer,
            status="delivered",
            total_amount=Decimal("100.00"),
        )
        
        # Create shipment (required for delivered status)
        shipment = Shipment.objects.create(
            order=order,
            carrier="dhl",
            status="delivered",
            tenant_id=self.tenant.id,
        )
        
        # Should be able to return from delivered
        OrderLifecycleService.transition(order=order, new_status="returned")
        order.refresh_from_db()
        
        self.assertEqual(order.status, "returned")
    
    def test_order_partial_refund_status(self):
        """Test transitioning to partially_refunded status."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-PREF-001",
            customer=self.customer,
            status="returned",
            total_amount=Decimal("100.00"),
        )
        
        OrderLifecycleService.transition(order=order, new_status="partially_refunded")
        order.refresh_from_db()
        
        self.assertEqual(order.status, "partially_refunded")
    
    def test_order_full_refund_status(self):
        """Test transitioning to refunded status."""
        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number="ORD-FREF-001",
            customer=self.customer,
            status="partially_refunded",
            total_amount=Decimal("100.00"),
        )
        
        OrderLifecycleService.transition(order=order, new_status="refunded")
        order.refresh_from_db()
        
        self.assertEqual(order.status, "refunded")
