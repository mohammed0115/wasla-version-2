from django.apps import AppConfig


class EmailsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.emails"
    verbose_name = "Emails"

    def ready(self):
        from . import interfaces  # noqa: F401
        from . import checks  # noqa: F401
