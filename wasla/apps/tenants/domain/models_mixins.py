"""
Tenant-scoped model mixins for multi-tenant isolation.

Provides base classes for models that need tenant isolation and query scoping.
"""

from django.db import models
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from apps.tenants.models import Tenant


class TenantScopedModel(models.Model):
    """
    Base model for tenant-scoped data.
    
    Ensures models are properly associated with a tenant/store context
    and can be queried with appropriate scoping.
    
    Usage:
        class MyModel(TenantScopedModel):
            name = models.CharField(max_length=100)
            
            class Meta:
                db_table = 'my_model'
    """
    
    # Default tenant field name - override in subclass if needed
    TENANT_FIELD = "tenant_id"

    class Meta:
        abstract = True
    
    def get_tenant_id(self) -> Optional[int]:
        """
        Get the tenant ID for this model instance.
        
        Returns:
            The tenant_id value if the field exists, None otherwise.
        """
        if hasattr(self, self.TENANT_FIELD):
            return getattr(self, self.TENANT_FIELD, None)
        return None
    
    def set_tenant(self, tenant: Any) -> None:
        """
        Set the tenant for this model instance.
        
        Args:
            tenant: Can be a Tenant instance or a tenant_id integer.
                   If Tenant instance, extracts the id. If int, sets directly.
        """
        if tenant is None:
            setattr(self, self.TENANT_FIELD, None)
        elif isinstance(tenant, int):
            setattr(self, self.TENANT_FIELD, tenant)
        else:
            # Assume it's a Tenant instance with an id
            tenant_id = getattr(tenant, "id", None)
            if tenant_id is not None:
                setattr(self, self.TENANT_FIELD, tenant_id)
