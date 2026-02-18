from __future__ import annotations

from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.system.application.use_cases.check_go_live import CheckGoLiveUseCase
from apps.system.domain.go_live_checks.types import GoLiveReport, GoLiveCategoryResult, GoLiveCheckItem


def _serialize_item(item: GoLiveCheckItem) -> dict:
    return {
        "key": item.key,
        "label": item.label,
        "ok": item.ok,
        "level": item.level,
        "message": item.message,
        "category": item.category,
    }


def _serialize_category(category: GoLiveCategoryResult) -> dict:
    return {
        "key": category.key,
        "label": category.label,
        "items": [_serialize_item(item) for item in category.items],
    }


def _serialize_report(report: GoLiveReport) -> dict:
    return {
        "ok": report.ok,
        "score": report.score,
        "hard_blockers": [_serialize_item(item) for item in report.hard_blockers],
        "warnings": [_serialize_item(item) for item in report.warnings],
        "categories": [_serialize_category(category) for category in report.categories],
    }


class GoLiveStatusAPI(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        report = CheckGoLiveUseCase.execute()
        return api_response(success=True, data=_serialize_report(report))
