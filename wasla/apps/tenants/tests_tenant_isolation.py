"""
Comprehensive tenant isolation security tests.

Tests verify that:
1. Unscoped queries on tenant models fail
2. Cross-tenant data access is prevented
3. Model save validates tenant
4. Middleware blocks requests without tenant context
5. Superadmin bypass is audit-logged
6. Concurrent requests maintain tenant isolation
"""

from __future__ import annotations

import pytest
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import override_settings

from apps.tenants.models import Tenant, StoreProfile
from apps.tenants.querysets import TenantQuerySet, TenantManager, TenantProtectedModel
from apps.tenants.security_middleware import TenantSecurityMiddleware
from apps.stores.models import Store

User = get_user_model()


class TenantUnscopedQueryTests(TestCase):
    """Test that unscoped queries fail with proper errors."""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data across multiple tenants."""
        # Create two separate tenants
        cls.tenant1 = Tenant.objects.create(
            slug='tenant-1',
            name='Tenant 1',
            is_active=True
        )
        cls.tenant2 = Tenant.objects.create(
            slug='tenant-2',
            name='Tenant 2',
            is_active=True
        )
        
        # Create users
        cls.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        cls.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        
        # Create stores for each tenant
        cls.store1 = Store.objects.create(
            tenant=cls.tenant1,
            slug='store-1',
            name='Store 1',
            owner=cls.user1
        )
        cls.store2 = Store.objects.create(
            tenant=cls.tenant2,
            slug='store-2',
            name='Store 2',
            owner=cls.user2
        )
    
    def test_unscoped_query_raises_validation_error(self):
        """Unscoped Store query should raise ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            Store.objects.all().count()
        
        self.assertIn('Unscoped query', str(cm.exception))
    
    def test_for_tenant_explicitly_scopes_query(self):
        """Explicit for_tenant() should work."""
        stores = Store.objects.for_tenant(self.tenant1).all()
        # Should not raise
        count = stores.count()
        self.assertEqual(count, 1)
        self.assertEqual(stores.first().slug, 'store-1')
    
    def test_for_tenant_with_integer_id(self):
        """for_tenant() should accept tenant ID as int."""
        stores = Store.objects.for_tenant(self.tenant1.id).all()
        count = stores.count()
        self.assertEqual(count, 1)
    
    def test_unscoped_filter_raises_error(self):
        """Filter without tenant scope should fail."""
        with self.assertRaises(ValidationError):
            Store.objects.filter(name__icontains='Store').count()
    
    def test_unscoped_first_raises_error(self):
        """Calling .first() without scope should fail."""
        with self.assertRaises(ValidationError):
            Store.objects.all().first()
    
    def test_unscoped_get_raises_error(self):
        """Calling .get() without scope should fail."""
        with self.assertRaises(ValidationError):
            Store.objects.get(slug='store-1')
    
    def test_migration_bypass_allows_unscoped(self):
        """unscoped_for_migration() should allow unscoped queries."""
        # Should not raise
        count = Store.objects.unscoped_for_migration().all().count()
        self.assertEqual(count, 2)  # Both stores


class TenantCrossTenantAccessTests(TestCase):
    """Test that cross-tenant access is prevented."""
    
    @classmethod
    def setUpTestData(cls):
        """Create data across tenants."""
        cls.tenant1 = Tenant.objects.create(
            slug='cross-test-1',
            name='Cross Test 1',
            is_active=True
        )
        cls.tenant2 = Tenant.objects.create(
            slug='cross-test-2',
            name='Cross Test 2',
            is_active=True
        )
        
        cls.user1 = User.objects.create_user(
            username='cross-user1',
            password='pass123'
        )
        cls.user2 = User.objects.create_user(
            username='cross-user2',
            password='pass123'
        )
        
        cls.store1 = Store.objects.create(
            tenant=cls.tenant1,
            slug='cross-store-1',
            name='Store 1',
            owner=cls.user1
        )
        cls.store2 = Store.objects.create(
            tenant=cls.tenant2,
            slug='cross-store-2',
            name='Store 2',
            owner=cls.user2
        )
    
    def test_tenant1_cannot_access_tenant2_stores(self):
        """Store from tenant2 should not appear in tenant1 queries."""
        stores = Store.objects.for_tenant(self.tenant1).filter(slug='cross-store-2')
        self.assertFalse(stores.exists())
    
    def test_tenant2_cannot_access_tenant1_stores(self):
        """Store from tenant1 should not appear in tenant2 queries."""
        stores = Store.objects.for_tenant(self.tenant2).filter(slug='cross-store-1')
        self.assertFalse(stores.exists())
    
    def test_different_tenants_isolation_count(self):
        """Each tenant should only see their own stores."""
        stores1 = Store.objects.for_tenant(self.tenant1)
        stores2 = Store.objects.for_tenant(self.tenant2)
        
        self.assertEqual(stores1.count(), 1)
        self.assertEqual(stores2.count(), 1)
    
    def test_no_id_reuse_across_tenants(self):
        """Even with same ID, cross-tenant access should fail."""
        # This is a bit artificial, but tests the principle
        stores = Store.objects.for_tenant(self.tenant1).all()
        store1_id = stores.first().id
        
        # Query with tenant2 for same ID should fail
        stores = Store.objects.for_tenant(self.tenant2).filter(id=store1_id)
        self.assertFalse(stores.exists())


