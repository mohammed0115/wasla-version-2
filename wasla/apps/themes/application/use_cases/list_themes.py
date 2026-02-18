from __future__ import annotations

from apps.themes.models import Theme


class ListThemesUseCase:
    @staticmethod
    def execute():
        return Theme.objects.filter(is_active=True).order_by("id")
