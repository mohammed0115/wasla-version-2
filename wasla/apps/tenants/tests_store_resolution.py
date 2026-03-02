from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, RequestFactory

from apps.stores.models import Store
from apps.tenants.middleware import TenantResolverMiddleware
from apps.tenants.models import StoreDomain, Tenant
from apps.tenants.services.domain_resolution import resolve_store_by_host


class StoreResolutionTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass1234",
        )
        self.tenant = Tenant.objects.create(slug="alpha", name="Alpha", is_active=True)
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Alpha Store",
            slug="alpha",
            subdomain="alpha",
            status=Store.STATUS_ACTIVE,
        )
        self.factory = RequestFactory()

    def test_root_domain_resolves_platform_store(self):
        platform_store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Platform Store",
            slug="platform",
            subdomain="platform",
            status=Store.STATUS_ACTIVE,
            is_platform_default=True,
        )
        request = self.factory.get("/", HTTP_HOST="w-sala.com")
        middleware = TenantResolverMiddleware(lambda r: None)
        middleware.process_request(request)
        self.assertIsNotNone(getattr(request, "store", None))
        self.assertEqual(request.store.id, platform_store.id)

    def test_subdomain_resolves_store(self):
        store = resolve_store_by_host("alpha.w-sala.com")
        self.assertIsNotNone(store)
        self.assertEqual(store.id, self.store.id)

    def test_dotted_subdomain_normalizes(self):
        store = resolve_store_by_host("alpha.com.w-sala.com")
        self.assertIsNotNone(store)
        self.assertEqual(store.id, self.store.id)

    def test_auto_creates_domain_mapping(self):
        host = "alpha.w-sala.com"
        self.assertFalse(StoreDomain.objects.filter(domain=host).exists())
        store = resolve_store_by_host(host)
        self.assertIsNotNone(store)
        self.assertTrue(StoreDomain.objects.filter(domain=host, store=store).exists())
