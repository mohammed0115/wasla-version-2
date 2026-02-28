"""
Dashboard services for KPI calculations and analytics.

Services for:
- Merchant KPI Dashboard (per-store metrics)
- Revenue charts (7-day, 30-day trends)
- Admin Executive Dashboard (platform-wide metrics)
- Event tracking (product_view, add_to_cart, checkout_started, purchase_completed)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import (
    Count, Sum, Q, F, Case, When, DecimalField, IntegerField, Avg, Window,
    CharField, Value, IntegerField as IntField
)
from django.db.models.functions import Coalesce, Cast, TruncDate, Extract, Lag
from django.utils import timezone
from django.core.cache import cache

from apps.analytics.models import Event
from apps.orders.models import Order, OrderItem
from apps.catalog.models import Product, ProductVariant
from apps.cart.models import Cart
from apps.purchases.models import Purchase

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class MerchantKPI:
    """Merchant KPI metrics for a store."""
    revenue_today: Decimal
    orders_today: int
    conversion_rate: float  # percentage
    low_stock_products: list[dict]  # [{'product_id': int, 'name': str, 'stock': int}]
    revenue_7d: Decimal
    revenue_30d: Decimal
    orders_7d: int
    orders_30d: int
    avg_order_value: Decimal
    cart_abandonment_rate: float
    timestamp: datetime


@dataclass
class RevenuePoint:
    """A single point in a revenue chart."""
    date: str
    revenue: Decimal
    orders: int
    avg_order_value: Decimal


@dataclass
class RevenueChart:
    """Revenue chart data."""
    period: str  # "7d" or "30d"
    points: list[RevenuePoint]
    total_revenue: Decimal
    total_orders: int
    avg_daily_revenue: Decimal
    timestamp: datetime


@dataclass
class AdminKPI:
    """Platform-wide KPIs for admin executive dashboard."""
    gmv: Decimal  # Gross Merchandise Volume (all orders total)
    mrr: Decimal  # Monthly Recurring Revenue
    active_stores: int
    churn_rate: float  # percentage - stores inactive
    total_customers: int
    avg_order_value: Decimal
    conversion_rate: float
    top_products: list[dict]
    top_merchants: list[dict]
    payment_success_rate: float
    timestamp: datetime


@dataclass
class EventFunnel:
    """Conversion funnel for user journey."""
    product_views: int
    add_to_cart: int
    checkout_started: int
    purchase_completed: int
    view_to_cart_rate: float
    cart_to_checkout_rate: float
    checkout_to_purchase_rate: float
    overall_conversion_rate: float


# ============================================================================
# Merchant Dashboard Services
# ============================================================================

class MerchantDashboardService:
    """Service for merchant KPI calculations."""

    @staticmethod
    def get_merchant_kpis(store_id: int, cache_ttl: int = 300) -> MerchantKPI:
        """
        Calculate merchant KPIs for a store.

        Args:
            store_id: Store ID
            cache_ttl: Cache time-to-live in seconds

        Returns:
            MerchantKPI dataclass with current metrics
        """
        cache_key = f"merchant_kpis:{store_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = today_start - timedelta(seconds=1)
        yesterday_start = yesterday_end.replace(hour=0, minute=0, second=0, microsecond=0)

        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        # Revenue today
        orders_today = Order.objects.filter(
            store_id=store_id,
            created_at__gte=today_start,
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        )
        revenue_today = orders_today.aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'), output_field=DecimalField())
        )['total']

        # Orders today count
        orders_today_count = orders_today.count()

        # 7-day and 30-day metrics
        orders_7d = Order.objects.filter(
            store_id=store_id,
            created_at__gte=seven_days_ago,
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        )
        revenue_7d = orders_7d.aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'), output_field=DecimalField())
        )['total']

        orders_30d = Order.objects.filter(
            store_id=store_id,
            created_at__gte=thirty_days_ago,
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        )
        revenue_30d = orders_30d.aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'), output_field=DecimalField())
        )['total']

        # Conversion rate (checkout started vs completed)
        checkout_started = Event.objects.filter(
            tenant_id=store_id,
            event_name='checkout_started',
            occurred_at__gte=today_start
        ).values('session_key_hash').distinct().count()

        purchase_completed = Event.objects.filter(
            tenant_id=store_id,
            event_name='purchase_completed',
            occurred_at__gte=today_start
        ).values('session_key_hash').distinct().count()

        conversion_rate = (
            (purchase_completed / checkout_started * 100)
            if checkout_started > 0 else 0.0
        )

        # Low stock products (< 10 units)
        low_stock = ProductVariant.objects.filter(
            product__store_id=store_id,
            stock__lt=10
        ).values('product__id', 'product__name', 'stock').order_by('stock')[:10]

        low_stock_products = [
            {
                'product_id': item['product__id'],
                'name': item['product__name'],
                'stock': item['stock']
            }
            for item in low_stock
        ]

        # Average order value
        avg_order_7d = orders_7d.aggregate(
            avg=Coalesce(Avg('total_amount'), Decimal('0.00'), output_field=DecimalField())
        )['avg']

        # Cart abandonment rate
        carts_total = Cart.objects.filter(
            store_id=store_id,
            created_at__gte=seven_days_ago
        ).count()

        carts_converted = Cart.objects.filter(
            store_id=store_id,
            created_at__gte=seven_days_ago,
            converted_at__isnull=False
        ).count()

        cart_abandonment_rate = (
            ((carts_total - carts_converted) / carts_total * 100)
            if carts_total > 0 else 0.0
        )

        kpi = MerchantKPI(
            revenue_today=revenue_today,
            orders_today=orders_today_count,
            conversion_rate=conversion_rate,
            low_stock_products=low_stock_products,
            revenue_7d=revenue_7d,
            revenue_30d=revenue_30d,
            orders_7d=orders_7d.count(),
            orders_30d=orders_30d.count(),
            avg_order_value=avg_order_7d,
            cart_abandonment_rate=cart_abandonment_rate,
            timestamp=now
        )

        cache.set(cache_key, kpi, cache_ttl)
        return kpi


# ============================================================================
# Revenue Chart Services
# ============================================================================

class RevenueChartService:
    """Service for revenue chart data."""

    @staticmethod
    def get_revenue_chart(store_id: int, days: int = 7, cache_ttl: int = 300) -> RevenueChart:
        """
        Get revenue chart data.

        Args:
            store_id: Store ID
            days: Number of days (7 or 30)
            cache_ttl: Cache TTL in seconds

        Returns:
            RevenueChart with data points
        """
        if days not in [7, 30]:
            days = 7

        cache_key = f"revenue_chart:{store_id}:{days}d"
        cached = cache.get(cache_key)
        if cached:
            return cached

        now = timezone.now()
        period_start = now - timedelta(days=days)

        # Aggregate by date
        orders = Order.objects.filter(
            store_id=store_id,
            created_at__gte=period_start,
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).annotate(
            order_date=TruncDate('created_at')
        ).values('order_date').annotate(
            daily_revenue=Coalesce(Sum('total_amount'), Decimal('0.00'), output_field=DecimalField()),
            order_count=Count('id'),
            avg_order_value=Coalesce(Avg('total_amount'), Decimal('0.00'), output_field=DecimalField())
        ).order_by('order_date')

        # Create data points
        points = [
            RevenuePoint(
                date=order['order_date'].isoformat(),
                revenue=order['daily_revenue'],
                orders=order['order_count'],
                avg_order_value=order['avg_order_value']
            )
            for order in orders
        ]

        # Calculate totals
        total_revenue = sum(p.revenue for p in points)
        total_orders = sum(p.orders for p in points)
        avg_daily_revenue = (
            total_revenue / days if days > 0 else Decimal('0.00')
        )

        chart = RevenueChart(
            period=f"{days}d",
            points=points,
            total_revenue=total_revenue,
            total_orders=total_orders,
            avg_daily_revenue=avg_daily_revenue,
            timestamp=now
        )

        cache.set(cache_key, chart, cache_ttl)
        return chart


# ============================================================================
# Admin Executive Dashboard Services
# ============================================================================

class AdminExecutiveDashboardService:
    """Service for admin executive dashboard metrics."""

    @staticmethod
    def get_admin_kpis(cache_ttl: int = 600) -> AdminKPI:
        """
        Get platform-wide KPIs.

        Args:
            cache_ttl: Cache TTL in seconds

        Returns:
            AdminKPI with platform metrics
        """
        cache_key = "admin_executive_kpis"
        cached = cache.get(cache_key)
        if cached:
            return cached

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # GMV - Gross Merchandise Volume (all orders)
        gmv = Order.objects.filter(
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'), output_field=DecimalField())
        )['total']

        # MRR - Monthly Recurring Revenue
        from apps.subscriptions.models import PaymentTransaction
        mrr = PaymentTransaction.objects.filter(
            created_at__gte=thirty_days_ago,
            status__in=['completed', 'paid']
        ).aggregate(
            total=Coalesce(Sum('amount'), Decimal('0.00'), output_field=DecimalField())
        )['total']

        # Active stores (stores with orders in last 30 days)
        from apps.stores.models import Store
        active_stores = Store.objects.filter(
            orders__created_at__gte=thirty_days_ago
        ).distinct().count()

        total_stores = Store.objects.count()
        inactive_stores = total_stores - active_stores
        churn_rate = (
            (inactive_stores / total_stores * 100) if total_stores > 0 else 0.0
        )

        # Total customers
        from apps.accounts.models import User
        total_customers = User.objects.filter(is_customer=True).count()

        # Average order value
        avg_order_value = Order.objects.filter(
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).aggregate(
            avg=Coalesce(Avg('total_amount'), Decimal('0.00'), output_field=DecimalField())
        )['avg']

        # Conversion rate platform-wide
        platform_views = Event.objects.filter(
            event_name='product_view'
        ).values('actor_id_hash').distinct().count()

        platform_purchases = Event.objects.filter(
            event_name='purchase_completed'
        ).values('actor_id_hash').distinct().count()

        conversion_rate = (
            (platform_purchases / platform_views * 100)
            if platform_views > 0 else 0.0
        )

        # Top products by revenue
        top_products = OrderItem.objects.filter(
            order__created_at__gte=thirty_days_ago
        ).values(
            'product__id', 'product__name'
        ).annotate(
            total_revenue=Coalesce(Sum('total_amount'), Decimal('0.00'), output_field=DecimalField()),
            quantity_sold=Sum('quantity')
        ).order_by('-total_revenue')[:5]

        top_products_list = [
            {
                'product_id': item['product__id'],
                'name': item['product__name'],
                'revenue': item['total_revenue'],
                'quantity_sold': item['quantity_sold']
            }
            for item in top_products
        ]

        # Top merchants by revenue
        top_merchants = Order.objects.filter(
            created_at__gte=thirty_days_ago,
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_PAID]
        ).values(
            'store__id', 'store__name'
        ).annotate(
            total_revenue=Coalesce(Sum('total_amount'), Decimal('0.00'), output_field=DecimalField()),
            order_count=Count('id')
        ).order_by('-total_revenue')[:5]

        top_merchants_list = [
            {
                'store_id': item['store__id'],
                'name': item['store__name'],
                'revenue': item['total_revenue'],
                'order_count': item['order_count']
            }
            for item in top_merchants
        ]

        # Payment success rate
        from apps.payments.models import PaymentAttempt
        total_payments = PaymentAttempt.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()

        successful_payments = PaymentAttempt.objects.filter(
            created_at__gte=thirty_days_ago,
            status=PaymentAttempt.STATUS_PAID
        ).count()

        payment_success_rate = (
            (successful_payments / total_payments * 100)
            if total_payments > 0 else 0.0
        )

        admin_kpi = AdminKPI(
            gmv=gmv,
            mrr=mrr,
            active_stores=active_stores,
            churn_rate=churn_rate,
            total_customers=total_customers,
            avg_order_value=avg_order_value,
            conversion_rate=conversion_rate,
            top_products=top_products_list,
            top_merchants=top_merchants_list,
            payment_success_rate=payment_success_rate,
            timestamp=now
        )

        cache.set(cache_key, admin_kpi, cache_ttl)
        return admin_kpi


# ============================================================================
# Event Tracking & Funnel Analysis
# ============================================================================

class EventTrackingService:
    """Service for event tracking and analysis."""

    @staticmethod
    def track_product_view(store_id: int, product_id: int, user_id: int | None = None,
                          session_key: str | None = None) -> None:
        """Track product view event."""
        from apps.analytics.application.track_event import safe_track_event
        from apps.analytics.domain.types import EventDTO

        event = EventDTO(
            event_name='product_view',
            actor_type='CUSTOMER' if user_id else 'ANON',
            actor_id=str(user_id) if user_id else None,
            session_key=session_key,
            object_type='PRODUCT',
            object_id=str(product_id),
            properties={'store_id': store_id},
        )
        safe_track_event(tenant_id=store_id, event=event)

    @staticmethod
    def track_add_to_cart(store_id: int, product_id: int, variant_id: int | None = None,
                         quantity: int = 1, user_id: int | None = None,
                         session_key: str | None = None) -> None:
        """Track add to cart event."""
        from apps.analytics.application.track_event import safe_track_event
        from apps.analytics.domain.types import EventDTO

        event = EventDTO(
            event_name='add_to_cart',
            actor_type='CUSTOMER' if user_id else 'ANON',
            actor_id=str(user_id) if user_id else None,
            session_key=session_key,
            object_type='PRODUCT',
            object_id=str(product_id),
            properties={
                'store_id': store_id,
                'variant_id': variant_id,
                'quantity': quantity
            },
        )
        safe_track_event(tenant_id=store_id, event=event)

    @staticmethod
    def track_checkout_started(store_id: int, cart_id: int, user_id: int | None = None,
                              session_key: str | None = None, item_count: int = 0,
                              cart_value: Decimal | None = None) -> None:
        """Track checkout started event."""
        from apps.analytics.application.track_event import safe_track_event
        from apps.analytics.domain.types import EventDTO

        event = EventDTO(
            event_name='checkout_started',
            actor_type='CUSTOMER' if user_id else 'ANON',
            actor_id=str(user_id) if user_id else None,
            session_key=session_key,
            object_type='CART',
            object_id=str(cart_id),
            properties={
                'store_id': store_id,
                'item_count': item_count,
                'cart_value': str(cart_value) if cart_value else None
            },
        )
        safe_track_event(tenant_id=store_id, event=event)

    @staticmethod
    def track_purchase_completed(store_id: int, order_id: int, user_id: int | None = None,
                                session_key: str | None = None, order_value: Decimal | None = None,
                                item_count: int = 0) -> None:
        """Track purchase completed event."""
        from apps.analytics.application.track_event import safe_track_event
        from apps.analytics.domain.types import EventDTO

        event = EventDTO(
            event_name='purchase_completed',
            actor_type='CUSTOMER' if user_id else 'ANON',
            actor_id=str(user_id) if user_id else None,
            session_key=session_key,
            object_type='ORDER',
            object_id=str(order_id),
            properties={
                'store_id': store_id,
                'order_value': str(order_value) if order_value else None,
                'item_count': item_count
            },
        )
        safe_track_event(tenant_id=store_id, event=event)


class FunnelAnalysisService:
    """Service for conversion funnel analysis."""

    @staticmethod
    def get_conversion_funnel(store_id: int, days: int = 7,
                             cache_ttl: int = 300) -> EventFunnel:
        """
        Get conversion funnel for a store.

        Args:
            store_id: Store ID
            days: Number of days to analyze
            cache_ttl: Cache TTL in seconds

        Returns:
            EventFunnel with conversion rates
        """
        cache_key = f"funnel:{store_id}:{days}d"
        cached = cache.get(cache_key)
        if cached:
            return cached

        now = timezone.now()
        period_start = now - timedelta(days=days)

        # Get unique sessions/users for each event
        events = Event.objects.filter(
            tenant_id=store_id,
            occurred_at__gte=period_start
        )

        product_views = events.filter(
            event_name='product_view'
        ).values('session_key_hash', 'actor_id_hash').distinct().count()

        add_to_cart = events.filter(
            event_name='add_to_cart'
        ).values('session_key_hash', 'actor_id_hash').distinct().count()

        checkout_started = events.filter(
            event_name='checkout_started'
        ).values('session_key_hash', 'actor_id_hash').distinct().count()

        purchase_completed = events.filter(
            event_name='purchase_completed'
        ).values('session_key_hash', 'actor_id_hash').distinct().count()

        # Calculate rates
        view_to_cart_rate = (
            (add_to_cart / product_views * 100)
            if product_views > 0 else 0.0
        )

        cart_to_checkout_rate = (
            (checkout_started / add_to_cart * 100)
            if add_to_cart > 0 else 0.0
        )

        checkout_to_purchase_rate = (
            (purchase_completed / checkout_started * 100)
            if checkout_started > 0 else 0.0
        )

        overall_conversion_rate = (
            (purchase_completed / product_views * 100)
            if product_views > 0 else 0.0
        )

        funnel = EventFunnel(
            product_views=product_views,
            add_to_cart=add_to_cart,
            checkout_started=checkout_started,
            purchase_completed=purchase_completed,
            view_to_cart_rate=view_to_cart_rate,
            cart_to_checkout_rate=cart_to_checkout_rate,
            checkout_to_purchase_rate=checkout_to_purchase_rate,
            overall_conversion_rate=overall_conversion_rate
        )

        cache.set(cache_key, funnel, cache_ttl)
        return funnel
