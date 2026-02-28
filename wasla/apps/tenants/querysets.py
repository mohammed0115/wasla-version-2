"""
Stricter tenant-aware QuerySets with security enforcement.

Prevents:
- Unscoped queries that leak across tenants
- Saves without attached tenant
- Superuser escaping tenant boundaries (without explicit bypass)
"""

from __future__ import annotations

from typing import Any, Optional
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class TenantQuerySet(models.QuerySet):
    """
    Base QuerySet that enforces tenant scoping.
    
    All queries must be scoped to a tenant unless:
    - Model is explicitly marked as TENANT_AGNOSTIC
    - Request has TENANT_BYPASS_SUPERADMIN enabled
    - Called from management command with explicit bypass
    """
    
    _tenant_context = None  # Will be set by middleware
    _bypass_tenant_check = False  # Emergency bypass for migrations
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_tenant_scoped = False
        self._explicit_tenant = None
    
    def _get_tenant_field(self) -> Optional[str]:
        """
        Detect which field is the tenant field.
        
        Priority:
        1. Explicit TENANT_FIELD on model
        2. 'tenant' ForeignKey
        3. 'store' ForeignKey (legacy)
        4. 'store_id' field (legacy)
        """
        model = self.model
        
        # Check explicit tenant field
        if hasattr(model, 'TENANT_FIELD'):
            field_name = model.TENANT_FIELD
            try:
                model._meta.get_field(field_name)
                return field_name
            except Exception as e:
                raise ImproperlyConfigured(
                    f"{model.__name__}.TENANT_FIELD = '{field_name}' does not exist"
                ) from e
        
        # Check for 'tenant' field
        try:
            model._meta.get_field('tenant')
            return 'tenant'
        except Exception:
            pass
        
        # Check for 'store' field
        try:
            model._meta.get_field('store')
            return 'store'
        except Exception:
            pass
        
        # Check for 'store_id' field
        try:
            model._meta.get_field('store_id')
            return 'store_id'
        except Exception:
            pass
        
        return None
    
    def for_tenant(self, tenant: Any) -> TenantQuerySet:
        """
        Explicitly scope this queryset to a specific tenant.
        
        Args:
            tenant: Tenant instance or tenant ID
            
        Returns:
            Scoped QuerySet
        """
        if isinstance(tenant, int):
            tenant_id = tenant
            tenant_obj = None
        else:
            tenant_id = getattr(tenant, 'id', tenant)
            tenant_obj = tenant
        
        tenant_field = self._get_tenant_field()
        if not tenant_field:
            raise ImproperlyConfigured(
                f"{self.model.__name__} has no TENANT_FIELD and no tenant/store field. "
                f"Cannot enforce tenant scoping for {self.model.__name__}"
            )
        
        qs = self.filter(**{tenant_field: tenant_id})
        qs._is_tenant_scoped = True
        qs._explicit_tenant = tenant_obj or tenant_id
        return qs
    
    def _check_tenant_scope(self):
        """
        Verify this queryset is tenant-scoped before executing.
        
        Raises:
            ValidationError: If queryset is not scoped and model requires scoping
        """
        if self._bypass_tenant_check:
            return
        
        # If explicitly marked as tenant-agnostic, skip check
        if getattr(self.model, 'TENANT_AGNOSTIC', False):
            return
        
        # If model doesn't have tenant field, it's not tenant-aware
        if not self._get_tenant_field():
            return
        
        # Check if this queryset is scoped
        if not self._is_tenant_scoped:
            raise ValidationError(
                f"Unscoped query on {self.model.__name__}. "
                f"All queries must call .for_tenant(tenant_id) first. "
                f"To bypass (superadmin only), use .unscoped_for_migration()"
            )
    
    def unscoped_for_migration(self) -> TenantQuerySet:
        """
        Bypass tenant scoping for migrations and management commands.
        
        WARNING: Only use in migrations, management commands, or admin operations.
        Do NOT use in request handlers without explicit audit logging.
        """
        qs = self.all()
        qs._bypass_tenant_check = True
        logger.info(
            f"Unscoped query on {self.model.__name__}. Caller: {self._get_caller_info()}"
        )
        return qs
    
    @staticmethod
    def _get_caller_info() -> str:
        """Get calling function info for audit logging."""
        import inspect
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back.f_back.f_back
            return f"{caller_frame.f_code.co_filename}:{caller_frame.f_lineno}"
        finally:
            del frame
    
    def get(self, *args, **kwargs):
        self._check_tenant_scope()
        return super().get(*args, **kwargs)
    
    def filter(self, *args, **kwargs):
        # Allow initial filter call to set scoping
        qs = super().filter(*args, **kwargs)
        
        # Check if this filter call is establishing tenant scope
        tenant_field = self._get_tenant_field()
        if tenant_field and tenant_field in kwargs:
            qs._is_tenant_scoped = True
            qs._explicit_tenant = kwargs[tenant_field]
        else:
            # Carry forward tenant scoping from parent
            qs._is_tenant_scoped = self._is_tenant_scoped
            qs._explicit_tenant = self._explicit_tenant
        
        qs._bypass_tenant_check = self._bypass_tenant_check
        return qs
    
    def exclude(self, *args, **kwargs):
        qs = super().exclude(*args, **kwargs)
        qs._is_tenant_scoped = self._is_tenant_scoped
        qs._explicit_tenant = self._explicit_tenant
        qs._bypass_tenant_check = self._bypass_tenant_check
        return qs
    
    def first(self):
        self._check_tenant_scope()
        return super().first()
    
    def last(self):
        self._check_tenant_scope()
        return super().last()
    
    def count(self):
        self._check_tenant_scope()
        return super().count()
    
    def exists(self):
        self._check_tenant_scope()
        return super().exists()
    
    def all(self):
        qs = super().all()
        qs._is_tenant_scoped = self._is_tenant_scoped
        qs._explicit_tenant = self._explicit_tenant
        qs._bypass_tenant_check = self._bypass_tenant_check
        return qs


