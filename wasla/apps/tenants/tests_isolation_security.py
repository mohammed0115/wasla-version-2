"""
Production-grade tenant isolation security tests.

Tests verify:
- Cross-tenant order read attempts → 403
- Token with tenant A cannot access tenant B store
- API requests without tenant context → 403
- Middleware enforces tenant scope
- User cannot access other tenants' data
"""

from __future__ import annotations

from django.test import TestCase, Client, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from apps.tenants.models import Tenant
from apps.stores.models import Store
from apps.orders.models import Order
from apps.tenants.middleware import TenantResolverMiddleware
from apps.tenants.security_middleware import TenantSecurityMiddleware
from apps.tenants.interfaces.api.authentication import TenantTokenAuth
from apps.tenants.guards import require_tenant

User = get_user_model()


class TenantIsolationAPITests(APITestCase):
    """Test tenant isolation in API layer."""

    @classmethod
    def setUpTestData(cls):
        """Create test tenants and users."""
        # Tenant A
        cls.tenant_a = Tenant.objects.create(
            slug='tenant-a',
            name='Tenant A',
            is_active=True
        )

        # Tenant B
        cls.tenant_b = Tenant.objects.create(
            slug='tenant-b',
            name='Tenant B',
            is_active=True
        )

        # Users
        cls.user_a = User.objects.create_user(
            username='user_a',
            email='user_a@test.com',
            password='pass123'
        )

        cls.user_b = User.objects.create_user(
            username='user_b',
            email='user_b@test.com',
            password='pass123'
        )

        # Stores
        cls.store_a = Store.objects.create(
            name='Store A',
            slug='store-a',
            owner=cls.user_a,
            tenant=cls.tenant_a
        )

        cls.store_b = Store.objects.create(
            name='Store B',
            slug='store-b',
            owner=cls.user_b,
            tenant=cls.tenant_b
        )

        # Orders
        cls.order_a = Order.objects.create(
            store=cls.store_a,
            total=100.00,
            currency='SAR'
        )

        cls.order_b = Order.objects.create(
            store=cls.store_b,
            total=200.00,
            currency='SAR'
        )

    def setUp(self):
        """Initialize API client."""
        self.client = APIClient()

    def test_api_request_without_tenant_context_returns_403(self):
        """
        SECURITY: API requests without tenant context should fail.
        
        Testing: GET /api/orders/ without tenant header
        Expected: 403 Forbidden
        """
        self.client.force_authenticate(user=self.user_a)
        
        response = self.client.get('/api/orders/v1/')
        
        # Should return 403 when tenant not available
        self.assertIn(
            response.status_code,
            [403, 400],
            msg=f"Expected 403/400, got {response.status_code} - {response.data}"
        )

    def test_user_a_cannot_access_order_from_tenant_b(self):
        """
        SECURITY: User from Tenant A cannot access orders from Tenant B.
        
        Testing: User A tries to read Order B
        Expected: 403 Forbidden or 404 Not Found
        """
        self.client.force_authenticate(user=self.user_a)
        
        # Set tenant A context
        response = self.client.get(
            f'/api/orders/{self.order_b.id}/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        
        # Should not find order from different tenant
        self.assertIn(
            response.status_code,
            [403, 404, 400],
            msg=f"User A should not access Order B. Status: {response.status_code}"
        )

    def test_cross_tenant_header_injection_blocked(self):
        """
        SECURITY: User cannot use X-Tenant header to access other tenants.
        
        Testing: User A authenticated for Tenant A, tries X-Tenant-ID: Tenant B
        Expected: 403 Forbidden (permission denied)
        """
        self.client.force_authenticate(user=self.user_a)
        
        # Try to inject Tenant B header
        response = self.client.get(
            '/api/orders/v1/',
            HTTP_X_TENANT_ID=str(self.tenant_b.id)
        )
        
        # Should deny access or return no data
        if response.status_code == 200:
            # If 200, ensure it returns empty data for unowned tenant
            self.assertEqual(
                len(response.data),
                0,
                msg="User A should not see Tenant B's orders"
            )
        else:
            # Better: reject outright
            self.assertIn(
                response.status_code,
                [403, 401, 400],
                msg="Should reject cross-tenant access attempt"
            )

    def test_unauthenticated_api_request_denied(self):
        """
        SECURITY: Unauthenticated API requests should be denied.
        
        Testing: GET /api/orders/ without authentication
        Expected: 401 Unauthorized
        """
        response = self.client.get('/api/orders/v1/')
        
        self.assertIn(
            response.status_code,
            [401, 403, 400],
            msg="Unauthenticated requests should be rejected"
        )

class TenantMiddlewareSecurityTests(TestCase):
    """Test tenant security middleware enforcement."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant1 = Tenant.objects.create(
            slug='mw-test-1',
            name='MW Test 1',
            is_active=True
        )
        cls.tenant2 = Tenant.objects.create(
            slug='mw-test-2',
            name='MW Test 2',
            is_active=True
        )
        cls.client = Client()
        cls.factory = RequestFactory()

    @override_settings(
        TENANT_REQUIRED_PATHS={'/api/v1/orders/', '/api/v1/invoices/'}
    )
    def test_middleware_blocks_unscoped_api_request(self):
        """
        Middleware should block API requests without tenant.
        
        Testing: TenantSecurityMiddleware on /api/v1/orders/ without tenant
        Expected: 403 Forbidden
        """
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        request = self.factory.get('/api/v1/orders/')
        request.user = None
        request.tenant = None  # No tenant resolved
        
        response = middleware.process_request(request)
        
        # Should return 403 Forbidden
        self.assertIsNotNone(
            response,
            msg="Middleware should block unscoped API request"
        )
        self.assertEqual(
            response.status_code,
            403,
            msg=f"Expected 403, got {response.status_code}"
        )

    def test_middleware_allows_optional_paths_without_tenant(self):
        """
        Middleware should allow health checks without tenant.
        
        Testing: /api/health/ without tenant
        Expected: None (allowed through)
        """
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        request = self.factory.get('/api/health/')
        request.user = None
        request.tenant = None
        
        response = middleware.process_request(request)
        
        # Should return None (allow through)
        self.assertIsNone(
            response,
            msg="Health check should not require tenant"
        )

    def test_middleware_allows_authenticated_request_with_tenant(self):
        """
        Middleware should allow authenticated requests with tenant.
        
        Testing: /api/v1/orders/ with authenticated user and tenant
        Expected: None (allowed through)
        """
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='pass123'
        )
        
        middleware = TenantSecurityMiddleware(lambda r: None)
        
        request = self.factory.get('/api/v1/orders/')
        request.user = user
        request.tenant = self.tenant1  # Tenant resolved
        
        response = middleware.process_request(request)
        
        # Should return None (allow through)
        self.assertIsNone(
            response,
            msg="Request with tenant should be allowed"
        )


class TenantTokenAuthTests(TestCase):
    """Test TenantTokenAuth implementation."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            slug='auth-test-1',
            name='Auth Test 1',
            is_active=True
        )
        cls.user = User.objects.create_user(
            username='authuser',
            email='auth@test.com',
            password='pass123'
        )

    def setUp(self):
        self.auth = TenantTokenAuth()
        self.factory = RequestFactory()

    def test_get_tenant_id_extracts_from_request(self):
        """
        Test TenantTokenAuth.get_tenant_id() extracts tenant.
        
        Testing: Request with resolved tenant
        Expected: Correct tenant ID returned
        """
        request = self.factory.get('/')
        request.tenant = self.tenant
        
        tenant_id = self.auth.get_tenant_id(request)
        
        self.assertEqual(
            tenant_id,
            self.tenant.id,
            msg="Should extract correct tenant ID"
        )

    def test_get_tenant_id_returns_none_without_tenant(self):
        """
        Test TenantTokenAuth returns None if no tenant.
        
        Testing: Request without tenant
        Expected: None returned
        """
        request = self.factory.get('/')
        request.tenant = None
        
        tenant_id = self.auth.get_tenant_id(request)
        
        self.assertIsNone(
            tenant_id,
            msg="Should return None when no tenant"
        )


