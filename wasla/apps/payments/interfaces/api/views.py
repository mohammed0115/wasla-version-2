from __future__ import annotations

import json

from rest_framework import status
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.cart.interfaces.api.responses import api_response
from apps.payments.application.use_cases.initiate_payment import (
    InitiatePaymentCommand,
    InitiatePaymentUseCase,
)
from apps.payments.application.use_cases.handle_webhook_event import (
    HandleWebhookEventCommand,
    HandleWebhookEventUseCase,
)
from apps.payments.interfaces.api.serializers import PaymentInitiateSerializer
from apps.payments.models import PaymentAttempt, PaymentRisk, WebhookEvent
from apps.orders.models import Order
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant, require_merchant


ErrorEnvelopeSerializer = inline_serializer(
    name="PaymentsErrorEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": serializers.JSONField(allow_null=True),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

PaymentInitiateDataSerializer = inline_serializer(
    name="PaymentInitiateData",
    fields={
        "redirect_url": serializers.CharField(allow_blank=True),
        "client_secret": serializers.CharField(allow_blank=True),
    },
)

PaymentInitiateEnvelopeSerializer = inline_serializer(
    name="PaymentInitiateEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": PaymentInitiateDataSerializer,
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

WebhookEnvelopeSerializer = inline_serializer(
    name="PaymentWebhookEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": serializers.JSONField(),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)


def _build_tenant_context(request) -> TenantContext:
    store = require_store(request)
    tenant = require_tenant(request)
    tenant_id = tenant.id
    store_id = store.id
    currency = getattr(tenant, "currency", "SAR")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=currency,
        user_id=user_id,
        session_key=session_key,
    )


class PaymentInitiateAPI(APIView):
    @extend_schema(
        tags=["Payments"],
        summary="Initiate payment for order",
        request=PaymentInitiateSerializer,
        responses={
            201: PaymentInitiateEnvelopeSerializer,
            400: ErrorEnvelopeSerializer,
        },
        examples=[
            OpenApiExample(
                "Initiate payment",
                value={
                    "order_id": 101,
                    "provider_code": "tap",
                    "return_url": "https://merchant.example.com/payments/return",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        require_store(request)
        require_merchant(request)
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            result = InitiatePaymentUseCase.execute(
                InitiatePaymentCommand(
                    tenant_ctx=tenant_ctx,
                    order_id=serializer.validated_data["order_id"],
                    provider_code=serializer.validated_data["provider_code"],
                    return_url=serializer.validated_data["return_url"],
                    idempotency_key=serializer.validated_data["idempotency_key"],
                    ip_address=request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip(),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)
        return api_response(
            success=True,
            data={
                "redirect_url": result.redirect_url,
                "client_secret": result.client_secret,
            },
            status_code=status.HTTP_201_CREATED,
        )


class PaymentWebhookAPI(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Payments"],
        summary="Handle provider webhook",
        request=inline_serializer(
            name="PaymentWebhookRequest",
            fields={
                "payload": serializers.JSONField(required=False),
            },
        ),
        responses={200: WebhookEnvelopeSerializer, 400: ErrorEnvelopeSerializer},
    )
    def post(self, request, provider: str):
        payload = request.data if isinstance(request.data, dict) else {}
        raw_body = ""
        provider_key = (provider or "").strip().lower()
        if provider_key == "stripe":
            try:
                raw_body = request.body.decode("utf-8") if request.body else ""
            except Exception:
                raw_body = ""
        if not raw_body:
            raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)

        cmd = HandleWebhookEventCommand(
            provider_code=provider,
            headers=dict(request.headers),
            payload=payload,
            raw_body=raw_body,
        )

        try:
            event = HandleWebhookEventUseCase.execute(cmd)
        except ValueError as exc:
            return api_response(
                success=False,
                errors=[str(exc)],
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_response(
            success=True,
            data={
                "event_id": event.event_id,
                "provider": event.provider,
                "processing_status": event.status,
            },
            status_code=status.HTTP_200_OK,
        )


class AdminPaymentEventsAPI(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset = WebhookEvent.objects.select_related("store").order_by("-received_at")
        store_id = request.GET.get("store")
        provider = request.GET.get("provider")
        status_filter = request.GET.get("status")

        if store_id:
            queryset = queryset.filter(store_id=store_id)
        if provider:
            queryset = queryset.filter(provider=provider)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        data = [
            {
                "id": event.id,
                "store": event.store_id,
                "provider": event.provider,
                "event_id": event.event_id,
                "signature_valid": event.signature_valid,
                "processed": event.processed,
                "received_at": event.received_at,
            }
            for event in queryset[:200]
        ]
        return api_response(success=True, data=data)


class AdminPaymentRiskAPI(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset = PaymentRisk.objects.select_related("order", "store").filter(flagged=True).order_by("-created_at")
        data = [
            {
                "id": risk.id,
                "store": risk.store_id,
                "order": risk.order_id,
                "risk_score": risk.risk_score,
                "velocity_count": risk.velocity_count_5min,
                "ip_address": risk.ip_address,
                "flagged": risk.flagged,
                "reviewed": risk.reviewed,
                "review_decision": risk.review_decision,
                "created_at": risk.created_at,
            }
            for risk in queryset[:200]
        ]
        return api_response(success=True, data=data)


class AdminPaymentRiskApproveAPI(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, risk_id: int):
        risk = get_object_or_404(PaymentRisk, id=risk_id)
        risk.reviewed = True
        risk.review_decision = "approved"
        risk.review_notes = request.data.get("note", "")
        risk.reviewed_by = getattr(request.user, "username", "admin")
        risk.reviewed_at = timezone.now()
        risk.save(update_fields=["reviewed", "review_decision", "review_notes", "reviewed_by", "reviewed_at", "updated_at"])

        if risk.payment_attempt and risk.payment_attempt.status == PaymentAttempt.STATUS_FLAGGED:
            risk.payment_attempt.status = PaymentAttempt.STATUS_PENDING
            risk.payment_attempt.save(update_fields=["status", "updated_at"])
        return api_response(success=True, data={"id": risk.id, "decision": "approved"})


class AdminPaymentRiskRejectAPI(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, risk_id: int):
        risk = get_object_or_404(PaymentRisk, id=risk_id)
        risk.reviewed = True
        risk.review_decision = "rejected"
        risk.review_notes = request.data.get("note", "")
        risk.reviewed_by = getattr(request.user, "username", "admin")
        risk.reviewed_at = timezone.now()
        risk.save(update_fields=["reviewed", "review_decision", "review_notes", "reviewed_by", "reviewed_at", "updated_at"])

        if risk.payment_attempt:
            risk.payment_attempt.status = PaymentAttempt.STATUS_FAILED
            risk.payment_attempt.save(update_fields=["status", "updated_at"])
        return api_response(success=True, data={"id": risk.id, "decision": "rejected"})


def _merchant_can_access_order(request, order: Order) -> bool:
    if request.user.is_staff or request.user.is_superuser:
        return True
    if not request.user.is_authenticated:
        return False
    stores = getattr(request.user, "stores", None)
    if stores is None:
        return False
    return stores.filter(id=order.store_id).exists()


class MerchantOrderPaymentStatusAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id: int):
        order = get_object_or_404(Order, id=order_id)
        if not _merchant_can_access_order(request, order):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        attempts = PaymentAttempt.objects.filter(order=order).order_by("-created_at")
        latest = attempts.first()
        payload = {
            "order_id": order.id,
            "payment_status": latest.status if latest else "initiated",
            "attempts": [
                {
                    "id": attempt.id,
                    "status": attempt.status,
                    "provider": attempt.provider,
                    "idempotency_key": attempt.idempotency_key,
                    "created_at": attempt.created_at,
                }
                for attempt in attempts
            ],
        }
        return api_response(success=True, data=payload)


class MerchantOrderPaymentTimelineAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id: int):
        order = get_object_or_404(Order, id=order_id)
        if not _merchant_can_access_order(request, order):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        attempts = PaymentAttempt.objects.filter(order=order).order_by("created_at")
        timeline = [
            {
                "status": attempt.status,
                "provider": attempt.provider,
                "timestamp": attempt.created_at,
                "idempotency_key": attempt.idempotency_key,
            }
            for attempt in attempts
        ]
        return api_response(success=True, data={"order_id": order.id, "timeline": timeline})
