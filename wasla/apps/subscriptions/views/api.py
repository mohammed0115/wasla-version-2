from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from ..models import SubscriptionPlan
from ..services.subscription_service import SubscriptionService
from ..serializers import SubscriptionPlanSerializer, StoreSubscriptionSerializer
from apps.tenants.guards import require_store, require_tenant

class PlanListAPI(APIView):
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "name")
        return Response(SubscriptionPlanSerializer(plans, many=True).data)

class SubscribeStoreAPI(APIView):
    def post(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store.id) != int(store_id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        plan = get_object_or_404(
            SubscriptionPlan,
            id=request.data.get("plan_id"),
            is_active=True,
        )
        try:
            sub = SubscriptionService.subscribe_store(store.id, plan)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StoreSubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)
