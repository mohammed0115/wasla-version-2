"""
Tenant Isolation Hardening - Quick Start Guide

This document shows practical examples of how to integration the hardened
tenant isolation layer into your models and views.
"""

# ============================================================================
# STEP 1: Update Models to Use TenantProtectedModel
# ============================================================================

"""
BEFORE (Current - File: apps/stores/models.py):

```python
from django.db import models
from apps.tenants.managers import TenantManager

class Store(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='stores'
    )
    slug = models.SlugField(max_length=100)
    name = models.CharField(max_length=200)
    
    objects = TenantManager()
    
    def __str__(self):
        return self.name
```

AFTER (Hardened):

```python
from django.db import models
from apps.tenants.querysets import TenantManager, TenantProtectedModel

class Store(TenantProtectedModel, models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='stores'
    )
    slug = models.SlugField(max_length=100)
    name = models.CharField(max_length=200)
    
    objects = TenantManager()
    
    # Explicitly mark tenant field for isolation
    TENANT_FIELD = 'tenant'
    
    def __str__(self):
        return self.name
    
    class Meta:
        # Add index for efficient scoped queries
        indexes = [
            models.Index(fields=['tenant', 'slug']),
            models.Index(fields=['tenant', 'is_active']),  # if is_active field exists
        ]
```

Changes:
1. Inherit from TenantProtectedModel
2. Update objects manager to new TenantManager
3. Add TENANT_FIELD = 'tenant' (or appropriate field name)
4. Add indexes for (tenant, other_field) combinations
"""


# ============================================================================
# STEP 2: Update Views to Enforce Tenant Scoping
# ============================================================================

"""
BEFORE (Vulnerable):

```python
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view
from apps.stores.models import Store

@api_view(['GET'])
def get_store_details(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    # VULNERABILITY: Anyone can access any store!
    return JsonResponse({
        'id': store.id,
        'name': store.name,
        'slug': store.slug,
    })

def list_stores_dashboard(request):
    # VULNERABILITY: Shows all stores, not just user's
    stores = Store.objects.all()
    return render(request, 'dashboard.html', {
        'stores': stores
    })
```

AFTER (Hardened):

```python
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, Http404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.stores.models import Store
from apps.tenants.querysets import get_object_for_tenant

@api_view(['GET'])
def get_store_details(request, store_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response(
            {'error': 'Tenant context required'},
            status=403
        )
    
    # SECURED: Can only access stores in their tenant
    store = get_object_for_tenant(Store, tenant, id=store_id)
    if not store:
        return Response({'error': 'Not found'}, status=404)
    
    return Response({
        'id': store.id,
        'name': store.name,
        'slug': store.slug,
    })

def list_stores_dashboard(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        raise Http404('Store context required')
    
    # SECURED: Can only access stores in their tenant
    stores = Store.objects.for_tenant(tenant).all()
    return render(request, 'dashboard.html', {
        'stores': stores
    })
```

Pattern:
1. Extract tenant from request
2. Validate tenant exists
3. Use .for_tenant(tenant) or get_object_for_tenant()
4. Handle missing results appropriately
"""


# ============================================================================
# STEP 3: Secure Admin Operations
# ============================================================================

"""
# In Django admin (apps/stores/admin.py)

BEFORE:

```python
from django.contrib import admin
from apps.stores.models import Store

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    
    def get_queryset(self, request):
        # VULNERABILITY: Superadmin can see all stores
        return super().get_queryset(request)
```

AFTER:

```python
from django.contrib import admin
from apps.stores.models import Store

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'tenant', 'created_at')
    
    def get_queryset(self, request):
        qs = Store.objects.unscoped_for_migration()
        
        if request.user.is_superuser:
            return qs
        
        # Limit staff to their own tenant
        if hasattr(request.user, 'tenant'):
            qs = qs.for_tenant(request.user.tenant)
        
        return qs
    
    def save_model(self, request, obj, form, change):
        # Ensure admin can't change tenant
        if not change:  # Creating
            if hasattr(request.user, 'tenant'):
                obj.tenant = request.user.tenant
        
        super().save_model(request, obj, form, change)
```
"""


# ============================================================================
# STEP 4: Secure Bulk Operations
# ============================================================================

"""
BEFORE (Vulnerable):

```python
def bulk_activate_stores(store_ids):
    # VULNERABILITY: No tenant validation
    Store.objects.filter(id__in=store_ids).update(is_active=True)
```

AFTER (Hardened):

```python
from apps.tenants.querysets import get_object_for_tenant

def bulk_activate_stores(tenant, store_ids):
    # SECURED: Validates tenant for each store
    stores = Store.objects.for_tenant(tenant).filter(id__in=store_ids)
    
    # Verify all stores belong to tenant (count check)
    if stores.count() != len(store_ids):
        raise ValueError("Some stores don't belong to this tenant")
    
    stores.update(is_active=True)

# Or with explicit validation:
def bulk_update_store_names(tenant, updates):
    # updates = {store_id: new_name, ...}
    
    for store_id, new_name in updates.items():
        store = get_object_for_tenant(Store, tenant, id=store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found in tenant")
        
        store.name = new_name
        store.save()
```
"""


# ============================================================================
# STEP 5: Secure API Serializers
# ============================================================================

