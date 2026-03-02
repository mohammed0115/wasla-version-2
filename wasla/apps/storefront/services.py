"""
Storefront services for publishing and managing store displays.
"""

from django.utils import timezone
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
    
    # Idempotency check: if already published, return early
    if getattr(store, "is_default_published", False):
        return False
    
    store.is_default_published = True
    store.default_published_at = timezone.now()
    store.save(update_fields=["is_default_published", "default_published_at", "updated_at"])
    
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
