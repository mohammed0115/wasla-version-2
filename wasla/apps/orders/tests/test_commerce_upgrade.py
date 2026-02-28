"""
Integration tests for production commerce upgrade

Tests:
- StockReservation functionality
- Invoice generation and ZATCA compliance
- RMA workflow
- Refund processing
- OrderLifecycleService state transitions
- Tenant isolation
"""

from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from io import BytesIO

from wasla.apps.orders.models import Order, OrderItem, Invoice, InvoiceLineItem, RMA, ReturnItem, RefundTransaction, StockReservation
from wasla.apps.orders.services.stock_reservation_service import StockReservationService
from wasla.apps.orders.services.invoice_service import InvoiceService
from wasla.apps.orders.services.returns_service import ReturnsService, RefundsService
from wasla.apps.orders.services.order_lifecycle_service import OrderLifecycleService
from wasla.apps.orders.services.order_service import OrderService
from wasla.apps.catalog.models import Product, Category, Inventory
from wasla.apps.stores.models import Store
from wasla.apps.accounts.models import TenantProfile


class StockReservationServiceTestCase(TestCase):
    """Test StockReservationService for inventory management"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = TenantProfile.objects.create(name="Test Tenant")
        self.store = Store.objects.create(tenant=self.tenant, name="Test Store")
        self.user = User.objects.create_user(username="testuser", password="testpass")
        
        # Create product and inventory
        self.category = Category.objects.create(name="Electronics", tenant=self.tenant)
        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name="Test Product",
            sku="TEST-001",
            price=Decimal("100.00"),
        )
        self.inventory = Inventory.objects.create(
            product=self.product,
            store=self.store,
            quantity_on_hand=100,
            quantity_reserved=0,
        )
        
        # Create order
        self.order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer_email="test@example.com",
            total_amount=Decimal("100.00"),
            status="pending",
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=5,
            unit_price=Decimal("100.00"),
            subtotal=Decimal("500.00"),
        )
        
        self.service = StockReservationService()
    
    def test_reserve_stock_success(self):
        """Test successful stock reservation"""
        reservation = self.service.reserve_stock(
            order_item=self.order_item,
            quantity=5,
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.reserved_quantity, 5)
        self.assertEqual(reservation.status, 'reserved')
        self.assertTrue(reservation.is_expired() == False)
        
        # Check inventory update
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_reserved, 5)
    
    def test_reserve_stock_insufficient_quantity(self):
        """Test reservation fails with insufficient stock"""
        # Try to reserve more than available
        with self.assertRaises(ValueError):
            self.service.reserve_stock(
                order_item=self.order_item,
                quantity=150,  # More than on_hand (100)
                tenant_id=self.tenant.id,
                store_id=self.store.id,
            )
    
    def test_confirm_reservation(self):
        """Test confirming reservation extends TTL"""
        reservation = self.service.reserve_stock(
            order_item=self.order_item,
            quantity=5,
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        
        original_expires = reservation.expires_at
        updated = self.service.confirm_reservation(reservation)
        
        self.assertEqual(updated.status, 'confirmed')
        # Should extend TTL (15 min to 30 min)
        self.assertGreater(updated.expires_at, original_expires)
    
    def test_release_reservation(self):
        """Test releasing reservation returns stock"""
        reservation = self.service.reserve_stock(
            order_item=self.order_item,
            quantity=5,
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        
        released = self.service.release_reservation(reservation, reason="order_cancelled")
        
        self.assertEqual(released.status, 'released')
        
        # Check inventory returned
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_reserved, 0)
    
    def test_reservation_expiry(self):
        """Test reservation expiry detection"""
        reservation = self.service.reserve_stock(
            order_item=self.order_item,
            quantity=5,
            tenant_id=self.tenant.id,
            store_id=self.store.id,
        )
        
        # Set expiry to past
        reservation.expires_at = timezone.now() - timedelta(minutes=1)
        reservation.save()
        
        self.assertTrue(reservation.is_expired())


class InvoiceServiceTestCase(TestCase):
    """Test InvoiceService for invoice generation"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = TenantProfile.objects.create(name="Test Tenant", vat_id="300123456700003")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Test Store",
            name_ar="متجر اختبار",
            vat_id="300123456700003",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass")
        
        # Create product and inventory
        self.category = Category.objects.create(name="Electronics", tenant=self.tenant)
        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name="Test Product",
            sku="TEST-001",
            price=Decimal("100.00"),
        )
        
        # Create order
        self.order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer_email="customer@example.com",
            customer_name="Test Customer",
            total_amount=Decimal("115.00"),
            status="paid",
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            unit_price=Decimal("100.00"),
            subtotal=Decimal("100.00"),
        )
        
        self.service = InvoiceService()
    
    def test_create_invoice_from_order(self):
        """Test invoice creation from order"""
        invoice = self.service.create_invoice_from_order(self.order)
        
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.order, self.order)
        self.assertEqual(invoice.subtotal, Decimal("100.00"))
        self.assertEqual(invoice.tax_amount, Decimal("15.00"))  # 15% VAT
        self.assertEqual(invoice.total_amount, Decimal("115.00"))
        self.assertEqual(invoice.currency, "SAR")
    
    def test_invoice_sequential_numbering(self):
        """Test invoice numbering is sequential per tenant/store"""
        invoice1 = self.service.create_invoice_from_order(self.order)
        
        # Create second order and invoice
        order2 = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer_email="customer2@example.com",
            total_amount=Decimal("230.00"),
            status="paid",
        )
        invoice2 = self.service.create_invoice_from_order(order2)
        
        # Verify sequential numbering
        self.assertNotEqual(invoice1.invoice_number, invoice2.invoice_number)
        # Both should follow pattern INV-<TENANT>-<STORE>-<SEQ>
        self.assertTrue(invoice1.invoice_number.startswith(f"INV-{self.tenant.id}-"))
        self.assertTrue(invoice2.invoice_number.startswith(f"INV-{self.tenant.id}-"))
    
    def test_invoice_line_items(self):
        """Test invoice has correct line items"""
        invoice = self.service.create_invoice_from_order(self.order)
        
        line_items = invoice.line_items.all()
        self.assertEqual(len(line_items), 1)
        
        line = line_items[0]
        self.assertEqual(line.quantity, 1)
        self.assertEqual(line.unit_price, Decimal("100.00"))
        self.assertEqual(line.line_subtotal, Decimal("100.00"))
        self.assertEqual(line.line_tax, Decimal("15.00"))
    
    def test_issue_invoice(self):
        """Test issuing invoice transitions it to issued state"""
        invoice = self.service.create_invoice_from_order(self.order)
        
        issued = self.service.issue_invoice(invoice, previous_hash=None)
        
        self.assertEqual(issued.status, 'issued')
        self.assertIsNotNone(issued.zatca_hash)
        self.assertIsNotNone(issued.issued_at)
    
    def test_generate_pdf(self):
        """Test PDF generation"""
        invoice = self.service.create_invoice_from_order(self.order)
        issued = self.service.issue_invoice(invoice, previous_hash=None)
        
        pdf_bytes = self.service.generate_pdf(issued)
        
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))  # PDF header
    
    def test_zatca_qr_code_generation(self):
        """Test ZATCA QR code generation"""
        invoice = self.service.create_invoice_from_order(self.order)
        issued = self.service.issue_invoice(invoice, previous_hash=None)
        
        qr_code = self.service.generate_zatca_qr_code(issued)
        
        self.assertIsNotNone(qr_code)
        self.assertTrue(len(qr_code) > 0)
        # Should contain invoice data in encoded format
        self.assertIn('data:image/png;base64', qr_code)


