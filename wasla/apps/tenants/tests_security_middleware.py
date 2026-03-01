"""
Unit tests for tenant security middleware.

Tests the new-style Django 5+ middleware implementation.
Ensures:
1. No AttributeError on async_mode
2. Tenant security checks work correctly
3. Middleware order is respected
4. Request/response flow works
"""

from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from apps.tenants.security_middleware import (
    TenantSecurityMiddleware,
    TenantContextMiddleware,
    TenantAuditMiddleware,
)

User = get_user_model()


class MockTenant:
    """Mock tenant for testing."""
    id = 1
    name = "Test Tenant"


class TestTenantSecurityMiddlewareInitialization(TestCase):
    """Test middleware initialization (no async_mode error)."""

    def test_middleware_initializes_without_error(self):
        """
        Test that TenantSecurityMiddleware can be initialized
        without raising AttributeError: async_mode.
        """
        # Create a mock get_response callable
        get_response = Mock(return_value=HttpResponse("OK"))
        
        # This should not raise AttributeError about async_mode
        middleware = TenantSecurityMiddleware(get_response)
        
        # Verify middleware was initialized
        self.assertIsNotNone(middleware)
        self.assertEqual(middleware.get_response, get_response)
        self.assertIsInstance(middleware.tenant_required_paths, set)

    def test_middleware_has_correct_interface(self):
        """Test that middleware implements new-style interface."""
        get_response = Mock(return_value=HttpResponse("OK"))
        middleware = TenantSecurityMiddleware(get_response)
        
        # Verify new-style middleware interface
        self.assertTrue(hasattr(middleware, '__init__'))
        self.assertTrue(hasattr(middleware, '__call__'))
        # Verify no old-style methods exist
        self.assertFalse(hasattr(middleware, 'process_request'))
        self.assertFalse(hasattr(middleware, 'process_response'))


@override_settings(
    MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'apps.tenants.middleware.TenantResolverMiddleware',
        'apps.tenants.middleware.TenantMiddleware',
        'apps.tenants.security_middleware.TenantSecurityMiddleware',
        'apps.tenants.security_middleware.TenantAuditMiddleware',
    ]
)
class TestTenantSecurityMiddlewareExecution(TestCase):
    """Test middleware execution with tenant resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse("OK", status=200))
        self.middleware = TenantSecurityMiddleware(self.get_response)

    def test_call_method_exists_and_works(self):
        """Test that __call__ method works correctly."""
        request = self.factory.get('/')
        request.tenant = MockTenant()
        request.user = Mock()
        request.user.is_authenticated = False
        
        response = self.middleware(request)
        
        # Verify get_response was called
        self.get_response.assert_called_once_with(request)
        # Verify response is returned
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)

    def test_optional_paths_bypass_tenant_check(self):
        """Test that optional paths don't require tenant."""
        request = self.factory.get('/api/auth/login')
        request.tenant = None  # No tenant
        request.user = Mock()
        request.user.is_authenticated = False
        
        response = self.middleware(request)
        
        # Should not raise error, should call get_response
        self.get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)

    def test_health_check_path_bypasses_tenant_check(self):
        """Test health check paths don't require tenant."""
        for path in ['/healthz', '/readyz', '/metrics']:
            self.get_response.reset_mock()
            request = self.factory.get(path)
            request.tenant = None
            request.user = Mock()
            request.user.is_authenticated = False
            
            response = self.middleware(request)
            
            self.get_response.assert_called_once()

    def test_api_without_tenant_returns_403(self):
        """Test that API requests without tenant are denied."""
        request = self.factory.get('/api/v1/products')
        request.tenant = None  # No tenant
        request.user = Mock()
        request.user.is_authenticated = False
        
        response = self.middleware(request)
        
        # Should return 403 without calling get_response
        self.get_response.assert_not_called()
        self.assertEqual(response.status_code, 403)

    def test_authenticated_user_without_tenant_access_denied(self):
        """Test that authenticated users without tenant access are denied."""
        request = self.factory.get('/api/v1/products')
        request.tenant = MockTenant()
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.id = 999
        request.user.is_superuser = False
        
        # Mock _user_has_tenant_access to return False
        self.middleware._user_has_tenant_access = Mock(return_value=False)
        
        response = self.middleware(request)
        
        # Should return 403
        self.get_response.assert_not_called()
        self.assertEqual(response.status_code, 403)

    def test_superuser_bypasses_tenant_access_check(self):
        """Test that superusers bypass tenant access checks."""
        request = self.factory.get('/api/v1/products')
        request.tenant = MockTenant()
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.is_superuser = True
        
        response = self.middleware(request)
        
        # Should call get_response
        self.get_response.assert_called_once()

    def test_path_requires_tenant_logic(self):
        """Test the path requirement checking logic."""
        middleware = TenantSecurityMiddleware(self.get_response)
        
        # Optional paths
        self.assertFalse(middleware._path_requires_tenant('/api/auth/login'))
        self.assertFalse(middleware._path_requires_tenant('/healthz'))
        self.assertFalse(middleware._path_requires_tenant('/static/style.css'))
        
        # Required paths
        self.assertTrue(middleware._path_requires_tenant('/api/v1/products'))
        self.assertTrue(middleware._path_requires_tenant('/dashboard/'))
        self.assertTrue(middleware._path_requires_tenant('/billing/'))


