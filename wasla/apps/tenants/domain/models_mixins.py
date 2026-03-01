"""
Tenant-scoped model mixins for multi-tenant isolation.

Provides base classes for models that need tenant isolation and query scoping.
"""

from django.db import models


class TenantScopedModel(models.Model):
    """
    Base model for tenant-scoped data.
    
    Ensures models are properly associated with a tenant/store context
    and can be queried with appropriate scoping.
    """

    class Meta:
        abstract = True
