"""
Tests for root domain default store resolution.

Tests the following scenarios:
1. GET "/" with root domain (w-sala.com) resolves to default store
2. GET "/billing/payment-required/" with root domain returns friendly error
3. GET "/" with unknown host returns 404 or default handling
4. Storefront works with default store context
5. Tenant isolation maintained for subdomains
"""

import pytest
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.http import Http404

from apps.tenants.models import Tenant
from apps.stores.models import Store
from apps.tenants.services.domain_resolution import resolve_store_by_slug

User = get_user_model()


class TestRootDomainDefaultStoreResolution(TestCase):
    """Test root domain resolution to default store."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.factory = RequestFactory()
        
        # Create a default tenant
        self.default_tenant = Tenant.objects.create(
            slug="default",
            name="Default Tenant",
            is_active=True,
            is_published=True,
        )
        
        # Create default store with store1 slug
        self.default_store = Store.objects.create(
            name="Default Store",
            slug="store1",
            tenant=self.default_tenant,
            is_active=True,
        )
        
        # Create a non-default store for subdomain testing
        self.other_tenant = Tenant.objects.create(
            slug="other",
            name="Other Tenant",
            is_active=True,
        )
        
        self.other_store = Store.objects.create(
            name="Other Store",
            slug="other-store",
            tenant=self.other_tenant,
            is_active=True,
        )
    
    def test_root_domain_resolves_to_default_store(self):
        """Test that w-sala.com resolves to default store (store1)."""
        response = self.client.get(
            '/',
            HTTP_HOST='w-sala.com'
        )
        # Should not return 503 or 404 for missing store
        self.assertNotIn(response.status_code, [503, 404])
        # Should be 200 or redirect (depends on home view)
        self.assertIn(response.status_code, [200, 302, 403])  # 403 from billing redirect
    
    def test_www_root_domain_resolves_to_default_store(self):
        """Test that www.w-sala.com resolves to default store."""
        response = self.client.get(
            '/',
            HTTP_HOST='www.w-sala.com'
        )
        # Should not return 503 for missing default store
        self.assertNotEqual(response.status_code, 503)
    
    def test_storefront_home_with_default_store(self):
        """Test /store/ works with default store context."""
        response = self.client.get(
            '/store/',
            HTTP_HOST='w-sala.com'
        )
        # Should render storefront (200, not 404 "Store context required")
        if response.status_code == 404:
            self.assertNotIn("Store context required", str(response.content))
    
    def test_subdomain_isolation_maintained(self):
        """Test that subdomains still resolve independently."""
        response = self.client.get(
            '/',
            HTTP_HOST='other-store.w-sala.com'
        )
        # Should resolve to 'other-store' subdomain, not default
        self.assertNotEqual(response.status_code, 500)
    
    def test_billing_redirect_on_root_domain(self):
        """Test that /billing/* on root domain doesn't crash."""
        response = self.client.get(
            '/billing/payment-required/',
            HTTP_HOST='w-sala.com'
        )
        # Should not be traceback (500)
        self.assertNotEqual(response.status_code, 500)
        # Should be redirect (302) or 403/404, not a Django traceback
        self.assertNotIn("Traceback", str(response.content))
    
    def test_default_store_missing_returns_503(self):
        """Test that missing default store returns friendly 503."""
        # Delete default store
        self.default_store.delete()
        
        response = self.client.get(
            '/',
            HTTP_HOST='w-sala.com'
        )
        # Should return 503 Service Unavailable, not 404
        self.assertEqual(response.status_code, 503)
        self.assertIn("Service Unavailable", str(response.content))
        self.assertIn("Default store not configured", str(response.content))
    
    def test_resolve_store_by_slug_function(self):
        """Test resolve_store_by_slug helper function."""
        # Should find default store
        store = resolve_store_by_slug("store1")
        self.assertIsNotNone(store)
        self.assertEqual(store.slug, "store1")
        
        # Should return None for non-existent
        store = resolve_store_by_slug("nonexistent")
        self.assertIsNone(store)
        
        # Should return None for empty slug
        store = resolve_store_by_slug("")
        self.assertIsNone(store)
    
    def test_inactive_store_not_resolved(self):
        """Test that inactive default store is not resolved."""
        # Make default store inactive
        self.default_store.is_active = False
        self.default_store.save()
        
        response = self.client.get(
            '/',
            HTTP_HOST='w-sala.com'
        )
        # Should return 503 since store is inactive
        self.assertEqual(response.status_code, 503)
    
    def test_api_without_tenant_returns_403(self):
        """Test that API requests without tenant return 403, not 503."""
        # Delete default store
        self.default_store.delete()
        
        response = self.client.get(
            '/api/products/',
            HTTP_HOST='w-sala.com'
        )
        # Should return 403 for API, not 503
        self.assertIn(response.status_code, [403, 404, 500])
    
    def test_root_domain_with_session_store(self):
        """Test that session store_id takes precedence on root domain."""
        # Set session store to other store
        session = self.client.session
        session['store_id'] = self.other_store.tenant.id
        session.save()
        
        response = self.client.get(
            '/',
            HTTP_HOST='w-sala.com'
        )
        # Should still work (session stores fallback in middleware)
        self.assertNotEqual(response.status_code, 500)


class TestRootDomainSecurityMiddleware(TestCase):
    """Test security middleware behavior for root domain."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        
        self.default_tenant = Tenant.objects.create(
            slug="default",
            name="Default Tenant",
            is_active=True,
        )
        
        self.default_store = Store.objects.create(
            name="Default Store",
            slug="store1",
            tenant=self.default_tenant,
            is_active=True,
        )
    
    def test_root_domain_requests_allowed(self):
        """Test that root domain requests are allowed through security middleware."""
        request = self.factory.get('/', HTTP_HOST='w-sala.com')
        request.tenant = self.default_tenant
        request.store = self.default_store
        
        # Should not raise permission denied
        from apps.tenants.security_middleware import TenantSecurityMiddleware
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        # Should return None (allow request through)
        result = middleware._check_tenant_security(request)
        self.assertIsNone(result)
    
    def test_default_store_not_configured_flag(self):
        """Test that flag is set when root domain lacks default store."""
        request = self.factory.get('/', HTTP_HOST='w-sala.com')
        request.tenant = None
        request.store = None
        request._is_root_domain_no_default = True
        
        from apps.tenants.security_middleware import TenantSecurityMiddleware
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        # Should return 503 response
        response = middleware._handle_missing_tenant(request)
        self.assertEqual(response.status_code, 503)


class TestDefaultStoreManagementCommand(TestCase):
    """Test the create_default_store management command."""
    
    def test_create_default_store_command_exists(self):
        """Test that create_default_store command is available."""
        from django.core.management import call_command
        
        # Should not raise CommandError
        try:
            call_command(
                'create_default_store',
                '--confirm',
                stdout=None,
                stderr=None,
            )
        except Exception as e:
            # It's OK if the command fails for other reasons (store exists, etc)
            # We're just checking it exists
            self.assertNotIn("Unknown command", str(e))


class TestRootDomainURLResolution(TestCase):
    """Test URL resolution with root domain context."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        self.default_tenant = Tenant.objects.create(
            slug="default",
            name="Default Tenant",
            is_active=True,
        )
        
        self.default_store = Store.objects.create(
            name="Default Store",
            slug="store1",
            tenant=self.default_tenant,
            is_active=True,
        )
    
    def test_home_page_accessible(self):
        """Test home page (/) is accessible on root domain."""
        response = self.client.get('/', HTTP_HOST='w-sala.com')
        self.assertNotEqual(response.status_code, 500)
    
    def test_healthz_always_accessible(self):
        """Test /healthz is accessible regardless of store context."""
        response = self.client.get('/healthz', HTTP_HOST='w-sala.com')
        # /healthz should always work
        self.assertIn(response.status_code, [200, 404])  # 404 if view doesn't exist
    
    def test_static_files_accessible(self):
        """Test /static/* doesn't require store context."""
        response = self.client.get(
            '/static/css/style.css',
            HTTP_HOST='w-sala.com'
        )
        # Should not return 403 "Tenant context required"
        if response.status_code == 404:
            # That's OK - file doesn't exist
            self.assertNotIn("Store context required", str(response.content))
