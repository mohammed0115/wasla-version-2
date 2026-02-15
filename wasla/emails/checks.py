from __future__ import annotations

from django.core.checks import Warning, register
from django.db.utils import OperationalError, ProgrammingError

from emails.models import GlobalEmailSettings


@register()
def email_settings_check(app_configs, **kwargs):
    errors = []
    try:
        count = GlobalEmailSettings.objects.count()
    except (OperationalError, ProgrammingError):
        return errors

    if count == 0:
        errors.append(
            Warning(
                "GlobalEmailSettings is missing.",
                hint="Create one GlobalEmailSettings row in the admin (superuser only).",
                id="emails.W001",
            )
        )
    elif count > 1:
        errors.append(
            Warning(
                "Multiple GlobalEmailSettings rows found.",
                hint="Keep a single GlobalEmailSettings row.",
                id="emails.W002",
            )
        )
    return errors