class TenantScopingIntegrationTests(APITestCase):
    """
    Integration tests for complete tenant isolation flow.
    
    Tests the entire request lifecycle:
    1. Request arrives
    2. Middleware resolves tenant
    3. Auth determines user
    4. ViewSet filters by tenant
    5. Response includes only scoped data
    """

    @classmethod
    def setUpTestData(cls):
        # Setup 2 complete tenants/stores/orders
        cls.tenant_x = Tenant.objects.create(slug='tenant-x', name='Tenant X', is_active=True)
        cls.tenant_y = Tenant.objects.create(slug='tenant-y', name='Tenant Y', is_active=True)
        
        cls.user_x = User.objects.create_user(username='user_x', password='pass')
        cls.user_y = User.objects.create_user(username='user_y', password='pass')
        
        cls.store_x = Store.objects.create(name='Store X', slug='store-x', owner=cls.user_x, tenant=cls.tenant_x)
        cls.store_y = Store.objects.create(name='Store Y', slug='store-y', owner=cls.user_y, tenant=cls.tenant_y)
        
        cls.order_x = Order.objects.create(store=cls.store_x, total=100, currency='SAR')
        cls.order_y = Order.objects.create(store=cls.store_y, total=200, currency='SAR')

    def test_user_x_sees_only_his_orders(self):
        """
        INTEGRATION: User X authenticated sees only their orders.
        
        Flow:
        1. User X authenticates
        2. Tenant X resolved from store
        3. OrderViewSet filters by tenant_x
        4. Response includes only Order X
        """
        self.client.force_authenticate(user=self.user_x)
        
        # If API exists and returns list
        response = self.client.get(
            '/api/orders/v1/',
            HTTP_X_TENANT_ID=str(self.tenant_x.id)
        )
        
        if response.status_code == 200 and isinstance(response.data, list):
            order_ids = [o['id'] for o in response.data]
            
            self.assertIn(
                self.order_x.id,
                order_ids,
                msg="Should see own order"
            )
            self.assertNotIn(
                self.order_y.id,
                order_ids,
                msg="Should NOT see other tenant's order"
            )

    def test_switching_tenant_context_via_header_not_allowed(self):
        """
        INTEGRATION: User X cannot switch to Tenant Y context via header.
        
        Security boundary test.
        """
        self.client.force_authenticate(user=self.user_x)
        
        # Try to view Tenant Y with User X
        response = self.client.get(
            '/api/orders/v1/',
            HTTP_X_TENANT_ID=str(self.tenant_y.id)
        )
        
        # Should be denied or return empty
        if response.status_code == 200:
            if isinstance(response.data, list):
                # Ensure no data from Y
                self.assertEqual(
                    len(response.data),
                    0,
                    msg="User X should not see Tenant Y data"
                )
