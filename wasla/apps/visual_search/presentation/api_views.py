from __future__ import annotations

from decimal import Decimal
from time import perf_counter

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.visual_search.application.services.text_search_engine import VisualTextSearchEngine
from apps.visual_search.infrastructure.models import VoiceSearchQueryLog
from apps.visual_search.infrastructure.stt.registry import get_stt_provider
from apps.visual_search.application.dto.visual_search_dto import VisualSearchQueryDTO
from apps.visual_search.application.usecases.visual_search_usecase import VisualSearchUseCase
from apps.visual_search.domain.errors import InvalidImageError
from apps.visual_search.infrastructure.repositories.django_visual_search_repository import (
    DjangoVisualSearchRepository,
)
from apps.visual_search.presentation.serializers import VisualSearchRequestSerializer, VoiceSearchRequestSerializer


class VisualSearchAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        tenant_id = getattr(tenant, "id", None)
        if not tenant_id:
            return Response({"ok": False, "error": "TENANT_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VisualSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        query = VisualSearchQueryDTO(
            tenant_id=int(tenant_id),
            image_file=payload.get("image"),
            image_url=payload.get("image_url"),
            max_results=payload.get("max_results", 12),
            min_price=payload.get("min_price"),
            max_price=payload.get("max_price"),
            sort_by=payload.get("sort_by", "similarity"),
        )

        use_case = VisualSearchUseCase(repository=DjangoVisualSearchRepository())

        started_at = perf_counter()
        try:
            result = use_case.run(query)
        except InvalidImageError as exc:
            return Response({"ok": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        took_ms = int((perf_counter() - started_at) * 1000)

        serialized_results = []
        for item in result.results:
            price_value = item.price
            if isinstance(price_value, Decimal):
                price_value = f"{price_value:.2f}"
            serialized_results.append(
                {
                    "product_id": item.product_id,
                    "title": item.title,
                    "price": str(price_value),
                    "currency": item.currency,
                    "similarity": item.similarity_score,
                    "image_url": item.image_url,
                }
            )

        return Response(
            {
                "ok": True,
                "tenant_id": int(tenant_id),
                "took_ms": took_ms,
                "results": serialized_results,
            },
            status=status.HTTP_200_OK,
        )


class VoiceSearchAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        tenant_id = getattr(tenant, "id", None)
        store = getattr(request, "store", None)
        store_id = getattr(store, "id", None)

        if not tenant_id or not store_id:
            return Response({"ok": False, "error": "TENANT_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VoiceSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        audio_file = payload.get("audio")
        content_type = str(getattr(audio_file, "content_type", "") or "")
        audio_bytes = audio_file.read() if audio_file else b""
        if not audio_bytes:
            return Response({"ok": False, "error": "EMPTY_AUDIO"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            stt_provider = get_stt_provider()
            transcript = stt_provider.transcribe(
                audio_bytes=audio_bytes,
                content_type=content_type,
                language=payload.get("language"),
            )
        except ValueError as exc:
            return Response({"ok": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        normalized_transcript = (transcript or "").strip()
        if not normalized_transcript:
            return Response(
                {"ok": False, "error": "EMPTY_TRANSCRIPT"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        engine = VisualTextSearchEngine()
        results = engine.search(
            tenant_id=int(tenant_id),
            query_text=normalized_transcript,
            max_results=payload.get("max_results", 12),
            min_price=payload.get("min_price"),
            max_price=payload.get("max_price"),
            sort_by=payload.get("sort_by", "similarity"),
        )

        VoiceSearchQueryLog.objects.create(
            store_id=int(store_id),
            tenant_id=int(tenant_id),
            user_id=request.user.id if request.user.is_authenticated else None,
            transcript=normalized_transcript,
            stt_provider=getattr(stt_provider, "code", "unknown"),
            language=payload.get("language", "") or "",
            audio_content_type=content_type,
            result_count=len(results),
        )

        return Response(
            {
                "ok": True,
                "tenant_id": int(tenant_id),
                "query": normalized_transcript,
                "provider": getattr(stt_provider, "code", "unknown"),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )
