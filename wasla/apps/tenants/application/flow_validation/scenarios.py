from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Category, Product
from apps.catalog.services.product_service import ProductService
from apps.customers.services.customer_service import CustomerService
from apps.orders.models import Order, OrderItem
from apps.orders.services.order_lifecycle_service import OrderLifecycleService
from apps.orders.services.order_service import OrderService
from apps.payments.services.payment_service import PaymentService
from apps.reviews.models import Review
from apps.shipping.services.shipping_service import ShippingService
from apps.subscriptions.models import SubscriptionPlan
from apps.subscriptions.services.subscription_service import SubscriptionService
from apps.wallet.services.wallet_service import WalletService
from apps.tenants.models import Tenant

from .base import FlowIssue, FlowResult


class MvpDataIntegrityScenario:
    name = "mvp_data_integrity"

    def run(self, *, tenant: Tenant) -> FlowResult:
        tenant_id = tenant.id
        issues: list[FlowIssue] = []

        invalid_product_categories = (
            Product.objects.filter(store_id=tenant_id)
            .filter(categories__isnull=False)
            .exclude(categories__store_id=tenant_id)
            .values_list("id", "sku", "categories__id", "categories__store_id")[:100]
        )
        for product_id, sku, category_id, category_store_id in invalid_product_categories:
            issues.append(
                FlowIssue(
                    code="catalog.product_category_tenant_mismatch",
                    message="Product is linked to a category from another tenant.",
                    context={
                        "product_id": product_id,
                        "sku": sku,
                        "category_id": category_id,
                        "category_store_id": category_store_id,
                        "expected_store_id": tenant_id,
                    },
                )
            )

        invalid_orders = (
            Order.objects.for_tenant(tenant_id)
            .exclude(customer__store_id=tenant_id)
            .values_list("id", "order_number", "customer_id", "customer__store_id")[:100]
        )
        for order_id, order_number, customer_id, customer_store_id in invalid_orders:
            issues.append(
                FlowIssue(
                    code="orders.order_customer_tenant_mismatch",
                    message="Order.store_id does not match the customer.store_id.",
                    context={
                        "order_id": order_id,
                        "order_number": order_number,
                        "customer_id": customer_id,
                        "customer_store_id": customer_store_id,
                        "expected_store_id": tenant_id,
                    },
                )
            )

        invalid_items = (
            OrderItem.objects.for_tenant(tenant_id)
            .exclude(product__store_id=tenant_id)
            .values_list("id", "order_id", "product_id", "product__store_id")[:100]
        )
        for item_id, order_id, product_id, product_store_id in invalid_items:
            issues.append(
                FlowIssue(
                    code="orders.order_item_product_tenant_mismatch",
                    message="Order item product belongs to a different tenant.",
                    context={
                        "order_item_id": item_id,
                        "order_id": order_id,
                        "product_id": product_id,
                        "product_store_id": product_store_id,
                        "expected_store_id": tenant_id,
                    },
                )
            )

        invalid_reviews = (
            Review.objects.for_tenant(tenant_id)
            .filter(product__store_id=tenant_id, customer__isnull=False)
            .exclude(customer__store_id=tenant_id)
            .values_list("id", "product_id", "customer_id", "customer__store_id")[:100]
        )
        for review_id, product_id, customer_id, customer_store_id in invalid_reviews:
            issues.append(
                FlowIssue(
                    code="reviews.review_customer_tenant_mismatch",
                    message="Review customer belongs to a different tenant than the product.",
                    context={
                        "review_id": review_id,
                        "product_id": product_id,
                        "customer_id": customer_id,
                        "customer_store_id": customer_store_id,
                        "expected_store_id": tenant_id,
                    },
                )
            )

        return FlowResult(
            scenario=self.name,
            tenant_id=tenant_id,
            tenant_slug=tenant.slug,
            issues=tuple(issues),
        )


class MvpServiceSmokeFlowScenario:
    name = "mvp_service_smoke_flow"

    def run(self, *, tenant: Tenant) -> FlowResult:
        tenant_id = tenant.id
        issues: list[FlowIssue] = []

        with transaction.atomic():
            subscription = SubscriptionService.get_active_subscription(tenant_id)
            if not subscription:
                plan = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "id").first()
                if not plan:
                    issues.append(
                        FlowIssue(
                            code="subscriptions.no_active_plan",
                            message=(
                                "No active subscription plan exists; seed an active plan "
                                "before running smoke flows."
                            ),
                            context={"tenant_id": tenant_id, "tenant_slug": tenant.slug},
                        )
                    )
                    transaction.set_rollback(True)
                    return FlowResult(
                        scenario=self.name,
                        tenant_id=tenant_id,
                        tenant_slug=tenant.slug,
                        issues=tuple(issues),
                    )
                SubscriptionService.subscribe_store(tenant_id, plan)

            category = Category.objects.create(
                store_id=tenant_id,
                name=f"Flow Category {uuid.uuid4().hex[:8]}",
            )

            sku = f"FLOW-{uuid.uuid4().hex[:10].upper()}"
            product = ProductService.create_product(
                store_id=tenant_id,
                sku=sku,
                name="Flow Product",
                price=Decimal("10.00"),
                categories=[category],
                quantity=5,
                image_file=None,
            )

            customer_email = f"flow-{uuid.uuid4().hex[:12]}@example.com"
            customer = CustomerService.create_customer(
                email=customer_email,
                full_name="Flow Customer",
                store_id=tenant_id,
            )

            order = OrderService.create_order(
                customer,
                items=[{"product": product, "quantity": 1, "price": product.price}],
                store_id=tenant_id,
                tenant_id=tenant_id,
            )

            wallet = WalletService.get_or_create_wallet(tenant_id, tenant_id=tenant_id)
            starting_balance = wallet.balance

            payment = PaymentService.initiate_payment(order, method="card")
            order.refresh_from_db()
            if payment.status != "success":
                issues.append(
                    FlowIssue(
                        code="payments.payment_not_success",
                        message="Expected dummy gateway payment to succeed.",
                        context={"order_id": order.id, "payment_id": payment.id, "status": payment.status},
                    )
                )
            if order.status != "paid":
                issues.append(
                    FlowIssue(
                        code="orders.order_not_paid_after_payment",
                        message="Order should be marked paid after successful payment.",
                        context={"order_id": order.id, "status": order.status},
                    )
                )

            OrderLifecycleService.transition(order=order, new_status="processing")
            order.refresh_from_db()
            if order.status != "processing":
                issues.append(
                    FlowIssue(
                        code="orders.order_not_processing",
                        message="Order should transition to processing.",
                        context={"order_id": order.id, "status": order.status},
                    )
                )

            shipment = ShippingService.create_shipment(order, carrier="dhl")
            order.refresh_from_db()
            if not shipment.tracking_number:
                issues.append(
                    FlowIssue(
                        code="shipping.tracking_number_missing",
                        message="Shipment should have a tracking number after carrier creation.",
                        context={"shipment_id": shipment.id},
                    )
                )
            if order.status != "shipped":
                issues.append(
                    FlowIssue(
                        code="orders.order_not_shipped",
                        message="Order should be marked shipped after shipment creation.",
                        context={"order_id": order.id, "status": order.status},
                    )
                )

            OrderLifecycleService.transition(order=order, new_status="delivered")
            OrderLifecycleService.transition(order=order, new_status="completed")

            wallet.refresh_from_db()
            expected_balance = starting_balance + order.total_amount
            if wallet.balance != expected_balance:
                issues.append(
                    FlowIssue(
                        code="wallet.balance_not_credited",
                        message="Wallet should be credited once when order is completed.",
                        context={
                            "wallet_id": wallet.id,
                            "starting_balance": str(starting_balance),
                            "expected_balance": str(expected_balance),
                            "actual_balance": str(wallet.balance),
                            "order_total": str(order.total_amount),
                        },
                    )
                )

            transaction.set_rollback(True)

        return FlowResult(
            scenario=self.name,
            tenant_id=tenant_id,
            tenant_slug=tenant.slug,
            issues=tuple(issues),
        )
