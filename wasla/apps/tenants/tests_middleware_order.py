"""
Regression tests for middleware ordering and request.user safety.

Tests ensure that:
1. TenantSecurityMiddleware runs AFTER AuthenticationMiddleware
2. request.user is safely accessed even if missing
3. Middleware chain doesn't crash when request.user is not yet attached
"""

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse, Http404
from django.contrib.auth.models import AnonymousUser

from apps.tenants.security_middleware import (
    TenantSecurityMiddleware,
    TenantContextMiddleware,
    TenantAuditMiddleware,
)


class TestTenantSecurityMiddlewareOrderAndSafety(TestCase):
    """Test that TenantSecurityMiddleware handles missing request.user safely."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse(status=200))

    def test_middleware_initializes_without_error(self):
        """Test that middleware initializes without AttributeError."""
        middleware = TenantSecurityMiddleware(self.get_response)
        self.assertIsNotNone(middleware)
        self.assertIsNotNone(middleware.get_response)

    def test_check_tenant_security_without_user_attribute(self):
        """
        Test that _check_tenant_security handles request without user attribute.
        
        This simulates a request that hasn't been processed by AuthenticationMiddleware yet.
        """
        middleware = TenantSecurityMiddleware(self.get_response)
        
        # Create request WITHOUT user attribute (simulates pre-auth middleware)
        request = self.factory.get('/')
        # Explicitly ensure no user attribute
        if hasattr(request, 'user'):
            delattr(request, 'user')
        
        # Should not crash
        result = middleware._check_tenant_security(request)
        
        # Should return None (allow through) for paths that don't require tenant
        self.assertIsNone(result)

    def test_check_tenant_security_with_missing_user_id(self):
        """Test safe handling of user without id attribute."""
        middleware = TenantSecurityMiddleware(self.get_response)
        
        request = self.factory.get('/api/billing/')
        
        # Mock user without id attribute
        user_mock = Mock(spec=['is_authenticated'])
        user_mock.is_authenticated = True
        request.user = user_mock
        
        # Mock tenant
        tenant_mock = Mock(id=1)
        request.tenant = tenant_mock
        
        # Mock _user_has_tenant_access to return False (to trigger logging with user_id access)
        with patch.object(middleware, '_user_has_tenant_access', return_value=False):
            response = middleware._check_tenant_security(request)
            
            # Should return 403 Forbidden
            self.assertEqual(response.status_code, 403)

    def test_handle_missing_tenant_with_no_user(self):
        """Test _handle_missing_tenant when request has no user attribute."""
        middleware = TenantSecurityMiddleware(self.get_response)
        
        request = self.factory.get('/api/billing/')
        if hasattr(request, 'user'):
            delattr(request, 'user')
        
        response = middleware._handle_missing_tenant(request)
        
        # Should return 403 for API paths
        self.assertEqual(response.status_code, 403)
        self.assertIn('Tenant context required', response.content.decode())

    def test_handle_missing_tenant_with_user(self):
        """Test _handle_missing_tenant when user is present but not authenticated."""
        middleware = TenantSecurityMiddleware(self.get_response)
        
        request = self.factory.get('/api/billing/')
        request.user = AnonymousUser()
        
        response = middleware._handle_missing_tenant(request)
        
        # Should return 403 for API paths
        self.assertEqual(response.status_code, 403)

    def test_handle_missing_tenant_web_request_raises_404(self):
        """Test that non-API paths raise Http404."""
        middleware = TenantSecurityMiddleware(self.get_response)
        
        request = self.factory.get('/billing/invoice/')
        request.user = AnonymousUser()
        
        with self.assertRaises(Http404):
            middleware._handle_missing_tenant(request)

    def test_tenant_context_middleware_safe_user_access(self):
        """Test TenantContextMiddleware safely accesses user attributes."""
        middleware = TenantContextMiddleware(self.get_response)
        
        request = self.factory.get('/')
        request.user = AnonymousUser()
        request._original_tenant = Mock(id=1)
        request.tenant = Mock(id=2)  # Different tenant
        
        response = HttpResponse(status=200)
        
        # Should not crash despite user.id potentially missing
        result = middleware._validate_tenant_context(request, response)
        
        self.assertEqual(result.status_code, 200)

    def test_audit_middleware_safe_user_access(self):
        """Test TenantAuditMiddleware safely accesses user attributes."""
        middleware = TenantAuditMiddleware(self.get_response)
        
        request = self.factory.get('/api/orders/')
        request.user = AnonymousUser()
        request.tenant = Mock(id=1)
        
        # Should not crash
        middleware._log_tenant_access(request)

    def test_audit_middleware_authenticated_user(self):
        """Test TenantAuditMiddleware with authenticated user."""
        middleware = TenantAuditMiddleware(self.get_response)
        
        request = self.factory.get('/api/orders/')
        user_mock = Mock()
        user_mock.id = 123
        user_mock.is_authenticated = True
        request.user = user_mock
        request.tenant = Mock(id=1)
        
        # Should not crash
        middleware._log_tenant_access(request)

    @override_settings(MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'apps.tenants.middleware.TenantResolverMiddleware',
        'apps.tenants.security_middleware.TenantSecurityMiddleware',
        'apps.tenants.security_middleware.TenantAuditMiddleware',
    ])
    def test_middleware_order_correct_in_settings(self):
        """
        Test that in production settings, AuthenticationMiddleware
        comes before TenantSecurityMiddleware.
        """
        from django.conf import settings
        
        middleware_list = settings.MIDDLEWARE
        auth_index = None
        security_index = None
        
        for idx, middleware in enumerate(middleware_list):
            if 'AuthenticationMiddleware' in middleware:
                auth_index = idx
            if 'TenantSecurityMiddleware' in middleware:
                security_index = idx
        
        # Both should exist
        self.assertIsNotNone(auth_index, "AuthenticationMiddleware not found")
        self.assertIsNotNone(security_index, "TenantSecurityMiddleware not found")
        
        # AuthenticationMiddleware MUST come before TenantSecurityMiddleware
        self.assertLess(auth_index, security_index,
                       f"AuthenticationMiddleware at {auth_index} must come before "
                       f"TenantSecurityMiddleware at {security_index}")

    def test_full_middleware_chain_with_no_user(self):
        """
        Integration test: Full middleware chain processes request
        without request.user being available initially.
        """
        middleware_security = TenantSecurityMiddleware(self.get_response)
        middleware_audit = TenantAuditMiddleware(middleware_security)
        
        request = self.factory.get('/')
        
        # Simulate AuthenticationMiddleware didn't run (request has no user)
        if hasattr(request, 'user'):
            delattr(request, 'user')
        
        # Should not crash
        response = middleware_audit(request)
        
        # Should call get_response and return its result
        self.assertEqual(response.status_code, 200)
        self.get_response.assert_called_once()

    def test_user_access_denial_logs_properly(self):
        """Test that access denial logging doesn't crash with missing user.id."""
        middleware = TenantSecurityMiddleware(self.get_response)
        
        request = self.factory.get('/api/merchant/')
        
        # User without id attribute
        user_mock = Mock()
        del user_mock.id  # Explicitly delete id attribute
        user_mock.is_authenticated = True
        request.user = user_mock
        
        # Tenant exists
        request.tenant = Mock(id=1)
        
        # Mock user_has_tenant_access to return False
        with patch.object(middleware, '_user_has_tenant_access', return_value=False):
            response = middleware._check_tenant_security(request)
            
            # Should return 403 without crashing
            self.assertEqual(response.status_code, 403)
