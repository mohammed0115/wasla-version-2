"""ZATCA app configuration."""

from django.apps import AppConfig


class ZatcaConfig(AppConfig):
    """ZATCA (Saudi Tax Authority) e-invoicing configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.zatca"
    verbose_name = "ZATCA E-Invoicing"

    def ready(self):
        """Initialize app."""
        pass
