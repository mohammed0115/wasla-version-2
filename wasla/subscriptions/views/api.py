from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from ..models import SubscriptionPlan
from ..services.subscription_service import SubscriptionService
from ..serializers import SubscriptionPlanSerializer, StoreSubscriptionSerializer

class PlanListAPI(APIView):
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "name")
        return Response(SubscriptionPlanSerializer(plans, many=True).data)

class SubscribeStoreAPI(APIView):
    def post(self, request, store_id):
        tenant = getattr(request, "tenant", None)
        tenant_id = getattr(tenant, "id", None) if tenant is not None else None
        if isinstance(tenant_id, int) and tenant_id != store_id:
            return Response({"detail": "Tenant mismatch."}, status=status.HTTP_403_FORBIDDEN)

        plan = get_object_or_404(
            SubscriptionPlan,
            id=request.data.get("plan_id"),
            is_active=True,
        )
        try:
            sub = SubscriptionService.subscribe_store(store_id, plan)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StoreSubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)
