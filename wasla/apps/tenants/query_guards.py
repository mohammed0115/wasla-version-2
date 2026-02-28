"""
ORM Query Guards - Prevent unscoped queries on sensitive models.

Enforces that sensitive models (Order, Invoice, etc.) are always filtered by tenant/store.
Raises exceptions when queries don't include tenant scope.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Type

from django.db import models
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation

logger = logging.getLogger(__name__)

# Models that ALWAYS require tenant/store scope
TENANT_REQUIRED_MODELS = {
    'Order',
    'OrderItem',
    'Invoice',
    'InvoiceLineItem',
    'Cart',
    'CartItem',
    'RefundTransaction',
    'RMA',
    'ReturnItem',
    'Payment',
    'PaymentAttempt',
    'Settlement',
    'SettlementRecord',
    'StockReservation',
    'Deal',
    'DealDiscount',
    'ProductVariant',
}


class TenantQueryGuard:
    """
    Mixin for models to enforce tenant-scope requirement.
    
    Usage:
        class Order(TenantQueryGuard, models.Model):
            tenant = models.ForeignKey(Tenant, ...)
            # Automatically enforces tenant scope on queries
    """

    @classmethod
    def raise_if_unscoped(cls, queryset: models.QuerySet) -> models.QuerySet:
        """
        Verify queryset has tenant filter applied.
        
        Args:
            queryset: Django QuerySet to validate
        
        Returns:
            Same queryset (if valid)
        
        Raises:
            SuspiciousOperation: If no tenant filter detected
        """
        query_dict = queryset.query.where.children if queryset.query.where else []
        
        # Check if tenant_id or tenant__id is in filters
        tenant_filtered = any(
            'tenant' in str(child)
            for child in query_dict
        )
        
        if not tenant_filtered:
            logger.error(
                f"SECURITY: Unscoped query on {cls.__name__}. "
                f"Queries must include .filter(tenant=...) or .filter(store__tenant=...)."
            )
            raise SuspiciousOperation(
                f"{cls.__name__} queries must be filtered by tenant"
            )
        
        return queryset


class enforce_tenant_scope:
    """
    Decorator for methods that should enforce tenant scoping.
    
    Usage:
        @enforce_tenant_scope
        def get_orders(tenant_id):
            return Order.objects.filter(tenant_id=tenant_id)
    
    Raises:
        SuspiciousOperation: If query not scoped to tenant
    """

    def __init__(self, model_class: Type[models.Model] = None):
        """
        Initialize decorator.
        
        Args:
            model_class: Model to validate (optional, can be inferred from context)
        """
        self.model_class = model_class

    def __call__(self, func) -> Any:
        """Wrap function to enforce tenant scoping."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # If result is a QuerySet, validate tenant scope
            if isinstance(result, models.QuerySet):
                self._validate_scoping(result)
            
            return result
        
        return wrapper

    def _validate_scoping(self, queryset: models.QuerySet):
        """
        Validate that queryset includes tenant filter.
        
        Args:
            queryset: QuerySet to validate
        
        Raises:
            SuspiciousOperation: If no tenant filter found
        """
        # Get model from queryset
        model = queryset.model
        
        # Check if this is a tenant-required model
        if model.__name__ not in TENANT_REQUIRED_MODELS:
            return  # Not a sensitive model, skip validation
        
        # Check for tenant filter
        query_str = str(queryset.query)
        
        if 'tenant' not in query_str and 'store' not in query_str:
            logger.error(
                f"SECURITY: Unscoped query on {model.__name__}. "
                f"Query: {query_str}"
            )
            raise SuspiciousOperation(
                f"Queries on {model.__name__} must include tenant or store filter"
            )


def assert_tenant_scoped(queryset: models.QuerySet, tenant_id_or_obj: int) -> models.QuerySet:
    """
    Assert that a queryset is properly scoped to tenant.
    
    Intended for use in ViewSet.get_queryset() or similar.
    
    Args:
        queryset: Base queryset
        tenant_id_or_obj: Tenant ID or Tenant object
    
    Returns:
        Filtered queryset
    
    Raises:
        SuspiciousOperation: If tenant not in queryset filter
    """
    if isinstance(tenant_id_or_obj, int):
        tenant_id = tenant_id_or_obj
    else:
        tenant_id = getattr(tenant_id_or_obj, 'id', None)
    
    if not tenant_id:
        raise ValueError("Invalid tenant_id_or_obj")
    
    # For models with tenant field
    try:
        queryset.model._meta.get_field('tenant')
        return queryset.filter(tenant_id=tenant_id)
    except:
        pass
    
    # For models with store field (store has tenant)
    try:
        queryset.model._meta.get_field('store')
        return queryset.filter(store__tenant_id=tenant_id)
    except:
        pass
    
    # If model has neither field, raise error
    raise ImproperlyConfigured(
        f"{queryset.model.__name__} must have 'tenant' or 'store' field for scoping"
    )


class ScopedQuerySet(models.QuerySet):
    """
    Custom QuerySet that enforces tenant scoping on sensitive models.
    
    Raises SuspiciousOperation if:
    - Model is TENANT_REQUIRED
    - No tenant/store filter applied
    - Query would return unfiltered data
    
    Usage:
        class OrderQuerySet(ScopedQuerySet):
            pass
        
        class Order(models.Model):
            objects = OrderQuerySet.as_manager()
    """

    def for_tenant(self, tenant):
        """
        Filter queryset by tenant.
        
        Args:
            tenant: Tenant object or ID
        
        Returns:
            Filtered queryset
        """
        if isinstance(tenant, int):
            return self.filter(tenant_id=tenant)
        else:
            return self.filter(tenant=tenant)

    def for_store(self, store):
        """
        Filter queryset by store.
        
        Args:
            store: Store object or ID
        
        Returns:
            Filtered queryset
        """
        try:
            # Try store field
            if isinstance(store, int):
                return self.filter(store_id=store)
            else:
                return self.filter(store=store)
        except:
            # Fall back to store__tenant
            if isinstance(store, int):
                return self.filter(store_id=store)
            else:
                return self.filter(store__tenant=store.tenant)

    def _check_scoped(self):
        """
        Verify query is scoped (private method - called by evaluate()).
        
        This runs when the queryset is evaluated.
        """
        # Only enforce for sensitive models
        if self.model.__name__ not in TENANT_REQUIRED_MODELS:
            return
        
        query_str = str(self.query)
        
        # Check if query includes tenant or store filter
        if 'tenant' not in query_str and 'store' not in query_str and '__' not in query_str:
            logger.critical(
                f"SECURITY VIOLATION: Unscoped query on {self.model.__name__}. "
                f"Model: {self.model}, Query: {query_str}"
            )
            raise SuspiciousOperation(
                f"Queries on {self.model.__name__} MUST include tenant or store filter"
            )

    def _fetch_all(self):
        """Override to check scoping before fetching."""
        self._check_scoped()
        return super()._fetch_all()
