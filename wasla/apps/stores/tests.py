from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.stores.models import Store
from apps.tenants.models import Tenant
from apps.tenants.services.domain_resolution import resolve_store_by_slug


class PlaceholderTests(TestCase):
    """Keep a minimal test module.

    The project may add comprehensive tests per phase later.
    """

    def test_placeholder(self):
        self.assertTrue(True)


class StoreSlugCacheInvalidationTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass1234",
        )
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A", is_active=True)

    def test_slug_change_invalidates_cache(self):
        store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Alpha Store",
            slug="alpha",
            subdomain="alpha",
            status=Store.STATUS_ACTIVE,
        )

        resolved = resolve_store_by_slug("alpha")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, store.id)

        store.slug = "beta"
        store.subdomain = "beta"
        store.save(update_fields=["slug", "subdomain"])

        self.assertIsNone(resolve_store_by_slug("alpha"))
        resolved_new = resolve_store_by_slug("beta")
        self.assertIsNotNone(resolved_new)
        self.assertEqual(resolved_new.id, store.id)
