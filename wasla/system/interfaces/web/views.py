from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from system.application.use_cases.check_go_live import CheckGoLiveUseCase


@staff_member_required
def admin_go_live_status(request: HttpRequest) -> HttpResponse:
    report = CheckGoLiveUseCase.execute()
    context = {
        "report": report,
        "hard_blockers": report.hard_blockers,
        "warnings": report.warnings,
    }
    return render(request, "admin/go_live_status.html", context)
