"""
Django REST Framework views for payment security endpoints.

Admin APIs:
- GET /api/admin/payments/risk/ - List flagged payments
- POST /api/admin/payments/risk/{id}/approve/ - Approve risky payment
- POST /api/admin/payments/risk/{id}/reject/ - Reject risky payment
- GET /api/admin/payments/events/ - Payment webhook event log
- GET /api/admin/payments/attempts/{id}/ - Payment attempt details

Merchant APIs:
- GET /api/orders/{order_id}/payment-status/ - Order payment status
- GET /api/orders/{order_id}/payment-timeline/ - Payment timeline
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters

from apps.payments.models import (
    PaymentAttempt,
    WebhookEvent,
    PaymentRisk,
    PaymentProviderSettings,
)
from apps.orders.models import Order
from apps.payments.serializers_security import (
    PaymentRiskSerializer,
    PaymentRiskApprovalSerializer,
    WebhookEventSerializer,
    PaymentAttemptTimelineSerializer,
    PaymentAttemptDetailSerializer,
    OrderPaymentStatusSerializer,
    PaymentProviderSettingsSerializer,
)


class AdminPaymentPermission(IsAuthenticated):
    """Permission for admin payment endpoints."""
    
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) 
            and (request.user.is_staff or request.user.is_superuser)
        )


class MerchantPaymentPermission(IsAuthenticated):
    """Permission for merchant payment endpoints."""
    
    def has_object_permission(self, request, view, obj):
        """Check if merchant can access order."""
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Merchant can only access their own orders
        if hasattr(obj, 'store') and obj.store:
            return obj.store.owner == request.user or request.user in obj.store.staff.all()
        
        return False


class PaymentRiskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for payment risk management.
    
    Actions:
    - list: Get flagged payments
    - retrieve: Get risk details
    - approve: Approve risky payment
    - reject: Reject risky payment
    """
    
    queryset = PaymentRisk.objects.filter(flagged=True).order_by('-created_at')
    serializer_class = PaymentRiskSerializer
    permission_classes = [AdminPaymentPermission]
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    filterset_fields = ['risk_level', 'reviewed', 'review_decision']
    search_fields = ['order__order_number', 'ip_address']
    ordering_fields = ['risk_score', 'created_at', 'reviewed_at']
    
    def get_queryset(self):
        """Filter by store if user is staff."""
        qs = super().get_queryset()
        
        if self.request.user.is_superuser:
            return qs
        
        # Staff can only see payments for their stores
        user_stores = self.request.user.store_set.all()
        return qs.filter(store__in=user_stores)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve a risky payment.
        
        Request body:
        {
            "review_notes": "Payment looks legitimate"
        }
        """
        risk = self.get_object()
        
        if risk.reviewed:
            return Response(
                {'detail': 'Payment already reviewed'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        serializer = PaymentRiskApprovalSerializer(
            risk,
            data={
                'review_decision': 'approved',
                'review_notes': request.data.get('review_notes', ''),
            },
            context={'request': request},
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                PaymentRiskSerializer(risk).data,
                status=status.HTTP_200_OK,
            )
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject a risky payment.
        
        Request body:
        {
            "review_notes": "Payment declined due to high risk"
        }
        """
        risk = self.get_object()
        
        if risk.reviewed:
            return Response(
                {'detail': 'Payment already reviewed'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        serializer = PaymentRiskApprovalSerializer(
            risk,
            data={
                'review_decision': 'rejected',
                'review_notes': request.data.get('review_notes', ''),
            },
            context={'request': request},
        )
        
        if serializer.is_valid():
            serializer.save()
            
            # TODO: If order payment was pending, mark as failed/cancelled
            try:
                if risk.order_id and risk.payment_attempt:
                    risk.payment_attempt.status = 'failed'
                    risk.payment_attempt.save(update_fields=['status'])
            except Exception as e:
                pass  # Don't block approval on payment update failure
            
            return Response(
                PaymentRiskSerializer(risk).data,
                status=status.HTTP_200_OK,
            )
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for webhook event log.
    
    Actions:
    - list: Get webhook events with filtering
    - retrieve: Get event details
    """
    
    queryset = WebhookEvent.objects.all().order_by('-created_at')
    serializer_class = WebhookEventSerializer
    permission_classes = [AdminPaymentPermission]
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_fields = ['provider', 'status', 'signature_verified']
    ordering_fields = ['created_at', 'retry_count']
    
    def get_queryset(self):
        """Filter by store if user is staff."""
        qs = super().get_queryset()
        
        if self.request.user.is_superuser:
            return qs
        
        # Staff can only see webhooks for their stores
        user_stores = self.request.user.store_set.all()
        return qs.filter(store__in=user_stores)


class PaymentAttemptDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for payment attempt admin view.
    
    Actions:
    - list: Get payment attempts
    - retrieve: Get attempt details with webhook and risk info
    """
    
    queryset = PaymentAttempt.objects.all().order_by('-created_at')
    serializer_class = PaymentAttemptDetailSerializer
    permission_classes = [AdminPaymentPermission]
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_fields = ['status', 'provider', 'webhook_verified']
    ordering_fields = ['created_at', 'confirmed_at', 'amount']
    
    def get_queryset(self):
        """Filter by store if user is staff."""
        qs = super().get_queryset()
        
        if self.request.user.is_superuser:
            return qs
        
        # Staff can only see payments for their orders
        user_stores = self.request.user.store_set.all()
        return qs.filter(order__store__in=user_stores)


class OrderPaymentStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for merchant order payment status.
    
    Actions:
    - retrieve: Get order payment status and timeline
    
    URL: /api/orders/{order_id}/payment-status/
    """
    
    queryset = Order.objects.all()
    serializer_class = OrderPaymentStatusSerializer
    permission_classes = [MerchantPaymentPermission]
    lookup_field = 'id'
    
    def get_queryset(self):
        """Filter merchant's orders."""
        qs = super().get_queryset()
        
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        
        # Merchant sees only their orders
        user_stores = self.request.user.store_set.all()
        return qs.filter(store__in=user_stores)
    
    def check_object_permissions(self, request, obj):
        """Check if merchant can access order."""
        if request.user.is_staff or request.user.is_superuser:
            return
        
        # Merchant can access their own orders
        user_stores = request.user.store_set.all()
        if obj.store not in user_stores:
            self.permission_denied(request)


class PaymentProviderSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for payment provider configuration (superuser only).
    
    Actions:
    - list: Get providers
    - retrieve: Get provider details
    - partial_update: Update settings (PATCH)
    """
    
    queryset = PaymentProviderSettings.objects.all()
    serializer_class = PaymentProviderSettingsSerializer
    permission_classes = [AdminPaymentPermission]
    lookup_field = 'provider_code'
    
    def get_queryset(self):
        """Only superuser can view all providers."""
        if not self.request.user.is_superuser:
            return PaymentProviderSettings.objects.none()
        
        return super().get_queryset()
    
    def update(self, request, *args, **kwargs):
        """Restrict updates to PATCH only."""
        return self.partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Prevent deletion."""
        return Response(
            {'detail': 'Provider settings cannot be deleted'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# Helper function to register routes
def register_payment_routes(router):
    """
    Register payment security routes.
    
    Usage in urls.py:
        from rest_framework.routers import DefaultRouter
        from apps.payments.views_security import register_payment_routes
        
        router = DefaultRouter()
        register_payment_routes(router)
        urlpatterns = router.urls
    """
    router.register(
        r'admin/payment-risk',
        PaymentRiskViewSet,
        basename='payment-risk',
    )
    router.register(
        r'admin/webhook-events',
        WebhookEventViewSet,
        basename='webhook-event',
    )
    router.register(
        r'admin/payment-attempts',
        PaymentAttemptDetailViewSet,
        basename='payment-attempt-detail',
    )
    router.register(
        r'orders/(?P<order_id>\d+)/payment-status',
        OrderPaymentStatusViewSet,
        basename='order-payment-status',
    )
    router.register(
        r'admin/provider-settings',
        PaymentProviderSettingsViewSet,
        basename='provider-settings',
    )