"""
from rest_framework import serializers
from apps.stores.models import Store

# BEFORE (Vulnerable):
class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['id', 'name', 'slug']
    
    def create(self, validated_data):
        # VULNERABILITY: No tenant assignment
        return Store.objects.create(**validated_data)

# AFTER (Hardened):
class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['id', 'name', 'slug']
    
    def create(self, validated_data):
        # SECURED: Assigns tenant from context
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError(
                'Tenant context required'
            )
        
        return Store.objects.create(
            tenant=tenant,
            **validated_data
        )

# In view:
@api_view(['POST'])
def create_store(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({'error': 'Tenant required'}, status=403)
    
    serializer = StoreSerializer(
        data=request.data,
        context={'tenant': tenant}
    )
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)
"""


# ============================================================================
# STEP 6: Secure Signals and Hooks
# ============================================================================

"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.stores.models import Store

# BEFORE (Vulnerable):
@receiver(post_save, sender=Store)
def on_store_created(sender, instance, created, **kwargs):
    if created:
        # VULNERABILITY: Could trigger wrong logic if tenant is None
        send_welcome_email(instance.name)

# AFTER (Hardened):
@receiver(post_save, sender=Store)
def on_store_created(sender, instance, created, **kwargs):
    if created:
        # SECURED: Validate tenant before processing
        if not instance.tenant_id:
            logger.error(
                f"Store created without tenant: {instance.id}"
            )
            return
        
        # Safe to use tenant-scoped operations
        send_welcome_email_for_tenant(instance.tenant, instance.name)
"""


# ============================================================================
# STEP 7: Test Your Hardening
# ============================================================================

"""
Create test file: tests/test_store_isolation.py

```python
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.tenants.models import Tenant
from apps.stores.models import Store
from django.contrib.auth import get_user_model

User = get_user_model()

class StoreIsolationTests(TestCase):
    def setUp(self):
        self.tenant1 = Tenant.objects.create(slug='t1', name='T1')
        self.tenant2 = Tenant.objects.create(slug='t2', name='T2')
        
        self.user = User.objects.create_user('user', password='pass')
        
        self.store1 = Store.objects.create(
            tenant=self.tenant1,
            slug='s1',
            name='Store 1',
            owner=self.user
        )
        self.store2 = Store.objects.create(
            tenant=self.tenant2,
            slug='s2',
            name='Store 2',
            owner=self.user
        )
    
    def test_unscoped_query_fails(self):
        with self.assertRaises(ValidationError):
            Store.objects.all().count()
    
    def test_scoped_query_works(self):
        stores = Store.objects.for_tenant(self.tenant1)
        self.assertEqual(stores.count(), 1)
        self.assertEqual(stores.first().id, self.store1.id)
    
    def test_cross_tenant_isolation(self):
        stores = Store.objects.for_tenant(self.tenant1)
        self.assertFalse(stores.filter(id=self.store2.id).exists())
    
    def test_save_without_tenant_fails(self):
        store = Store(slug='invalid', name='Invalid')
        with self.assertRaises(ValidationError):
            store.save()
```

Run tests:
  python manage.py test tests.test_store_isolation
"""


# ============================================================================
# STEP 8: Migration Checklist
# ============================================================================

"""
For each model:

□ Add TenantProtectedModel to base classes
□ Update manager to new TenantManager
□ Add TENANT_FIELD = 'field_name'
□ Add database indexes for tenant+key combinations
□ Update all views to call .for_tenant()
□ Update all serializers to use context['tenant']
□ Update all signals to validate tenant
□ Update admin class to enforce tenant scoping
□ Add isolation tests
□ Test with multiple tenants
□ Performance test with indexes

Models to migrate:
Priority 1: Store, Order, Subscription
Priority 2: Customer, Product, Cart, Checkout
Priority 3: Review, Analytics, Notification
Priority 4: Webhook, Settlement, Payment
Priority 5: Supporting models
"""


# ============================================================================
# STEP 9: Monitoring Integration
# ============================================================================

"""
Add logging handler to settings.py:

import logging

# Monitor validation errors
validation_logger = logging.getLogger('tenant.validation')

# In your error handler:
try:
    stores = Store.objects.filter(name='test')
except ValidationError as e:
    validation_logger.warning(
        f"Unscoped query prevented: {e}",
        extra={
            'user_id': request.user.id,
            'path': request.path,
            'ip': request.META.get('REMOTE_ADDR'),
        }
    )

# Create dashboard to monitor:
# - Count of ValidationError by model
# - Count of 403 Forbidden responses
# - Count of missing tenant context
# - Superadmin bypass usage
"""


# ============================================================================
# STEP 10: Rollout Plan
# ============================================================================

"""
Week 1: Foundation
□ Deploy querysets.py and security_middleware.py
□ Update Django settings
□ Deploy tests_tenant_isolation.py
□ Run test suite (expect failures)

Week 2: Core Models
□ Update Store model
□ Update Order model
□ Update Subscription model
□ Update views and serializers for these
□ Test in staging
□ Deploy behind feature flag

Week 3: High-Risk Models
□ Update Customer, Product, Cart, Checkout
□ Update all related views
□ Test thoroughly
□ Deploy

Week 4: Verification
□ Monitor logs for issues
□ Review 403 responses
□ Performance testing
□ Security audit

Ongoing:
□ Update remaining models
□ Migrate support code
□ Audit new code for violations
□ Train developers on patterns
"""
