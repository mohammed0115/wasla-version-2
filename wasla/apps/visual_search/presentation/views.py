from __future__ import annotations

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.visual_search.application.dto.visual_search_dto import VisualSearchQueryDTO
from apps.visual_search.application.usecases.visual_search_usecase import VisualSearchUseCase
from apps.visual_search.domain.errors import InvalidImageError
from apps.visual_search.infrastructure.repositories.django_visual_search_repository import (
    DjangoVisualSearchRepository,
)


@require_http_methods(["GET", "POST"])
def visual_search_view(request):
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)

    context = {
        "results": [],
        "error_message": "",
        "min_price": request.POST.get("min_price", "") if request.method == "POST" else "",
        "max_price": request.POST.get("max_price", "") if request.method == "POST" else "",
        "sort_by": request.POST.get("sort_by", "similarity") if request.method == "POST" else "similarity",
    }

    if request.method == "GET":
        return render(request, "visual_search/search.html", context)

    if not tenant_id:
        context["error_message"] = "Tenant context is required."
        return render(request, "visual_search/search.html", context, status=400)

    uploaded_image = request.FILES.get("image_file")
    image_url = (request.POST.get("image_url") or "").strip()
    min_price = request.POST.get("min_price", "")
    max_price = request.POST.get("max_price", "")
    sort_by = request.POST.get("sort_by", "similarity")

    query = VisualSearchQueryDTO(
        tenant_id=int(tenant_id),
        image_file=uploaded_image,
        image_url=image_url,
        max_results=24,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
    )

    use_case = VisualSearchUseCase(repository=DjangoVisualSearchRepository())

    try:
        found = use_case.execute(query)
    except InvalidImageError as exc:
        context["error_message"] = str(exc)
        return render(request, "visual_search/search.html", context, status=400)

    context.update(
        {
            "results": found,
            "min_price": min_price,
            "max_price": max_price,
            "sort_by": sort_by,
        }
    )
    return render(request, "visual_search/search.html", context)
