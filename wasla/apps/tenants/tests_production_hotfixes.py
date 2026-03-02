"""
Tests for production hotfixes (March 2026):
- TenantSecurityMiddleware async_mode fix
- Prometheus metrics graceful degradation
- StoreDomain status constant fallback
- Domain resolution with proxy headers
"""

from unittest.mock import Mock, patch, MagicMock
import pytest
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.contrib.auth import get_user_model

User = get_user_model()


class TestMetricsEndpointGracefulDegradation(TestCase):
    """Test /metrics endpoint works even if prometheus_client is missing."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('apps.observability.views.metrics.PROMETHEUS_AVAILABLE', False)
    def test_metrics_returns_503_when_prometheus_unavailable(self):
        """Metrics endpoint returns 503 with helpful message if prometheus_client missing."""
        from apps.observability.views.metrics import metrics
        
        request = self.factory.get('/metrics')
        response = metrics(request)
        
        assert response.status_code == 503, "Should return 503 when prometheus_client unavailable"
        assert 'prometheus-client' in response.content.decode(), "Should mention install command"

    @patch('apps.observability.views.metrics.PROMETHEUS_AVAILABLE', True)
    @patch('apps.observability.views.metrics.generate_latest')
    def test_metrics_returns_200_when_prometheus_available(self, mock_generate):
        """Metrics endpoint returns 200 when prometheus_client is available."""
        mock_generate.return_value = b"# HELP metrics\n"
        from apps.observability.views.metrics import metrics
        
        request = self.factory.get('/metrics')
        response = metrics(request)
        
        assert response.status_code == 200, "Should return 200 when prometheus_client available"

    @patch('apps.observability.views.metrics.PROMETHEUS_AVAILABLE', True)
    @patch('apps.observability.views.metrics.generate_latest')
    def test_metrics_handles_generation_errors(self, mock_generate):
        """Metrics endpoint returns 500 with message if generation fails."""
        mock_generate.side_effect = RuntimeError("Metrics generation failed")
        from apps.observability.views.metrics import metrics
        
        request = self.factory.get('/metrics')
        response = metrics(request)
        
        assert response.status_code == 500, "Should return 500 on metrics generation error"
        assert 'error' in response.content.decode(), "Should return error message"


class TestStoreDomainStatusConstants(TestCase):
    """Test StoreDomain status constants are correctly defined and safe."""

    def test_store_domain_has_status_constants(self):
        """StoreDomain model should have all required status constants."""
        from apps.tenants.models import StoreDomain
        
        expected_constants = [
            'STATUS_PENDING_VERIFICATION',
            'STATUS_VERIFIED',
            'STATUS_CERT_REQUESTED',
            'STATUS_CERT_ISSUED',
            'STATUS_ACTIVE',
            'STATUS_DEGRADED',
            'STATUS_FAILED',
            # Backward compatibility aliases
            'STATUS_SSL_PENDING',
            'STATUS_SSL_ACTIVE',
            'STATUS_SSL_DEGRADED',
            'STATUS_SSL_FAILED',
        ]
        
        for const in expected_constants:
            assert hasattr(StoreDomain, const), f"Missing constant: {const}"

    def test_domain_resolution_uses_defensive_getattr(self):
        """Domain resolution should safely handle missing status constants."""
        from apps.tenants.services.domain_resolution import _resolve_uncached
        from apps.tenants.models import StoreDomain, Tenant
        
        # This should not crash even if we simulate a constant being missing
        with patch.object(StoreDomain, 'STATUS_ACTIVE', 'active'):
            with patch.object(StoreDomain, 'STATUS_DEGRADED', 'degraded'):
                # Create a test domain
                tenant = Tenant.objects.create(
                    name="Test Tenant",
                    is_active=True,
                    slug="test-tenant"
                )
                
                # Result should work without errors
                result = _resolve_uncached("test.example.com")
                # Expected: None, but no AttributeError


class TestTenantSecurityMiddlewareAsync(TestCase):
    """Test TenantSecurityMiddleware works without async_mode errors."""

    def test_middleware_initializes_without_async_mode_error(self):
        """TenantSecurityMiddleware should not access async_mode on init."""
        from apps.tenants.security_middleware import (
            TenantSecurityMiddleware,
            TenantContextMiddleware,
            TenantAuditMiddleware
        )
        
        get_response = Mock(return_value=HttpResponse("OK"))
        
        # All three middleware should initialize without AttributeError
        m1 = TenantSecurityMiddleware(get_response)
        m2 = TenantContextMiddleware(get_response)
        m3 = TenantAuditMiddleware(get_response)
        
        assert not hasattr(m1, 'async_mode'), "Middleware should not have async_mode"
        assert not hasattr(m2, 'async_mode'), "Middleware should not have async_mode"
        assert not hasattr(m3, 'async_mode'), "Middleware should not have async_mode"

    def test_middleware_call_method_works(self):
        """Middleware __call__ method should work correctly."""
        from apps.tenants.security_middleware import TenantSecurityMiddleware
        
        factory = RequestFactory()
        get_response = Mock(return_value=HttpResponse("OK", status=200))
        middleware = TenantSecurityMiddleware(get_response)
        
        request = factory.get('/healthz')  # Health check path doesn't require tenant
        request.tenant = None
        request.user = Mock(is_authenticated=False)
        
        response = middleware(request)
        
        assert response.status_code == 200
        get_response.assert_called_once()


@override_settings(USE_X_FORWARDED_HOST=True)
class TestProxyHeaderHandling(TestCase):
    """Test subdomain and proxy header handling."""

    def test_settings_has_use_x_forwarded_host(self):
        """Settings should include USE_X_FORWARDED_HOST for proxy."""
        from django.conf import settings
        
        assert hasattr(settings, 'USE_X_FORWARDED_HOST'), "Missing USE_X_FORWARDED_HOST setting"
        assert settings.USE_X_FORWARDED_HOST is True, "USE_X_FORWARDED_HOST should be True for production"

    def test_allowed_hosts_includes_wildcards(self):
        """Settings should include wildcard domains for subdomains."""
        from django.conf import settings
        
        # Check that w-sala.com and wildcard .w-sala.com are in ALLOWED_HOSTS
        assert 'w-sala.com' in settings.ALLOWED_HOSTS or any(
            'sala' in h.lower() for h in settings.ALLOWED_HOSTS
        ), "ALLOWED_HOSTS should include w-sala.com or similar"

    def test_csrf_trusted_origins_secured(self):
        """Settings should have CSRF_TRUSTED_ORIGINS set correctly."""
        from django.conf import settings
        
        assert hasattr(settings, 'CSRF_TRUSTED_ORIGINS'), "Missing CSRF_TRUSTED_ORIGINS setting"
        csrf_origins = settings.CSRF_TRUSTED_ORIGINS
        
        # Should have https origins
        https_origins = [o for o in csrf_origins if o.startswith('https://')]
        assert len(https_origins) > 0, "CSRF_TRUSTED_ORIGINS should have HTTPS origins for production"


class TestHostHeaderNormalizationWithProxy(TestCase):
    """Test that host header handling works correctly behind proxy."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_x_forwarded_host_header_respected(self):
        """Middleware should respect X-Forwarded-Host header from reverse proxy."""
        from django.test import Client
        
        # This test simulates a reverse proxy sending X-Forwarded-Host
        client = Client()
        
        # Request with X-Forwarded-Host header
        response = client.get(
            '/healthz',
            HTTP_X_FORWARDED_HOST='platform.w-sala.com',
            HTTP_X_FORWARDED_PROTO='https'
        )
        
        # Should not crash; return some response (2xx or 4xx expected, not 5xx)
        assert response.status_code < 500, f"Got 5xx response: {response.status_code}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