class ReturnsServiceTestCase(TestCase):
    """Test RMA and refund workflows"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = TenantProfile.objects.create(name="Test Tenant")
        self.store = Store.objects.create(tenant=self.tenant, name="Test Store")
        self.user = User.objects.create_user(username="testuser", password="testpass")
        
        # Create product
        self.category = Category.objects.create(name="Electronics", tenant=self.tenant)
        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name="Test Product",
            sku="TEST-001",
            price=Decimal("100.00"),
        )
        
        # Create order
        self.order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer_email="test@example.com",
            total_amount=Decimal("100.00"),
            status="delivered",
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price=Decimal("100.00"),
            subtotal=Decimal("200.00"),
        )
        
        self.returns_service = ReturnsService()
        self.refunds_service = RefundsService()
    
    def test_request_rma(self):
        """Test creating RMA request"""
        rma = self.returns_service.request_rma(
            order=self.order,
            items=[{
                'order_item': self.order_item,
                'quantity': 1,
                'reason': 'defective',
            }],
            reason='defective',
            description='Product not working',
        )
        
        self.assertIsNotNone(rma)
        self.assertEqual(rma.status, 'requested')
        self.assertIsNotNone(rma.rma_number)
        self.assertEqual(rma.items.count(), 1)
    
    def test_approve_rma(self):
        """Test approving RMA"""
        rma = self.returns_service.request_rma(
            order=self.order,
            items=[{
                'order_item': self.order_item,
                'quantity': 1,
                'reason': 'defective',
            }],
            reason='defective',
            description='Product not working',
        )
        
        approved_rma = self.returns_service.approve_rma(rma, comment="Approved for return")
        
        self.assertEqual(approved_rma.status, 'approved')
        self.assertIsNotNone(approved_rma.approved_at)
    
    def test_rma_workflow_complete(self):
        """Test complete RMA workflow from request to completion"""
        # Request RMA
        rma = self.returns_service.request_rma(
            order=self.order,
            items=[{
                'order_item': self.order_item,
                'quantity': 1,
                'reason': 'defective',
            }],
            reason='defective',
            description='Product defective',
        )
        
        # Approve RMA
        rma = self.returns_service.approve_rma(rma)
        
        # Track return shipment
        rma = self.returns_service.track_return_shipment(
            rma,
            carrier='FedEx',
            tracking_number='1234567890',
        )
        self.assertEqual(rma.status, 'in_transit')
        
        # Receive return
        rma = self.returns_service.receive_return(rma)
        self.assertEqual(rma.status, 'received')
        
        # Inspect return
        rma = self.returns_service.inspect_return(
            rma,
            inspections=[{
                'return_item_id': rma.items.first().id,
                'condition': 'damaged',
                'refund_amount': Decimal("80.00"),
            }],
        )
        self.assertEqual(rma.status, 'inspected')
        
        # Complete RMA with refund
        rma = self.returns_service.complete_rma(rma, refund_method='original')
        self.assertEqual(rma.status, 'completed')
        self.assertIsNotNone(rma.completed_at)
    
    def test_request_refund(self):
        """Test creating refund request"""
        refund = self.refunds_service.request_refund(
            order=self.order,
            amount=Decimal("100.00"),
            reason="customer_request",
        )
        
        self.assertIsNotNone(refund)
        self.assertEqual(refund.status, 'initiated')
        self.assertEqual(refund.amount, Decimal("100.00"))
        self.assertIsNotNone(refund.refund_id)


class OrderLifecycleServiceTestCase(TestCase):
    """Test OrderLifecycleService state transitions"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = TenantProfile.objects.create(name="Test Tenant")
        self.store = Store.objects.create(tenant=self.tenant, name="Test Store")
        
        # Create order
        self.order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer_email="test@example.com",
            total_amount=Decimal("100.00"),
            status="pending",
        )
        
        self.service = OrderLifecycleService()
    
    def test_transition_pending_to_paid(self):
        """Test pending -> paid transition"""
        result = self.service.transition(self.order, 'paid')
        
        self.assertTrue(result)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
    
    def test_transition_paid_to_processing(self):
        """Test paid -> processing transition"""
        self.order.status = 'paid'
        self.order.save()
        
        result = self.service.transition(self.order, 'processing')
        
        self.assertTrue(result)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processing')
    
    def test_transition_delivered_to_returned(self):
        """Test delivered -> returned transition (new state)"""
        self.order.status = 'delivered'
        self.order.save()
        
        result = self.service.transition(self.order, 'returned')
        
        self.assertTrue(result)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'returned')
    
    def test_transition_returned_to_partially_refunded(self):
        """Test returned -> partially_refunded transition (new state)"""
        self.order.status = 'returned'
        self.order.save()
        
        result = self.service.transition(self.order, 'partially_refunded')
        
        self.assertTrue(result)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'partially_refunded')
    
    def test_transition_partially_refunded_to_refunded(self):
        """Test partially_refunded -> refunded transition"""
        self.order.status = 'partially_refunded'
        self.order.save()
        
        result = self.service.transition(self.order, 'refunded')
        
        self.assertTrue(result)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'refunded')
    
    def test_invalid_transition_raises_error(self):
        """Test invalid state transition raises error"""
        self.order.status = 'pending'
        self.order.save()
        
        # pending cannot go to refunded directly
        with self.assertRaises(ValueError):
            self.service.transition(self.order, 'refunded')


