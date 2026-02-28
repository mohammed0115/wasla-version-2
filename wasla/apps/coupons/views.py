"""Coupon validation views and endpoints."""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from apps.coupons.models import Coupon
from apps.coupons.services import CouponValidationService


@require_http_methods(["POST"])
@csrf_exempt
def validate_coupon(request):
    """
    Validate a coupon code.

    POST /api/coupons/validate/
    {
        "code": "SAVE20",
        "subtotal": "100.00",
        "store_id": 1
    }
    """
    try:
        data = request.POST if request.method == "POST" else request.GET
        code = data.get("code", "").strip().upper()
        subtotal = Decimal(data.get("subtotal", "0"))
        store_id = data.get("store_id")

        if not code or not store_id:
            return JsonResponse(
                {"valid": False, "error": "Missing code or store_id"},
                status=400,
            )

        # Get coupon
        try:
            coupon = Coupon.objects.get(
                store_id=store_id,
                code=code,
            )
        except Coupon.DoesNotExist:
            return JsonResponse(
                {"valid": False, "error": "Coupon not found"},
                status=404,
            )

        # Validate
        service = CouponValidationService()
        is_valid, error_message = service.validate_coupon(
            coupon,
            customer=request.user if request.user.is_authenticated else None,
            subtotal=subtotal,
        )

        if not is_valid:
            return JsonResponse(
                {"valid": False, "error": error_message},
                status=400,
            )

        # Calculate discount
        discount_amount = coupon.calculate_discount(subtotal)
        final_total = subtotal - discount_amount

        return JsonResponse(
            {
                "valid": True,
                "code": coupon.code,
                "discount_type": coupon.discount_type,
                "discount_value": str(coupon.discount_value),
                "discount_amount": str(discount_amount),
                "final_total": str(final_total),
                "message": f"{coupon.code} applied successfully!",
            },
            status=200,
        )

    except Exception as e:
        return JsonResponse(
            {"valid": False, "error": str(e)},
            status=500,
        )


@require_http_methods(["GET"])
def get_coupon_details(request, code):
    """
    Get coupon details.

    GET /api/coupons/{code}/?store_id=1
    """
    try:
        store_id = request.GET.get("store_id")
        if not store_id:
            return JsonResponse(
                {"error": "Missing store_id"},
                status=400,
            )

        coupon = Coupon.objects.get(
            store_id=store_id,
            code=code.upper(),
            is_active=True,
        )

        return JsonResponse(
            {
                "code": coupon.code,
                "discount_type": coupon.get_discount_type_display(),
                "discount_value": str(coupon.discount_value),
                "minimum_purchase_amount": str(coupon.minimum_purchase_amount),
                "max_discount_amount": str(coupon.max_discount_amount) if coupon.max_discount_amount else None,
                "description": coupon.description,
                "is_active": coupon.is_active,
            }
        )

    except Coupon.DoesNotExist:
        return JsonResponse(
            {"error": "Coupon not found"},
            status=404,
        )
    except Exception as e:
        return JsonResponse(
            {"error": str(e)},
            status=500,
        )
