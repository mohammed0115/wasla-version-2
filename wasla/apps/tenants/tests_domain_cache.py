from django.core.cache import cache
from django.test import TestCase

from apps.tenants.models import StoreDomain, Tenant
from apps.tenants.services.domain_resolution import resolve_tenant_by_host


class TenantDomainCacheInvalidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A", is_active=True)

    def test_store_domain_change_invalidates_cache(self):
        domain = StoreDomain.objects.create(
            tenant=self.tenant,
            domain="foo.com",
            status=StoreDomain.STATUS_ACTIVE,
        )

        resolved = resolve_tenant_by_host("foo.com")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, self.tenant.id)

        domain.domain = "bar.com"
        domain.save(update_fields=["domain"])

        self.assertIsNone(resolve_tenant_by_host("foo.com"))
        resolved_new = resolve_tenant_by_host("bar.com")
        self.assertIsNotNone(resolved_new)
        self.assertEqual(resolved_new.id, self.tenant.id)