class TenantIsolationTestCase(TestCase):
    """Test tenant isolation in new models"""
    
    def setUp(self):
        """Set up test data with multiple tenants"""
        self.tenant1 = TenantProfile.objects.create(name="Tenant 1")
        self.tenant2 = TenantProfile.objects.create(name="Tenant 2")
        
        self.store1 = Store.objects.create(tenant=self.tenant1, name="Store 1")
        self.store2 = Store.objects.create(tenant=self.tenant2, name="Store 2")
        
        # Create products
        self.category1 = Category.objects.create(name="Electronics", tenant=self.tenant1)
        self.category2 = Category.objects.create(name="Electronics", tenant=self.tenant2)
        
        self.product1 = Product.objects.create(
            tenant=self.tenant1,
            category=self.category1,
            name="Product 1",
            sku="PROD-1",
            price=Decimal("100.00"),
        )
        self.product2 = Product.objects.create(
            tenant=self.tenant2,
            category=self.category2,
            name="Product 2",
            sku="PROD-2",
            price=Decimal("100.00"),
        )
        
        # Create orders
        self.order1 = Order.objects.create(
            tenant=self.tenant1,
            store=self.store1,
            customer_email="test1@example.com",
            total_amount=Decimal("100.00"),
        )
        self.order2 = Order.objects.create(
            tenant=self.tenant2,
            store=self.store2,
            customer_email="test2@example.com",
            total_amount=Decimal("100.00"),
        )
    
    def test_invoices_tenant_isolation(self):
        """Test invoices are isolated per tenant"""
        service = InvoiceService()
        
        invoice1 = service.create_invoice_from_order(self.order1)
        invoice2 = service.create_invoice_from_order(self.order2)
        
        self.assertEqual(invoice1.tenant_id, self.tenant1.id)
        self.assertEqual(invoice2.tenant_id, self.tenant2.id)
        
        # Tenant 1 should not see tenant 2's invoice
        tenant1_invoices = Invoice.objects.filter(tenant_id=self.tenant1.id)
        self.assertIn(invoice1, tenant1_invoices)
        self.assertNotIn(invoice2, tenant1_invoices)
    
    def test_rma_tenant_isolation(self):
        """Test RMA records are isolated per tenant"""
        category1 = Category.objects.create(name="Test", tenant=self.tenant1)
        product1 = Product.objects.create(
            tenant=self.tenant1,
            category=category1,
            name="Test",
            price=Decimal("100"),
        )
        oi1 = OrderItem.objects.create(
            order=self.order1,
            product=product1,
            quantity=1,
            unit_price=Decimal("100"),
            subtotal=Decimal("100"),
        )
        
        category2 = Category.objects.create(name="Test", tenant=self.tenant2)
        product2 = Product.objects.create(
            tenant=self.tenant2,
            category=category2,
            name="Test",
            price=Decimal("100"),
        )
        oi2 = OrderItem.objects.create(
            order=self.order2,
            product=product2,
            quantity=1,
            unit_price=Decimal("100"),
            subtotal=Decimal("100"),
        )
        
        returns_service = ReturnsService()
        
        rma1 = returns_service.request_rma(
            order=self.order1,
            items=[{'order_item': oi1, 'quantity': 1, 'reason': 'defective'}],
            reason='defective',
        )
        rma2 = returns_service.request_rma(
            order=self.order2,
            items=[{'order_item': oi2, 'quantity': 1, 'reason': 'defective'}],
            reason='defective',
        )
        
        self.assertEqual(rma1.tenant_id, self.tenant1.id)
        self.assertEqual(rma2.tenant_id, self.tenant2.id)
        
        # Tenant 1 should not see tenant 2's RMA
        tenant1_rmas = RMA.objects.filter(tenant_id=self.tenant1.id)
        self.assertIn(rma1, tenant1_rmas)
        self.assertNotIn(rma2, tenant1_rmas)
