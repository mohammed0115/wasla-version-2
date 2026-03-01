"""
Management command to create the default store for root domain.

Usage:
    python manage.py create_default_store
    python manage.py create_default_store --slug custom-store-slug
    python manage.py create_default_store --confirm  # Skip confirmation
"""

from django.core.management.base import BaseCommand
from django.conf import settings

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
            help='Store slug (default: from WASLA_DEFAULT_STORE_SLUG setting)',
        )
        parser.add_argument(
            '--name',
            type=str,
            default='Wasla Default Store',
            help='Store name',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        slug = options['slug'] or getattr(settings, 'DEFAULT_STORE_SLUG', 'store1')
        name = options['name']
        confirm = options['confirm']
        
        # Check if store already exists
        existing = Store.objects.filter(slug=slug).first()
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f'Store with slug "{slug}" already exists: {existing.name}'
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
            self.stdout.write(f'  Tenant: {default_tenant.name} ({default_tenant.slug})')
            confirm_input = input('\nCreate this store? [y/N]: ').strip().lower()
            if confirm_input != 'y':
                self.stdout.write(self.style.WARNING('Cancelled.'))
                return
        
        # Create store
        try:
            store = Store.objects.create(
                slug=slug,
                name=name,
                tenant=default_tenant,
                is_active=True,
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created default store: {store.name} ({store.slug})')
            )
            self.stdout.write(
                f'\nRoot domain ({getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com")}) '
                f'will now resolve to this store.'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to create store: {e}'))
