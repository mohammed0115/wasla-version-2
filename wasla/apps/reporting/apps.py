"""Reporting/VAT compliance app configuration."""

from django.apps import AppConfig


class ReportingConfig(AppConfig):
    """Tax reporting and VAT compliance configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reporting"
    verbose_name = "Tax & VAT Reporting"

    def ready(self):
        """Initialize app."""
        pass
