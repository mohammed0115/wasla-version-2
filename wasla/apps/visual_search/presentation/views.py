from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.visual_search.application.dto.visual_search_dto import VisualSearchQueryDTO
from apps.visual_search.application.usecases.visual_search_usecase import VisualSearchUseCase
from apps.visual_search.domain.errors import InvalidImageError
from apps.visual_search.infrastructure.repositories.django_visual_search_repository import (
    DjangoVisualSearchRepository,
)


def _parse_optional_decimal(raw_value: str) -> Decimal | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    return Decimal(value)


@require_http_methods(["GET", "POST"])
def visual_search_view(request):
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    payload = request.GET if request.method == "GET" else request.POST

    sort_by = (payload.get("sort_by") or "similarity").strip().lower()
    if sort_by not in {"similarity", "price_low", "price_high", "newest"}:
        sort_by = "similarity"

    max_results_raw = (payload.get("max_results") or "12").strip()
    try:
        max_results = int(max_results_raw)
    except (TypeError, ValueError):
        max_results = 12
    max_results = max(1, min(max_results, 50))

    context = {
        "results": [],
        "error_message": "",
        "info_message": "",
        "has_searched": request.method == "POST",
        "min_price": (payload.get("min_price") or "").strip(),
        "max_price": (payload.get("max_price") or "").strip(),
        "sort_by": sort_by,
        "max_results": str(max_results),
        "image_url": (payload.get("image_url") or "").strip(),
        "attributes": {},
    }

    if request.method == "GET":
        if not tenant_id:
            context["info_message"] = "Tenant is not selected yet. Please open visual search from your store dashboard."
        return render(request, "visual_search/search.html", context)

    if not tenant_id:
        context["info_message"] = "Tenant is required to run visual search."
        return render(request, "visual_search/search.html", context)

    uploaded_image = request.FILES.get("image") or request.FILES.get("image_file")

    if not uploaded_image and not context["image_url"]:
        context["error_message"] = "Please provide an image file or image URL."
        return render(request, "visual_search/search.html", context)

    try:
        min_price = _parse_optional_decimal(context["min_price"])
        max_price = _parse_optional_decimal(context["max_price"])
    except InvalidOperation:
        context["error_message"] = "Min and max price must be valid numeric values."
        return render(request, "visual_search/search.html", context)

    if min_price is not None and max_price is not None and min_price > max_price:
        context["error_message"] = "Min price cannot be greater than max price."
        return render(request, "visual_search/search.html", context)

    query = VisualSearchQueryDTO(
        tenant_id=int(tenant_id),
        image_file=uploaded_image,
        image_url=context["image_url"],
        max_results=max_results,
        min_price=min_price,
        max_price=max_price,
        sort_by=context["sort_by"],
    )

    use_case = VisualSearchUseCase(repository=DjangoVisualSearchRepository())

    try:
        response = use_case.run(query)
    except InvalidImageError as exc:
        context["error_message"] = str(exc)
        return render(request, "visual_search/search.html", context)

    serialized_results = []
    for row in response.results:
        price_value = row.price
        if isinstance(price_value, Decimal):
            price_value = f"{price_value:.2f}"
        serialized_results.append(
            {
                "product_id": row.product_id,
                "title": row.title,
                "price": price_value,
                "currency": row.currency,
                "similarity_score": row.similarity_score,
                "image_url": row.image_url,
            }
        )

    context.update(
        {
            "results": serialized_results,
            "sort_by": context["sort_by"],
            "max_results": str(max_results),
            "image_url": context["image_url"],
            "attributes": response.attributes,
        }
    )
    return render(request, "visual_search/search.html", context)
