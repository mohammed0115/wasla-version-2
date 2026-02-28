"""
DRF ViewSets for SaaS billing API.

REST API endpoints for:
- Subscriptions (CRUD, plan changes, cancellation)
- Invoices and billing cycles
- Payment methods
- Dunning management
- Webhook handling
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db import transaction
import logging

from .models_billing import (
    Subscription, SubscriptionItem, BillingCycle, Invoice,
    DunningAttempt, PaymentEvent, PaymentMethod, BillingPlan
)
from .serializers_billing import (
    SubscriptionDetailSerializer, SubscriptionListSerializer,
    SubscriptionCreateSerializer, SubscriptionChangeSerializer,
    SubscriptionCancelSerializer, BillingCycleSerializer,
    InvoiceSerializer, DunningAttemptSerializer, PaymentMethodSerializer,
    PaymentMethodCreateSerializer, PaymentEventSerializer,
    GracePeriodSerializer, BillingPlanSerializer,
    BillingStatusSerializer, ProrateCalculationSerializer,
    DunningStatusSerializer
)
from .services_billing import (
    SubscriptionService, BillingService, DunningService, WebhookService
)

logger = logging.getLogger(__name__)


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    API for managing subscriptions.
    
    Endpoints:
    - GET /subscriptions/ - List subscriptions
    - GET /subscriptions/<id>/ - Get subscription details
    - POST /subscriptions/ - Create subscription
    - PATCH /subscriptions/<id>/ - Update subscription
    - DELETE /subscriptions/<id>/ - Delete subscription
    - POST /subscriptions/<id>/change-plan/ - Change plan
    - POST /subscriptions/<id>/cancel/ - Cancel subscription
    - POST /subscriptions/<id>/suspend/ - Suspend (admin)
    - POST /subscriptions/<id>/reactivate/ - Reactivate
    - POST /subscriptions/<id>/add-grace-period/ - Add grace period
    - GET /subscriptions/<id>/billing-status/ - Get billing status
    """
    
    queryset = Subscription.objects.all().select_related(
        'tenant', 'plan', 'payment_method'
    )
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = []  # Can add DjangoFilterBackend for filtering
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SubscriptionListSerializer
        elif self.action == 'create':
            return SubscriptionCreateSerializer
        elif self.action == 'change_plan':
            return SubscriptionChangeSerializer
        elif self.action == 'cancel':
            return SubscriptionCancelSerializer
        elif self.action == 'add_grace_period':
            return GracePeriodSerializer
        else:
            return SubscriptionDetailSerializer
    
    def get_queryset(self):
        # Filter by tenant (multi-tenant safety)
        user = self.request.user
        if hasattr(user, 'tenant'):
            return self.queryset.filter(tenant=user.tenant)
        return self.queryset
    
    @action(detail=True, methods=['post'])
    def change_plan(self, request, pk=None):
        """Change subscription to a new plan with proration."""
        subscription = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            new_plan = BillingPlan.objects.get(
                id=serializer.validated_data['new_plan_id']
            )
            
            # Calculate proration
            proration = BillingService.calculate_proration(
                subscription=subscription,
                old_plan=subscription.plan,
                new_plan=new_plan
            )
            
            # Change plan
            with transaction.atomic():
                updated_subscription = SubscriptionService.change_plan(
                    subscription=subscription,
                    new_plan=new_plan,
                    idempotency_key=f"plan_change_{subscription.id}_{new_plan.id}"
                )
            
            # Return response with proration info
            response_data = SubscriptionDetailSerializer(
                updated_subscription
            ).data
            response_data['proration'] = {
                'amount': float(proration),
                'type': 'credit' if proration < 0 else 'charge'
            }
            
            return Response(
                response_data,
                status=status.HTTP_200_OK
            )
        
        except BillingPlan.DoesNotExist:
            return Response(
                {'error': 'Plan not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Error changing plan: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a subscription."""
        subscription = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            cancelled = SubscriptionService.cancel_subscription(
                subscription=subscription,
                reason=serializer.validated_data.get('reason'),
                immediately=serializer.validated_data.get('immediately', False)
            )
            
            return Response(
                SubscriptionDetailSerializer(cancelled).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception(f"Error cancelling subscription: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def suspend(self, request, pk=None):
        """Suspend a subscription (admin only)."""
        subscription = self.get_object()
        reason = request.data.get('reason', 'Admin suspension')
        
        try:
            suspended = SubscriptionService.suspend_subscription(
                subscription=subscription,
                reason=reason
            )
            
            return Response(
                SubscriptionDetailSerializer(suspended).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reactivate(self, request, pk=None):
        """Reactivate a suspended subscription (admin only)."""
        subscription = self.get_object()
        
        try:
            reactivated = SubscriptionService.reactivate_subscription(
                subscription=subscription
            )
            
            return Response(
                SubscriptionDetailSerializer(reactivated).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def add_grace_period(self, request, pk=None):
        """Add grace period to a past-due subscription."""
        subscription = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            updated = DunningService.add_grace_period(
                subscription=subscription,
                days=serializer.validated_data.get('days', 7)
            )
            
            return Response(
                SubscriptionDetailSerializer(updated).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def billing_status(self, request, pk=None):
        """Get detailed billing status for a subscription."""
        subscription = self.get_object()
        
        # Calculate outstanding balance
        outstanding_invoices = Invoice.objects.filter(
            subscription=subscription,
            status__in=['issued', 'overdue', 'partial']
        )
        outstanding = sum(inv.amount_due for inv in outstanding_invoices)
        
        # Determine if action required
        action_required = subscription.state in ['past_due', 'grace']
        
        data = {
            'subscription_state': subscription.state,
            'next_billing_date': subscription.next_billing_date,
            'outstanding_balance': float(outstanding),
            'currency': subscription.currency,
            'is_active': subscription.is_active(),
            'grace_until': subscription.grace_until,
            'action_required': action_required
        }
        
        serializer = BillingStatusSerializer(data)
        return Response(serializer.data)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for invoices.
    
    Endpoints:
    - GET /invoices/ - List invoices
    - GET /invoices/<id>/ - Get invoice details
    """
    
    queryset = Invoice.objects.all().select_related(
        'subscription', 'billing_cycle'
    ).order_by('-issued_date')
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'tenant'):
            return self.queryset.filter(subscription__tenant=user.tenant)
        return self.queryset


class BillingCycleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for billing cycles.
    
    Endpoints:
    - GET /billing-cycles/ - List cycles
    - GET /billing-cycles/<id>/ - Get cycle details
    """
    
    queryset = BillingCycle.objects.all().select_related(
        'subscription'
    ).order_by('-period_end')
    serializer_class = BillingCycleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'tenant'):
            return self.queryset.filter(subscription__tenant=user.tenant)
        return self.queryset


class PaymentMethodViewSet(viewsets.ViewSet):
    """
    API for managing payment methods.
    
    Endpoints:
    - GET /payment-methods/<subscription_id>/ - Get payment method
    - POST /payment-methods/<subscription_id>/ - Create/update payment method
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def retrieve(self, request, pk=None):
        """Get payment method for a subscription."""
        subscription = get_object_or_404(Subscription, id=pk)
        
        # Check permissions
        if hasattr(request.user, 'tenant'):
            if subscription.tenant != request.user.tenant:
                return Response(
                    {'error': 'Not authorized'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        payment_method = subscription.payment_method
        if not payment_method:
            return Response(
                {'error': 'No payment method on file'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PaymentMethodSerializer(payment_method)
        return Response(serializer.data)
    
    def create(self, request, pk=None):
        """Create or update payment method for a subscription."""
        subscription = get_object_or_404(Subscription, id=pk)
        serializer = PaymentMethodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            payment_method, _ = PaymentMethod.objects.update_or_create(
                subscription=subscription,
                defaults={
                    'method_type': serializer.validated_data['method_type'],
                    'provider_customer_id': serializer.validated_data['provider_customer_id'],
                    'provider_payment_method_id': serializer.validated_data['provider_payment_method_id'],
                    'display_name': serializer.validated_data['display_name'],
                }
            )
            
            return Response(
                PaymentMethodSerializer(payment_method).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class WebhookViewSet(viewsets.ViewSet):
    """
    API endpoint for receiving webhooks from payment provider.
    
    Endpoints:
    - POST /webhooks/payment-events/ - Receive webhook
    """
    
    permission_classes = [permissions.AllowAny]  # Verify signature instead
    
    def create(self, request):
        """Handle incoming webhook from payment provider."""
        serializer = PaymentEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # TODO: Verify webhook signature from payment provider
            # Example: stripe_signature = request.META.get('HTTP_STRIPE_SIGNATURE')
            
            event = WebhookService.handle_payment_event(
                event_type=serializer.validated_data['event_type'],
                provider_event_id=serializer.validated_data['provider_event_id'],
                payload=serializer.validated_data['payload']
            )
            
            return Response(
                {
                    'id': str(event.id),
                    'status': event.status,
                    'provider_event_id': event.provider_event_id
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.exception(f"Webhook processing error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class DunningViewSet(viewsets.ViewSet):
    """
    API for dunning (payment retry) management.
    
    Endpoints:
    - GET /dunning/<subscription_id>/ - Get dunning status
    - POST /dunning/<subscription_id>/retry/ - Manually trigger retry
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def retrieve(self, request, pk=None):
        """Get dunning status for a subscription."""
        subscription = get_object_or_404(Subscription, id=pk)
        
        # Check permissions
        if hasattr(request.user, 'tenant'):
            if subscription.tenant != request.user.tenant:
                return Response(
                    {'error': 'Not authorized'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Get latest dunning attempt
        latest_attempt = DunningAttempt.objects.filter(
            subscription=subscription
        ).order_by('-created_at').first()
        
        if not latest_attempt:
            return Response(
                {'status': 'none'},
                status=status.HTTP_200_OK
            )
        
        data = {
            'invoice_id': str(latest_attempt.invoice_id),
            'invoice_amount': float(latest_attempt.invoice.amount_due),
            'current_attempt': latest_attempt.attempt_number,
            'next_retry_date': latest_attempt.next_retry_at,
            'last_error': latest_attempt.error_message,
            'status': latest_attempt.status
        }
        
        serializer = DunningStatusSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def retry(self, request):
        """Manually trigger dunning retry for an invoice."""
        invoice_id = request.data.get('invoice_id')
        
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            
            # Find next pending dunning attempt
            attempt = DunningAttempt.objects.filter(
                invoice=invoice,
                status='pending'
            ).order_by('attempt_number').first()
            
            if not attempt:
                return Response(
                    {'error': 'No pending dunning attempts'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process retry
            success = DunningService.process_dunning_attempt(attempt)
            
            return Response(
                {
                    'success': success,
                    'attempt_number': attempt.attempt_number,
                    'status': attempt.status
                },
                status=status.HTTP_200_OK
            )
        
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Error retrying dunning: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
