"""BNPL webhook handlers and payment views."""

import json
import logging
from decimal import Decimal

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _

from apps.orders.models import Order
from apps.bnpl.models import BnplProvider, BnplTransaction
from apps.bnpl.services import (
    BnplPaymentOrchestrator,
    BnplProviderInterface,
)

logger = logging.getLogger(__name__)


@login_required
def initiate_bnpl_payment(request, order_id):
    """
    Initiate BNPL payment for an order.

    GET /checkout/bnpl/initiate/<order_id>/?provider=tabby|tamara
    """
    provider = request.GET.get("provider", "tabby")

    # Get order
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    # Validate provider
    if provider not in ["tabby", "tamara"]:
        return JsonResponse(
            {"error": f"Unknown provider: {provider}"},
            status=400,
        )

    # Create payment session
    result = BnplPaymentOrchestrator.create_payment_session(order, provider)

    if result.get("status") == "error":
        logger.error(f"BNPL session creation failed: {result.get('error')}")
        return JsonResponse(result, status=400)

    # Create transaction record
    checkout_url = result.get("checkout_url")
    session_id = result.get("session_id")

    transaction = BnplTransaction.objects.create(
        order=order,
        provider=provider,
        provider_order_id=session_id,
        amount=order.total_amount,
        currency="SAR",
        status=BnplTransaction.STATUS_PENDING,
        customer_email=order.email,
        customer_phone=order.shipping_address.phone
        if order.shipping_address
        else "",
        payment_url=checkout_url,
        checkout_id=session_id,
        response_data=result,
    )

    # Redirect to provider
    return redirect(checkout_url)


@login_required
def bnpl_payment_success(request):
    """
    Handle successful BNPL payment redirect.

    GET /checkout/bnpl-success/?checkout_id=...
    """
    checkout_id = request.GET.get("checkout_id")

    if not checkout_id:
        return JsonResponse(
            {"error": "Missing checkout_id"},
            status=400,
        )

    # Find transaction
    try:
        transaction = BnplTransaction.objects.get(checkout_id=checkout_id)
    except BnplTransaction.DoesNotExist:
        return JsonResponse(
            {"error": "Transaction not found"},
            status=404,
        )

    # Redirect to order confirmation
    return redirect("order_confirmation", order_id=transaction.order.id)


@login_required
def bnpl_payment_failure(request):
    """
    Handle failed BNPL payment redirect.

    GET /checkout/bnpl-failure/?checkout_id=...&reason=...
    """
    checkout_id = request.GET.get("checkout_id")
    reason = request.GET.get("reason", "Payment failed")

    if checkout_id:
        try:
            transaction = BnplTransaction.objects.get(checkout_id=checkout_id)
            transaction.status = BnplTransaction.STATUS_REJECTED
            transaction.response_data = {"error": reason}
            transaction.save()
        except BnplTransaction.DoesNotExist:
            pass

    return JsonResponse(
        {
            "status": "failed",
            "error": reason,
        },
        status=400,
    )


def bnpl_payment_cancel(request):
    """
    Handle cancelled BNPL payment.

    GET /checkout/bnpl-cancel/?checkout_id=...
    """
    checkout_id = request.GET.get("checkout_id")

    if checkout_id:
        try:
            transaction = BnplTransaction.objects.get(checkout_id=checkout_id)
            transaction.status = BnplTransaction.STATUS_CANCELLED
            transaction.save()
        except BnplTransaction.DoesNotExist:
            pass

    return JsonResponse(
        {
            "status": "cancelled",
            "message": "Payment cancelled",
        },
        status=400,
    )


