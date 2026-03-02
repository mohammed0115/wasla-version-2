"""
Subscription Limits Service - Enforces plan limits at operation level.

Financial Integrity Level: HIGH

This service:
- Enforces product creation limit
- Enforces staff user limit
- Enforces orders/month limit
- Returns friendly UX errors when limit exceeded
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q

from apps.subscriptions.models import StoreSubscription
from apps.subscriptions.services.subscription_service import SubscriptionService
from apps.catalog.models import Product
from apps.accounts.models import User  # or your staff user model
from apps.orders.models import Order

logger = logging.getLogger("wasla.subscriptions")


class SubscriptionLimitExceededError(Exception):
    """Raised when subscription limit is exceeded."""
    
    def __init__(self, limit_type: str, current: int, limit: int, message: str = ""):
        self.limit_type = limit_type
        self.current = current
        self.limit = limit
        self.message = message or f"Limit exceeded: {current}/{limit}"
        super().__init__(self.message)


class SubscriptionLimitService:
    """
    Validates operations against subscription plan limits.
    
    Usage:
        service = SubscriptionLimitService()
        
        # Check product creation limit
        try:
            service.check_product_limit(store_id=5)
        except SubscriptionLimitExceededError as e:
            # Show friendly error: "You've reached the 100 product limit on your plan"
            pass
        
        # Check staff user limit
        try:
            service.check_staff_user_limit(store_id=5)
        except SubscriptionLimitExceededError as e:
            # Show friendly error
            pass
        
        # Check monthly orders limit
        try:
            service.check_monthly_orders_limit(store_id=5)
        except SubscriptionLimitExceededError as e:
            # Show friendly error
            pass
    """
    
    def get_active_subscription(self, store_id: int) -> Optional[StoreSubscription]:
        """Get active subscription for store."""
        return SubscriptionService.get_active_subscription(store_id)
    
    def get_plan_limits(self, store_id: int) -> Dict[str, Optional[int]]:
        """Get all limits for store's plan."""
        subscription = self.get_active_subscription(store_id)
        
        if not subscription:
            # No subscription = unlimited
            return {
                "max_products": None,
                "max_staff_users": None,
                "max_orders_monthly": None,
            }
        
        plan = subscription.plan
        return {
            "max_products": plan.max_products,
            "max_staff_users": plan.max_staff_users,
            "max_orders_monthly": plan.max_orders_monthly,
        }
    
    def check_product_limit(self, store_id: int) -> Dict[str, Any]:
        """
        Check if store can create new product.
        
        Returns:
            {
                "allowed": bool,
                "current": int,
                "limit": int or None,
                "message": str,
            }
        
        Raises:
            SubscriptionLimitExceededError if limit exceeded
        """
        limits = self.get_plan_limits(store_id)
        max_products = limits["max_products"]
        
        if max_products is None:
            # Unlimited
            return {
                "allowed": True,
                "current": 0,
                "limit": None,
                "message": "",
            }
        
        # Count existing products
        current_count = Product.objects.filter(
            store_id=store_id
        ).count()
        
        if current_count >= max_products:
            raise SubscriptionLimitExceededError(
                limit_type="products",
                current=current_count,
                limit=max_products,
                message=f"You've reached the {max_products} product limit on your plan. "
                        f"Please upgrade to add more products.",
            )
        
        return {
            "allowed": True,
            "current": current_count,
            "limit": max_products,
            "message": f"{current_count}/{max_products} products",
        }
    
    def check_staff_user_limit(self, store_id: int) -> Dict[str, Any]:
        """
        Check if store can add new staff user.
        
        Returns / Raises like check_product_limit
        """
        limits = self.get_plan_limits(store_id)
        max_staff_users = limits["max_staff_users"]
        
        if max_staff_users is None:
            return {
                "allowed": True,
                "current": 0,
                "limit": None,
                "message": "",
            }
        
        # Count existing staff users (simplified - adjust based on your user model)
        from apps.accounts.models import StaffUser  # or your staff model
        current_count = StaffUser.objects.filter(
            store_id=store_id,
            is_active=True,
        ).count()
        
        if current_count >= max_staff_users:
            raise SubscriptionLimitExceededError(
                limit_type="staff_users",
                current=current_count,
                limit=max_staff_users,
                message=f"You've reached the {max_staff_users} staff user limit on your plan. "
                        f"Please upgrade to add more team members.",
            )
        
        return {
            "allowed": True,
            "current": current_count,
            "limit": max_staff_users,
            "message": f"{current_count}/{max_staff_users} staff users",
        }
    
    def check_monthly_orders_limit(self, store_id: int) -> Dict[str, Any]:
        """
        Check if store can process more orders this month.
        
        Returns / Raises like check_product_limit
        """
        limits = self.get_plan_limits(store_id)
        max_orders = limits["max_orders_monthly"]
        
        if max_orders is None:
            return {
                "allowed": True,
                "current": 0,
                "limit": None,
                "message": "",
            }
        
        # Count orders this month
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        current_count = Order.objects.filter(
            store_id=store_id,
            created_at__gte=month_start,
            created_at__lte=month_end,
        ).count()
        
        if current_count >= max_orders:
            raise SubscriptionLimitExceededError(
                limit_type="orders_monthly",
                current=current_count,
                limit=max_orders,
                message=f"You've reached the {max_orders} monthly orders limit on your plan. "
                        f"Please upgrade for higher limits.",
            )
        
        return {
            "allowed": True,
            "current": current_count,
            "limit": max_orders,
            "message": f"{current_count}/{max_orders} orders this month",
        }
    
    def get_subscription_summary(self, store_id: int) -> Dict[str, Any]:
        """Get complete subscription and usage summary."""
        subscription = self.get_active_subscription(store_id)
        
        if not subscription:
            return {
                "status": "no_subscription",
                "plan": None,
                "usage": {
                    "products": 0,
                    "staff_users": 0,
                    "orders_this_month": 0,
                },
                "limits": {
                    "max_products": None,
                    "max_staff_users": None,
                    "max_orders_monthly": None,
                },
            }
        
        plan = subscription.plan
        
        # Get current usage
        product_count = Product.objects.filter(store_id=store_id).count()
        
        from apps.accounts.models import StaffUser
        staff_count = StaffUser.objects.filter(
            store_id=store_id,
            is_active=True,
        ).count()
        
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        orders_count = Order.objects.filter(
            store_id=store_id,
            created_at__gte=month_start,
            created_at__lte=month_end,
        ).count()
        
        return {
            "status": "active",
            "plan": plan.name,
            "plan_id": plan.id,
            "billing_cycle": plan.billing_cycle,
            "usage": {
                "products": product_count,
                "staff_users": staff_count,
                "orders_this_month": orders_count,
            },
            "limits": {
                "max_products": plan.max_products,
                "max_staff_users": plan.max_staff_users,
                "max_orders_monthly": plan.max_orders_monthly,
            },
            "subscription_start": subscription.start_date.isoformat(),
            "subscription_end": subscription.end_date.isoformat(),
        }