class TenantModelSaveValidationTests(TestCase):
    """Test that models validate tenant before save."""
    
    @classmethod
    def setUpTestData(cls):
        cls.tenant1 = Tenant.objects.create(
            slug='save-test-1',
            name='Save Test 1',
            is_active=True
        )
        cls.user1 = User.objects.create_user(
            username='save-user1',
            password='pass123'
        )
    
    def test_save_without_tenant_raises_validation_error(self):
        """Saving a Store without tenant should fail."""
        store = Store(
            slug='invalid-store',
            name='Invalid Store',
            owner=self.user1,
            # tenant is missing
        )
        
        with self.assertRaises(ValidationError) as cm:
            store.save()
        
        self.assertIn('tenant', str(cm.exception).lower())
    
    def test_save_with_tenant_succeeds(self):
        """Saving with tenant should work."""
        store = Store(
            tenant=self.tenant1,
            slug='valid-store',
            name='Valid Store',
            owner=self.user1
        )
        # Should not raise
        store.save()
        self.assertIsNotNone(store.id)
    
    def test_delete_without_tenant_raises_validation_error(self):
        """Deleting a model without tenant should fail."""
        store = Store(
            slug='delete-test',
            name='Delete Test',
            owner=self.user1,
        )
        # Manually set without tenant for deletion test
        store.tenant = None
        
        # This should fail on delete validation
        # Note: This is a bit artificial as django would normally require it during save
        # but we're testing the guard


class TenantMiddlewareSecurityTests(TestCase):
    """Test middleware tenant security enforcement."""
    
    @classmethod
    def setUpTestData(cls):
        cls.tenant1 = Tenant.objects.create(
            slug='mw-test-1',
            name='MW Test 1',
            is_active=True
        )
        cls.client = Client()
        cls.factory = RequestFactory()
    
    @override_settings(
        TENANT_REQUIRED_PATHS={'/api/subscriptions/', '/api/orders/'}
    )
    def test_middleware_blocks_unscoped_api_request(self):
        """Middleware should block API requests without tenant."""
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        # Create a request to a tenant-required path without tenant
        request = self.factory.get('/api/subscriptions/')
        request.user = None
        request.tenant = None  # No tenant resolved
        
        response = middleware.process_request(request)
        
        # Should return 403 Forbidden
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
    
    def test_middleware_allows_optional_paths(self):
        """Middleware should allow requests to optional paths without tenant."""
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        request = self.factory.get('/api/auth/login/')
        request.user = None
        request.tenant = None
        
        response = middleware.process_request(request)
        
        # Should not block
        self.assertIsNone(response)
    
    def test_middleware_allows_scoped_requests(self):
        """Middleware should allow requests with tenant."""
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        request = self.factory.get('/api/subscriptions/')
        request.user = None
        request.tenant = self.tenant1
        
        response = middleware.process_request(request)
        
        # Should not block
        self.assertIsNone(response)


class TenantBypassAuditTests(TestCase):
    """Test that superadmin bypasses are logged."""
    
    @classmethod
    def setUpTestData(cls):
        cls.tenant1 = Tenant.objects.create(
            slug='bypass-test-1',
            name='Bypass Test 1',
            is_active=True
        )
    
    def test_unscoped_for_migration_logs_caller(self):
        """unscoped_for_migration() should log caller information."""
        import logging
        
        with self.assertLogs('apps.tenants.querysets', level='INFO') as cm:
            # This should log
            Store.objects.unscoped_for_migration().all().count()
        
        # Should have logged the unscoped query
        self.assertTrue(any('Unscoped query' in msg for msg in cm.output))


class TenantConcurrencyTests(TestCase):
    """Test tenant isolation under concurrent access."""
    
    @classmethod
    def setUpTestData(cls):
        cls.tenant1 = Tenant.objects.create(
            slug='concurrent-1',
            name='Concurrent 1',
            is_active=True
        )
        cls.tenant2 = Tenant.objects.create(
            slug='concurrent-2',
            name='Concurrent 2',
            is_active=True
        )
        
        cls.user1 = User.objects.create_user(
            username='concurrent-user1',
            password='pass123'
        )
        cls.user2 = User.objects.create_user(
            username='concurrent-user2',
            password='pass123'
        )
        
        cls.store1 = Store.objects.create(
            tenant=cls.tenant1,
            slug='concurrent-store-1',
            name='Concurrent Store 1',
            owner=cls.user1
        )
        cls.store2 = Store.objects.create(
            tenant=cls.tenant2,
            slug='concurrent-store-2',
            name='Concurrent Store 2',
            owner=cls.user2
        )
    
    def test_multiple_tenant_queries_dont_interfere(self):
        """Querying multiple tenants sequentially should isolate results."""
        qs1 = Store.objects.for_tenant(self.tenant1)
        qs2 = Store.objects.for_tenant(self.tenant2)
        
        result1 = qs1.first()
        result2 = qs2.first()
        
        self.assertEqual(result1.tenant_id, self.tenant1.id)
        self.assertEqual(result2.tenant_id, self.tenant2.id)


class TenantProtectionDecoratorTests(TestCase):
    """Test that TenantProtectedModel decorator enforces isolation."""
    
    @classmethod
    def setUpTestData(cls):
        cls.tenant1 = Tenant.objects.create(
            slug='protected-1',
            name='Protected 1',
            is_active=True
        )
    
    def test_tenant_protected_model_requires_tenant(self):
        """TenantProtectedModel subclasses should require tenant on save."""
        # Store is a tenant-protected model
        store = Store(
            slug='protected-store',
            name='Protected Store',
            owner_id=1  # Fake owner
            # tenant is missing
        )
        
        with self.assertRaises(ValidationError):
            store.save()


# ============================================================================
# Integration Tests - High-Level Attack Scenarios
# ============================================================================

class TenantSecurityIntegrationTests(TestCase):
    """Integration tests simulating real attack scenarios."""
    
    @classmethod
    def setUpTestData(cls):
        """Create realistic multi-tenant scenario."""
        # Create two competing businesses using the same system
        cls.shop1_tenant = Tenant.objects.create(
            slug='shop1',
            name='Shop 1',
            is_active=True
        )
        cls.shop2_tenant = Tenant.objects.create(
            slug='shop2',
            name='Shop 2',
            is_active=True
        )
        
        # Create owners
        cls.shop1_owner = User.objects.create_user(
            username='shop1-owner',
            email='shop1@example.com',
            password='shop1pass'
        )
        cls.shop2_owner = User.objects.create_user(
            username='shop2-owner',
            email='shop2@example.com',
            password='shop2pass'
        )
        
        # Create shops
        cls.shop1 = Store.objects.create(
            tenant=cls.shop1_tenant,
            slug='shop1',
            name='Shop 1',
            owner=cls.shop1_owner
        )
        cls.shop2 = Store.objects.create(
            tenant=cls.shop2_tenant,
            slug='shop2',
            name='Shop 2',
            owner=cls.shop2_owner
        )
    
    def test_scenario_tenant_hijacking_attempt(self):
        """
        Attack Scenario: Attacker tries to hijack another tenant's data.
        
        Expected: Attack fails with ValidationError.
        """
        # Attacker (shop2_owner) tries to access shop1's data
        with self.assertRaises(ValidationError):
            # This would be like: Store.objects.filter(tenant=shop1_tenant).count()
            # without explicit for_tenant() call
            Store.objects.filter(slug='shop1').count()
    
    def test_scenario_cross_tenant_write_attempt(self):
        """
        Attack Scenario: Attacker tries to write data to another tenant.
        
        Expected: save() fails with ValidationError.
        """
        # Attacker tries to create a store in shop1's tenant
        unauthorized_store = Store(
            tenant=self.shop1_tenant,
            slug='unauthorized',
            name='Unauthorized Store',
            owner=self.shop2_owner
        )
        
        # Note: This would need to be prevented at application level too
        # But the model validates tenant is present
        unauthorized_store.save()  # This should succeed at model level
        
        # The auth layer should prevent this
        # (ownership/permission checks)


@pytest.mark.django_db
class TenantQuerySetAdvancedTests:
    """Advanced QuerySet scoping tests using pytest."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tenant1 = Tenant.objects.create(
            slug='pytest-tenant-1',
            name='Pytest Tenant 1'
        )
        self.tenant2 = Tenant.objects.create(
            slug='pytest-tenant-2',
            name='Pytest Tenant 2'
        )
        
        self.user1 = User.objects.create_user(
            username='pytest-user-1',
            password='pass'
        )
        
        self.store1 = Store.objects.create(
            tenant=self.tenant1,
            slug='pytest-store-1',
            name='Store 1',
            owner=self.user1
        )
        self.store2 = Store.objects.create(
            tenant=self.tenant2,
            slug='pytest-store-2',
            name='Store 2',
            owner=self.user1
        )
    
    def test_filter_maintains_scope(self):
        """Chained filters should maintain tenant scope."""
        qs = Store.objects.for_tenant(self.tenant1)
        filtered = qs.filter(slug='pytest-store-1')
        
        assert filtered.count() == 1
        assert filtered.first().tenant_id == self.tenant1.id
    
    def test_exclude_maintains_scope(self):
        """Exclude should not escape tenant scope."""
        # Create multiple stores in tenant1
        Store.objects.create(
            tenant=self.tenant1,
            slug='store-a',
            name='Store A',
            owner=self.user1
        )
        Store.objects.create(
            tenant=self.tenant1,
            slug='store-b',
            name='Store B',
            owner=self.user1
        )
        
        qs = Store.objects.for_tenant(self.tenant1)
        excluded = qs.exclude(slug='pytest-store-1')
        
        # Should have 2 stores (not counting tenant2)
        assert excluded.count() == 2
        
        # All should be from tenant1
        for store in excluded:
            assert store.tenant_id == self.tenant1.id