@csrf_exempt
@require_http_methods(["POST"])
def tabby_webhook(request):
    """
    Handle Tabby webhook.

    POST /api/webhooks/tabby/
    """
    try:
        payload = json.loads(request.body)
        signature = request.META.get("HTTP_X_TABBY_SIGNATURE", "")

        result = BnplPaymentOrchestrator.process_webhook("tabby", payload, signature)

        if result.get("status") == "error":
            logger.error(f"Tabby webhook error: {result.get('error')}")
            return JsonResponse(result, status=400)

        return JsonResponse(
            {
                "status": "success",
                "message": result.get("message"),
            }
        )
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Tabby webhook")
        return JsonResponse(
            {"error": "Invalid JSON"},
            status=400,
        )
    except Exception as e:
        logger.exception(f"Tabby webhook error: {str(e)}")
        return JsonResponse(
            {"error": "Webhook processing failed"},
            status=500,
        )


@csrf_exempt
@require_http_methods(["POST"])
def tamara_webhook(request):
    """
    Handle Tamara webhook.

    POST /api/webhooks/tamara/
    """
    try:
        payload = json.loads(request.body)
        signature = request.META.get("HTTP_X_TAMARA_SIGNATURE", "")

        result = BnplPaymentOrchestrator.process_webhook("tamara", payload, signature)

        if result.get("status") == "error":
            logger.error(f"Tamara webhook error: {result.get('error')}")
            return JsonResponse(result, status=400)

        return JsonResponse(
            {
                "status": "success",
                "message": result.get("message"),
            }
        )
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Tamara webhook")
        return JsonResponse(
            {"error": "Invalid JSON"},
            status=400,
        )
    except Exception as e:
        logger.exception(f"Tamara webhook error: {str(e)}")
        return JsonResponse(
            {"error": "Webhook processing failed"},
            status=500,
        )


def get_available_bnpl_providers(store_id: int) -> list:
    """Get all active BNPL providers for a store."""
    providers = BnplProvider.objects.filter(
        store_id=store_id,
        is_active=True,
    ).values_list("provider", flat=True)

    return list(providers)


def get_bnpl_transaction_status(transaction_id: int) -> dict:
    """
    Get current status of BNPL transaction from provider.

    Args:
        transaction_id: BnplTransaction ID

    Returns:
        {"status": "pending|approved|rejected|...", "data": {...}}
    """
    try:
        transaction = BnplTransaction.objects.get(id=transaction_id)
    except BnplTransaction.DoesNotExist:
        return {"status": "error", "error": "Transaction not found"}

    # Get provider config
    try:
        config = BnplProvider.objects.get(
            store_id=transaction.order.store_id,
            provider=transaction.provider,
        )
    except BnplProvider.DoesNotExist:
        return {"status": "error", "error": "Provider not configured"}

    # Get adapter and fetch status
    adapter = BnplPaymentOrchestrator.get_adapter(config)
    result = adapter.get_payment_status(transaction.provider_order_id)

    # Update transaction if status changed
    if result.get("status") != "error":
        new_status = result.get("status")
        if new_status and transaction.status != new_status:
            transaction.status = new_status
            transaction.response_data = result.get("data", {})
            transaction.save()

    return result


def refund_bnpl_payment(
    transaction_id: int, amount: Decimal = None
) -> dict:
    """
    Refund a BNPL payment.

    Args:
        transaction_id: BnplTransaction ID
        amount: Amount to refund (None = full refund)

    Returns:
        {"status": "success|error", ...}
    """
    try:
        transaction = BnplTransaction.objects.get(id=transaction_id)
    except BnplTransaction.DoesNotExist:
        return {"status": "error", "error": "Transaction not found"}

    # Default to full refund
    if amount is None:
        amount = transaction.amount

    # Get provider config
    try:
        config = BnplProvider.objects.get(
            store_id=transaction.order.store_id,
            provider=transaction.provider,
        )
    except BnplProvider.DoesNotExist:
        return {"status": "error", "error": "Provider not configured"}

    # Get adapter and process refund
    adapter = BnplPaymentOrchestrator.get_adapter(config)
    result = adapter.refund(transaction.provider_order_id, amount)

    if result.get("status") == "success":
        # Update transaction status
        transaction.status = BnplTransaction.STATUS_REFUNDED
        transaction.save()

    return result
