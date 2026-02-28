"""Privacy/PDPL app configuration."""

from django.apps import AppConfig


class PrivacyConfig(AppConfig):
    """Privacy and PDPL (Personal Data Protection Law) configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.privacy"
    verbose_name = "Privacy & Data Protection"

    def ready(self):
        """Initialize app."""
        pass