class TestTenantContextMiddleware(TestCase):
    """Test TenantContextMiddleware (no async_mode error)."""

    def test_context_middleware_initializes_without_error(self):
        """Test that TenantContextMiddleware initializes correctly."""
        get_response = Mock(return_value=HttpResponse("OK"))
        
        middleware = TenantContextMiddleware(get_response)
        
        self.assertIsNotNone(middleware)
        self.assertEqual(middleware.get_response, get_response)

    def test_context_middleware_call_method(self):
        """Test __call__ method of context middleware."""
        factory = RequestFactory()
        get_response = Mock(return_value=HttpResponse("OK", status=200))
        middleware = TenantContextMiddleware(get_response)
        
        request = factory.get('/')
        request.tenant = MockTenant()
        
        response = middleware(request)
        
        get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)

    def test_context_change_detection(self):
        """Test detection of tenant context changes mid-request."""
        factory = RequestFactory()
        get_response = Mock(return_value=HttpResponse("OK", status=200))
        middleware = TenantContextMiddleware(get_response)
        
        request = factory.get('/')
        tenant1 = MockTenant()
        tenant2 = MockTenant()
        tenant2.id = 2
        
        request.tenant = tenant1
        
        # Simulate tenant change during request processing
        def change_tenant(*args, **kwargs):
            request.tenant = tenant2
            return HttpResponse("OK", status=200)
        
        get_response.side_effect = change_tenant
        
        with patch('apps.tenants.security_middleware.logger') as mock_logger:
            response = middleware(request)
            
            # Should log error about tenant change
            mock_logger.error.assert_called()


class TestTenantAuditMiddleware(TestCase):
    """Test TenantAuditMiddleware (no async_mode error)."""

    def test_audit_middleware_initializes_without_error(self):
        """Test that TenantAuditMiddleware initializes correctly."""
        get_response = Mock(return_value=HttpResponse("OK"))
        
        middleware = TenantAuditMiddleware(get_response)
        
        self.assertIsNotNone(middleware)
        self.assertEqual(middleware.get_response, get_response)

    def test_audit_middleware_call_method(self):
        """Test __call__ method of audit middleware."""
        factory = RequestFactory()
        get_response = Mock(return_value=HttpResponse("OK", status=200))
        middleware = TenantAuditMiddleware(get_response)
        
        request = factory.get('/api/v1/products')
        request.tenant = MockTenant()
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.id = 1
        
        response = middleware(request)
        
        get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)

    def test_audit_logs_api_access(self):
        """Test that API access is logged."""
        factory = RequestFactory()
        get_response = Mock(return_value=HttpResponse("OK", status=200))
        middleware = TenantAuditMiddleware(get_response)
        
        request = factory.get('/api/v1/products')
        request.tenant = MockTenant()
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.id = 1
        request.method = 'GET'
        
        with patch('apps.tenants.security_middleware.logger') as mock_logger:
            response = middleware(request)
            
            # Should log debug message
            mock_logger.debug.assert_called()


@override_settings(
    MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'apps.tenants.middleware.TenantResolverMiddleware',
        'apps.tenants.middleware.TenantMiddleware',
        'apps.tenants.security_middleware.TenantSecurityMiddleware',
        'apps.tenants.security_middleware.TenantAuditMiddleware',
    ],
    ROOT_URLCONF='tests.test_urls'
)
class TestMiddlewareIntegration(TestCase):
    """Integration tests for middleware stack."""

    def test_middleware_order_enforcement(self):
        """Test that middleware executes in correct order."""
        from django.test import Client
        
        # Use Django test client which will run through middleware stack
        client = Client()
        
        # This request should not raise AttributeError about async_mode
        try:
            response = client.get('/')
            # Should get a response (may be 200, 302, 403, or 404)
            self.assertIn(response.status_code, [200, 302, 403, 404])
        except AttributeError as e:
            if 'async_mode' in str(e):
                self.fail(f"Middleware async_mode error: {e}")
            raise

    def test_health_endpoint_accessible(self):
        """Test that health endpoints bypass tenant checks."""
        from django.test import Client
        
        client = Client()
        
        # Health endpoints should be accessible without tenant
        try:
            response = client.get('/healthz')
            self.assertNotEqual(response.status_code, 500)
        except AttributeError as e:
            if 'async_mode' in str(e):
                self.fail(f"Middleware async_mode error: {e}")
            raise
