"""
Management command to create the default store for root domain.

Usage:
    python manage.py create_default_store
    python manage.py create_default_store --slug custom-store-slug
    python manage.py create_default_store --confirm  # Skip confirmation
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist

from apps.tenants.models import Tenant
from apps.stores.models import Store


class Command(BaseCommand):
    """Create default store for root domain."""
    
    help = 'Create default store for root domain (e.g., w-sala.com)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--slug',
            type=str,
            default=None,
            help='Store slug (default: from WASSLA_PLATFORM_STORE_SLUG setting)',
        )
        parser.add_argument(
            '--name',
            type=str,
            default='Wasla Default Store',
            help='Store name',
        )
        parser.add_argument(
            '--subdomain',
            type=str,
            default='',
            help='Store subdomain (default: same as slug)',
        )
        parser.add_argument(
            '--owner-username',
            type=str,
            default='',
            help='Owner username (optional; defaults to first active superuser)',
        )
        parser.add_argument(
            '--owner-email',
            type=str,
            default='',
            help='Owner email (optional; defaults to first active superuser)',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        slug = (
            options['slug']
            or getattr(settings, 'WASSLA_PLATFORM_STORE_SLUG', '')
            or 'platform'
        )
        name = options['name']
        subdomain = (options.get('subdomain') or slug).strip() or slug
        owner_username = (options.get('owner_username') or '').strip()
        owner_email = (options.get('owner_email') or '').strip()
        confirm = options['confirm']
        
        # Check if store already exists
        existing = Store.objects.filter(slug=slug).first()
        if existing:
            try:
                Store._meta.get_field("is_platform_default")
                if not existing.is_platform_default:
                    existing.is_platform_default = True
                    existing.save(update_fields=["is_platform_default"])
                    self.stdout.write(self.style.SUCCESS("Marked existing store as platform default."))
            except FieldDoesNotExist:
                pass
            self.stdout.write(
                self.style.WARNING(
                    f'Store with slug "{slug}" already exists: {existing.name}'
                )
            )
            return
        
        # Resolve owner
        User = get_user_model()
        owner = None
        if owner_username:
            owner = User.objects.filter(username=owner_username, is_active=True).first()
        if not owner and owner_email:
            owner = User.objects.filter(email=owner_email, is_active=True).first()
        if not owner:
            owner = User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()
        if not owner:
            self.stdout.write(
                self.style.ERROR(
                    'No active superuser found. Create one or pass --owner-username/--owner-email.'
                )
            )
            return

        # Check if we need a tenant first
        default_tenant = Tenant.objects.filter(is_active=True).first()
        if not default_tenant:
            self.stdout.write(
                self.style.ERROR(
                    'No active tenant found. Create a tenant first:\n'
                    '  python manage.py shell\n'
                    '  from apps.tenants.models import Tenant\n'
                    '  Tenant.objects.create(slug="default", name="Default Tenant")\n'
                )
            )
            return
        
        # Confirm creation
        if not confirm:
            self.stdout.write('\nDefault Store Configuration:')
            self.stdout.write(f'  Slug: {slug}')
            self.stdout.write(f'  Name: {name}')
            self.stdout.write(f'  Subdomain: {subdomain}')
            self.stdout.write(f'  Tenant: {default_tenant.name} ({default_tenant.slug})')
            self.stdout.write(f'  Owner: {owner.get_username()} (id={owner.id})')
            confirm_input = input('\nCreate this store? [y/N]: ').strip().lower()
            if confirm_input != 'y':
                self.stdout.write(self.style.WARNING('Cancelled.'))
                return
        
        # Create store
        try:
            store_kwargs = {
                "slug": slug,
                "name": name,
                "tenant": default_tenant,
            }
            try:
                Store._meta.get_field("owner")
                store_kwargs["owner"] = owner
            except FieldDoesNotExist:
                pass
            try:
                Store._meta.get_field("subdomain")
                store_kwargs["subdomain"] = subdomain
            except FieldDoesNotExist:
                pass
            try:
                Store._meta.get_field("status")
                store_kwargs["status"] = Store.STATUS_ACTIVE
            except FieldDoesNotExist:
                try:
                    Store._meta.get_field("is_active")
                    store_kwargs["is_active"] = True
                except FieldDoesNotExist:
                    pass
            try:
                Store._meta.get_field("is_platform_default")
                store_kwargs["is_platform_default"] = True
            except FieldDoesNotExist:
                pass

            store = Store.objects.create(**store_kwargs)
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created default store: {store.name} ({store.slug})')
            )
            self.stdout.write(
                f'\nRoot domain ({getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com")}) '
                f'will now resolve to this store.'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to create store: {e}'))
