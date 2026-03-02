"""
Storefront services for publishing and managing store displays.
"""

from django.utils import timezone
from django.core.exceptions import FieldDoesNotExist
from apps.stores.models import Store


def publish_default_storefront(store: Store) -> bool:
    """
    Publish the default storefront for a store.
    
    This function is idempotent: it can be called multiple times safely.
    If the storefront is already published, it returns early without changes.
    
    Args:
        store: The Store instance to publish
    
    Returns:
        bool: True if publication happened, False if already published
    
    Side Effects:
        - Sets store.is_default_published = True
        - Sets store.default_published_at to current time
        - Saves the store
        - Creates/activates default theme/branding if needed
    """
    
    has_default_published = False
    has_published_at = False
    try:
        store._meta.get_field("is_default_published")
        has_default_published = True
    except FieldDoesNotExist:
        has_default_published = False
    try:
        store._meta.get_field("default_published_at")
        has_published_at = True
    except FieldDoesNotExist:
        has_published_at = False

    # Idempotency check: if already published, return early
    if has_default_published and getattr(store, "is_default_published", False):
        return False

    update_fields = []
    if has_default_published:
        store.is_default_published = True
        update_fields.append("is_default_published")
    if has_published_at:
        store.default_published_at = timezone.now()
        update_fields.append("default_published_at")

    if update_fields:
        update_fields.append("updated_at")
        store.save(update_fields=update_fields)
    
    # Create default StoreBranding if not exists (assign first active theme)
    try:
        from apps.themes.models import Theme, StoreBranding
        
        # Get first active theme as default
        default_theme = Theme.objects.filter(is_active=True).first()
        
        if default_theme:
            # Create or get StoreBranding
            branding, created = StoreBranding.objects.get_or_create(
                store=store,
                defaults={
                    'theme': default_theme,
                }
            )
            if created:
                # Newly created - it's now active
                pass
    except ImportError:
        # Theme models not available, skip theming
        pass
    except Exception as e:
        # Log but don't fail - publishing doesn't depend on theming
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not set default theme for store {store.id}: {str(e)}")
    
    return True