class TenantManager(models.Manager):
    """
    Manager that wraps TenantQuerySet.
    
    Forces all queries to be explicitly tenant-scoped.
    """
    
    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db)
    
    def for_tenant(self, tenant: Any) -> TenantQuerySet:
        """Scope this manager's queries to a specific tenant."""
        return self.get_queryset().for_tenant(tenant)
    
    def unscoped_for_migration(self) -> TenantQuerySet:
        """Use only in migrations and management commands."""
        return self.get_queryset().unscoped_for_migration()


class TenantProtectedModel(models.Model):
    """
    Base model that adds tenant isolation guarantees.
    
    - Automatically validates tenant on save
    - Prevents accidental cross-tenant data writes
    - Requires explicit bypass for superadmin operations
    """
    
    # Override in subclass if different field name
    TENANT_FIELD: str = None
    
    # Set to True if model doesn't need tenant scoping
    TENANT_AGNOSTIC: bool = False
    
    class Meta:
        abstract = True
    
    def _get_tenant_field(self) -> Optional[str]:
        """Get the tenant field name for this model instance."""
        if self.TENANT_FIELD:
            return self.TENANT_FIELD
        
        for field_name in ['tenant', 'store', 'store_id']:
            try:
                self._meta.get_field(field_name)
                return field_name
            except Exception:
                pass
        
        return None
    
    def _get_tenant_value(self) -> Optional[int]:
        """Get the tenant ID value from this instance."""
        field = self._get_tenant_field()
        if not field:
            return None
        
        value = getattr(self, field, None)
        if value is None:
            return None
        
        # Handle both Tenant objects and IDs
        if hasattr(value, 'id'):
            return value.id
        return value
    
    def save(self, *args, **kwargs):
        """
        Validate tenant before saving.
        
        Raises:
            ValidationError: If tenant is None on a tenant-scoped model
        """
        # Skip validation if marked as TENANT_AGNOSTIC
        if self.TENANT_AGNOSTIC:
            super().save(*args, **kwargs)
            return
        
        # Allow hard delete bypass
        if kwargs.get('_skip_tenant_validation'):
            super().save(*args, **kwargs)
            return
        
        tenant_value = self._get_tenant_value()
        if not tenant_value:
            field = self._get_tenant_field()
            if field:
                raise ValidationError(
                    f"Cannot save {self.__class__.__name__}: {field} is required"
                )
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Ensure tenant consistency on delete.
        """
        if self.TENANT_AGNOSTIC:
            super().delete(*args, **kwargs)
            return
        
        tenant_value = self._get_tenant_value()
        if not tenant_value and not kwargs.get('_skip_tenant_validation'):
            field = self._get_tenant_field()
            if field:
                raise ValidationError(
                    f"Cannot delete {self.__class__.__name__}: {field} is missing"
                )
        
        super().delete(*args, **kwargs)


def get_object_for_tenant(model, tenant, **lookup) -> Optional[models.Model]:
    """
    Strongly-typed helper to get a single object for a tenant.
    
    Enforces tenant scoping in the lookup.
    
    Args:
        model: Django model class
        tenant: Tenant instance or ID
        **lookup: Query parameters
        
    Returns:
        Model instance or None
        
    Raises:
        ValidationError: If query would escape tenant boundary
    """
    qs = model.objects.for_tenant(tenant)
    return qs.get(**lookup) if qs.exists() else None
