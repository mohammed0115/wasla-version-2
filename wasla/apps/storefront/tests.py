"""Tests for storefront views and models."""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.catalog.models import Product, Category, ProductVariant
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.stores.models import Store
from apps.tenants.models import Tenant
from .models import ProductSEO, CategorySEO, StorefrontSettings

User = get_user_model()


class StorefrontHomeViewTest(TestCase):
    """Test storefront home page."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            name="Test Store",
            slug="test-store",
            tenant=self.tenant,
            description="Test store"
        )

    def test_home_page_loads(self):
        """Test that home page loads successfully."""
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/home.html")

    def test_home_page_shows_categories(self):
        """Test that home page displays categories."""
        category = Category.objects.create(
            store_id=self.store.id,
            name="Test Category"
        )
        CategorySEO.objects.create(
            category=category,
            slug="test-category"
        )

        response = self.client.get(reverse("storefront:home"))
        self.assertIn(category, response.context["categories"])

    def test_home_page_shows_products(self):
        """Test that home page displays products."""
        product = Product.objects.create(
            store_id=self.store.id,
            sku="TEST001",
            name="Test Product",
            price=Decimal("100.00"),
            visibility=Product.VISIBILITY_ENABLED,
            is_active=True
        )
        ProductSEO.objects.create(
            product=product,
            slug="test-product"
        )

        response = self.client.get(reverse("storefront:home"))
        self.assertIn(product, response.context["products"])


class CategoryProductsViewTest(TestCase):
    """Test category products page."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            name="Test Store",
            slug="test-store",
            tenant=self.tenant
        )
        self.category = Category.objects.create(
            store_id=self.store.id,
            name="Test Category"
        )
        self.category_seo = CategorySEO.objects.create(
            category=self.category,
            slug="test-category"
        )

    def test_category_page_loads(self):
        """Test that category page loads."""
        response = self.client.get(
            reverse("storefront:category", kwargs={"slug": "test-category"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/category.html")

    def test_category_shows_products(self):
        """Test that category page shows products in that category."""
        product = Product.objects.create(
            store_id=self.store.id,
            sku="TEST001",
            name="Test Product",
            price=Decimal("100.00"),
            visibility=Product.VISIBILITY_ENABLED,
            is_active=True
        )
        product.categories.add(self.category)
        ProductSEO.objects.create(
            product=product,
            slug="test-product"
        )

        response = self.client.get(
            reverse("storefront:category", kwargs={"slug": "test-category"})
        )
        self.assertIn(product, response.context["products"].object_list)

    def test_category_filters_by_price(self):
        """Test price filtering on category page."""
        # Create products with different prices
        cheap_product = Product.objects.create(
            store_id=self.store.id,
            sku="CHEAP001",
            name="Cheap Product",
            price=Decimal("10.00"),
            visibility=Product.VISIBILITY_ENABLED,
            is_active=True
        )
        cheap_product.categories.add(self.category)
        ProductSEO.objects.create(product=cheap_product, slug="cheap-product")

        expensive_product = Product.objects.create(
            store_id=self.store.id,
            sku="EXP001",
            name="Expensive Product",
            price=Decimal("1000.00"),
            visibility=Product.VISIBILITY_ENABLED,
            is_active=True
        )
        expensive_product.categories.add(self.category)
        ProductSEO.objects.create(product=expensive_product, slug="expensive-product")

        # Filter by price range
        response = self.client.get(
            reverse("storefront:category", kwargs={"slug": "test-category"}),
            {"min_price": "50", "max_price": "500"}
        )
        self.assertEqual(response.status_code, 200)
        # Neither should be in results for 50-500 range
        products = list(response.context["products"])
        self.assertNotIn(cheap_product, products)
        self.assertNotIn(expensive_product, products)


class ProductSearchViewTest(TestCase):
    """Test product search functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            name="Test Store",
            slug="test-store",
            tenant=self.tenant
        )

    def test_search_page_loads(self):
        """Test that search page loads."""
        response = self.client.get(reverse("storefront:search"), {"q": "test"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/search.html")

    def test_search_finds_products_by_name(self):
        """Test that search finds products by name."""
        product = Product.objects.create(
            store_id=self.store.id,
            sku="TEST001",
            name="Test Product",
            price=Decimal("100.00"),
            visibility=Product.VISIBILITY_ENABLED,
            is_active=True
        )
        ProductSEO.objects.create(product=product, slug="test-product")

        response = self.client.get(reverse("storefront:search"), {"q": "Test"})
        self.assertIn(product, response.context["products"].object_list)

    def test_search_finds_products_by_sku(self):
        """Test that search finds products by SKU."""
        product = Product.objects.create(
            store_id=self.store.id,
            sku="ABC123",
            name="Product",
            price=Decimal("100.00"),
            visibility=Product.VISIBILITY_ENABLED,
            is_active=True
        )
        ProductSEO.objects.create(product=product, slug="product")

        response = self.client.get(reverse("storefront:search"), {"q": "ABC123"})
        self.assertIn(product, response.context["products"].object_list)

    def test_search_returns_empty_without_query(self):
        """Test that search returns no results without query."""
        response = self.client.get(reverse("storefront:search"), {"q": ""})
        self.assertEqual(len(response.context["products"]), 0)


class ProductDetailViewTest(TestCase):
    """Test product detail page."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            name="Test Store",
            slug="test-store",
            tenant=self.tenant
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="TEST001",
            name="Test Product",
            price=Decimal("100.00"),
            description_en="Test description",
            visibility=Product.VISIBILITY_ENABLED,
            is_active=True
        )
        self.product_seo = ProductSEO.objects.create(
            product=self.product,
            slug="test-product",
            meta_title="Test Product",
            meta_description="Test description"
        )

    def test_product_detail_page_loads(self):
        """Test that product detail page loads."""
        response = self.client.get(
            reverse("storefront:product_detail", kwargs={"slug": "test-product"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/product_detail.html")

    def test_product_detail_shows_correct_product(self):
        """Test that product detail page shows correct product."""
        response = self.client.get(
            reverse("storefront:product_detail", kwargs={"slug": "test-product"})
        )
        self.assertEqual(response.context["product"], self.product)

    def test_product_detail_with_variants(self):
        """Test product detail with variants."""
        variant = ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="VAR001",
            stock_quantity=10,
            is_active=True
        )

        response = self.client.get(
            reverse("storefront:product_detail", kwargs={"slug": "test-product"})
        )
        self.assertIn(variant, response.context["variants"])


class CustomerAccountViewTest(TestCase):
    """Test customer account pages."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            name="Test Store",
            slug="test-store",
            tenant=self.tenant
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.customer = Customer.objects.create(
            store_id=self.store.id,
            email=self.user.email,
            full_name="Test User"
        )

    def test_customer_orders_page_requires_login(self):
        """Test that customer orders page requires login."""
        response = self.client.get(reverse("storefront:customer_orders"))
        # Should redirect to login
        self.assertNotEqual(response.status_code, 200)

    def test_customer_orders_page_loads(self):
        """Test that customer orders page loads when logged in."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("storefront:customer_orders"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/customer_orders.html")

    def test_customer_addresses_page_requires_login(self):
        """Test that customer addresses page requires login."""
        response = self.client.get(reverse("storefront:customer_addresses"))
        # Should redirect to login
        self.assertNotEqual(response.status_code, 200)


class SEOModelTest(TestCase):
    """Test SEO models."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            name="Test Store",
            slug="test-store",
            tenant=self.tenant
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="TEST001",
            name="Test Product",
            price=Decimal("100.00"),
            description_en="Great product",
            is_active=True
        )

    def test_product_seo_auto_slug(self):
        """Test that ProductSEO auto-generates slug."""
        seo = ProductSEO.objects.create(product=self.product)
        self.assertIsNotNone(seo.slug)
        self.assertEqual(seo.slug, "test-product")

    def test_product_seo_auto_meta_description(self):
        """Test that ProductSEO auto-generates meta description."""
        seo = ProductSEO.objects.create(product=self.product)
        self.assertIsNotNone(seo.meta_description)
        self.assertIn("Great product", seo.meta_description)

    def test_category_seo_auto_slug(self):
        """Test that CategorySEO auto-generates slug."""
        category = Category.objects.create(
            store_id=self.store.id,
            name="Test Category"
        )
        seo = CategorySEO.objects.create(category=category)
        self.assertIsNotNone(seo.slug)
        self.assertEqual(seo.slug, "test-category")


class StorefrontSettingsTest(TestCase):
    """Test storefront settings."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            name="Test Store",
            slug="test-store",
            tenant=self.tenant
        )

    def test_storefront_settings_creation(self):
        """Test creating storefront settings."""
        settings = StorefrontSettings.objects.create(
            store=self.store,
            product_per_page=20,
            enable_search=True,
            enable_filters=True
        )
        self.assertEqual(settings.store, self.store)
        self.assertEqual(settings.product_per_page, 20)
        self.assertTrue(settings.enable_search)

    def test_default_vat_rate(self):
        """Test default VAT rate."""
        settings = StorefrontSettings.objects.create(store=self.store)
        self.assertEqual(settings.vat_rate, Decimal("0.15"))
