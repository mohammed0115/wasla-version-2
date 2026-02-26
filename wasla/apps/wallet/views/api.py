from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, inline_serializer

from apps.cart.interfaces.api.responses import api_response
from apps.security.rbac import require_permission
from apps.tenants.guards import require_merchant

from ..services.wallet_service import WalletService
from ..serializers import (
    WalletSerializer,
    WalletSummarySerializer,
    WithdrawalCreateSerializer,
    WithdrawalRejectSerializer,
    WithdrawalMarkPaidSerializer,
    WithdrawalRequestSerializer,
    WithdrawalRequestListSerializer,
    JournalEntrySerializer,
    JournalEntryListSerializer,
    FeePolicySerializer,
    PaymentAllocationSerializer,
)
from ..models import WithdrawalRequest, JournalEntry, FeePolicy, PaymentAllocation
from apps.tenants.guards import require_store, require_tenant


ErrorEnvelopeSerializer = inline_serializer(
    name="WalletErrorEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": serializers.JSONField(allow_null=True),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

WithdrawalListDataSerializer = inline_serializer(
    name="WalletWithdrawalListData",
    fields={
        "items": WithdrawalRequestSerializer(many=True),
    },
)

WithdrawalListEnvelopeSerializer = inline_serializer(
    name="WalletWithdrawalListEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": WithdrawalListDataSerializer,
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

WithdrawalEnvelopeSerializer = inline_serializer(
    name="WalletWithdrawalEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": WithdrawalRequestSerializer(),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

LedgerIntegrityDataSerializer = inline_serializer(
    name="WalletLedgerIntegrityData",
    fields={
        "store_id": serializers.IntegerField(),
        "wallet_id": serializers.IntegerField(),
        "is_valid": serializers.BooleanField(),
        "computed": serializers.JSONField(),
        "stored": serializers.JSONField(),
        "transaction_count": serializers.IntegerField(),
    },
)

LedgerIntegrityEnvelopeSerializer = inline_serializer(
    name="WalletLedgerIntegrityEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": LedgerIntegrityDataSerializer,
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

class WalletDetailAPI(APIView):
    @extend_schema(
        tags=["Wallet"],
        summary="Get wallet balances and transactions",
        responses={200: WalletSerializer},
    )
    @method_decorator(require_permission("wallet.view_wallet"))
    def get(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store.id) != int(store_id):
            return Response({"detail": "Not found"}, status=404)
        wallet = WalletService.get_or_create_wallet(store.id, tenant_id=tenant.id)
        return Response(WalletSerializer(wallet).data)


class MerchantWithdrawalRequestAPI(APIView):
    @extend_schema(
        tags=["Wallet"],
        summary="List withdrawal requests for merchant store",
        responses={
            200: WithdrawalListEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    @method_decorator(require_permission("wallet.view_withdrawals"))
    def get(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        require_merchant(request)
        if int(store.id) != int(store_id):
            return api_response(success=False, errors=["not_found"], status_code=404)

        items = WithdrawalRequest.objects.filter(store_id=store.id).order_by("-requested_at")[:100]
        return api_response(success=True, data={"items": WithdrawalRequestSerializer(items, many=True).data})

    @extend_schema(
        tags=["Wallet"],
        summary="Create withdrawal request",
        request=WithdrawalCreateSerializer,
        responses={
            201: WithdrawalEnvelopeSerializer,
            400: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
        examples=[
            OpenApiExample(
                "Create withdrawal",
                value={"amount": "120.00", "note": "Weekly payout"},
                request_only=True,
            )
        ],
    )
    @method_decorator(require_permission("wallet.create_withdrawal"))
    def post(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        require_merchant(request)
        if int(store.id) != int(store_id):
            return api_response(success=False, errors=["not_found"], status_code=404)

        serializer = WithdrawalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            withdrawal = WalletService.create_withdrawal_request(
                store_id=store.id,
                tenant_id=tenant.id,
                amount=serializer.validated_data["amount"],
                note=serializer.validated_data.get("note", ""),
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=400)

        return api_response(
            success=True,
            data=WithdrawalRequestSerializer(withdrawal).data,
            status_code=201,
        )


class AdminApproveWithdrawalAPI(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Wallet"],
        summary="Admin approve withdrawal request",
        responses={
            200: WithdrawalEnvelopeSerializer,
            400: ErrorEnvelopeSerializer,
        },
    )
    @method_decorator(require_permission("wallet.manage_withdrawals"))
    def post(self, request, withdrawal_id: int):
        try:
            withdrawal = WalletService.approve_withdrawal(
                withdrawal_id=withdrawal_id,
                actor_user_id=request.user.id,
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=400)

        return api_response(success=True, data=WithdrawalRequestSerializer(withdrawal).data)


class AdminRejectWithdrawalAPI(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Wallet"],
        summary="Admin reject withdrawal request",
        request=WithdrawalRejectSerializer,
        responses={
            200: WithdrawalEnvelopeSerializer,
            400: ErrorEnvelopeSerializer,
        },
        examples=[
            OpenApiExample(
                "Reject withdrawal",
                value={"rejection_reason": "Bank account verification failed"},
                request_only=True,
            )
        ],
    )
    @method_decorator(require_permission("wallet.manage_withdrawals"))
    def post(self, request, withdrawal_id: int):
        serializer = WithdrawalRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            withdrawal = WalletService.reject_withdrawal(
                withdrawal_id=withdrawal_id,
                actor_user_id=request.user.id,
                rejection_reason=serializer.validated_data.get("rejection_reason", ""),
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=400)

        return api_response(success=True, data=WithdrawalRequestSerializer(withdrawal).data)


class AdminMarkWithdrawalPaidAPI(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Wallet"],
        summary="Admin mark withdrawal as paid",
        request=WithdrawalMarkPaidSerializer,
        responses={
            200: WithdrawalEnvelopeSerializer,
            400: ErrorEnvelopeSerializer,
        },
        examples=[
            OpenApiExample(
                "Mark paid",
                value={"payout_reference": "BANK-TX-123456"},
                request_only=True,
            )
        ],
    )
    @method_decorator(require_permission("wallet.manage_withdrawals"))
    def post(self, request, withdrawal_id: int):
        serializer = WithdrawalMarkPaidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            withdrawal = WalletService.mark_withdrawal_paid(
                withdrawal_id=withdrawal_id,
                actor_user_id=request.user.id,
                payout_reference=serializer.validated_data.get("payout_reference", ""),
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=400)

        return api_response(success=True, data=WithdrawalRequestSerializer(withdrawal).data)


class WalletLedgerIntegrityAPI(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Wallet"],
        summary="Run wallet ledger integrity check",
        responses={200: LedgerIntegrityEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.view_ledger_integrity"))
    def get(self, request, store_id: int):
        tenant = require_tenant(request)
        result = WalletService.ledger_integrity_check(store_id=store_id, tenant_id=tenant.id)
        return api_response(success=True, data=result)


# ========== NEW: Enhanced Wallet Summary API ==========

WalletSummaryEnvelopeSerializer = inline_serializer(
    name="WalletSummaryEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": WalletSummarySerializer(),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)


class WalletSummaryAPI(APIView):
    """Enhanced wallet summary with pending/available breakdown."""
    
    @extend_schema(
        tags=["Wallet"],
        summary="Get comprehensive wallet summary",
        responses={200: WalletSummaryEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.view_wallet"))
    def get(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store.id) != int(store_id):
            return api_response(success=False, errors=["not_found"], status_code=404)
        
        summary = WalletService.get_wallet_summary(store_id=store.id, tenant_id=tenant.id)
        return api_response(success=True, data=summary)


# ========== NEW: Journal Ledger APIs ==========

JournalEntryListDataSerializer = inline_serializer(
    name="JournalEntryListData",
    fields={
        "items": JournalEntryListSerializer(many=True),
        "count": serializers.IntegerField(),
    },
)

JournalEntryListEnvelopeSerializer = inline_serializer(
    name="JournalEntryListEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": JournalEntryListDataSerializer,
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

JournalEntryDetailEnvelopeSerializer = inline_serializer(
    name="JournalEntryDetailEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": JournalEntrySerializer(),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)


class JournalLedgerAPI(APIView):
    """List journal entries (ledger) for merchant store."""
    
    @extend_schema(
        tags=["Wallet - Accounting"],
        summary="List journal entries (merchant ledger)",
        responses={200: JournalEntryListEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.view_ledger"))
    def get(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        require_merchant(request)
        if int(store.id) != int(store_id):
            return api_response(success=False, errors=["not_found"], status_code=404)
        
        limit = int(request.query_params.get('limit', 100))
        entry_type = request.query_params.get('entry_type', None)
        
        query = JournalEntry.objects.filter(store_id=store.id).order_by('-created_at')
        if entry_type:
            query = query.filter(entry_type=entry_type)
        
        entries = query[:limit]
        return api_response(success=True, data={
            'items': JournalEntryListSerializer(entries, many=True).data,
            'count': query.count()
        })


class JournalEntryDetailAPI(APIView):
    """Get detailed journal entry with lines."""
    
    @extend_schema(
        tags=["Wallet - Accounting"],
        summary="Get journal entry details",
        responses={200: JournalEntryDetailEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.view_ledger"))
    def get(self, request, store_id, entry_id):
        store = require_store(request)
        tenant = require_tenant(request)
        require_merchant(request)
        if int(store.id) != int(store_id):
            return api_response(success=False, errors=["not_found"], status_code=404)
        
        try:
            entry = JournalEntry.objects.prefetch_related('lines__account').get(
                id=entry_id,
                store_id=store.id
            )
        except JournalEntry.DoesNotExist:
            return api_response(success=False, errors=["entry_not_found"], status_code=404)
        
        return api_response(success=True, data=JournalEntrySerializer(entry).data)


# ========== NEW: Fee Policy Management (Admin) ==========

FeePolicyListDataSerializer = inline_serializer(
    name="FeePolicyListData",
    fields={
        "items": FeePolicySerializer(many=True),
    },
)

FeePolicyListEnvelopeSerializer = inline_serializer(
    name="FeePolicyListEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": FeePolicyListDataSerializer,
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)

FeePolicyDetailEnvelopeSerializer = inline_serializer(
    name="FeePolicyDetailEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": FeePolicySerializer(),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)


class AdminFeePolicyListCreateAPI(APIView):
    """Admin: List and create fee policies."""
    permission_classes = [IsAdminUser]
    
    @extend_schema(
        tags=["Wallet - Admin"],
        summary="List fee policies (admin)",
        responses={200: FeePolicyListEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.view_fee_policies"))
    def get(self, request):
        store_id = request.query_params.get('store_id', None)
        plan_id = request.query_params.get('plan_id', None)
        
        query = FeePolicy.objects.filter(is_active=True).order_by('-created_at')
        
        if store_id:
            query = query.filter(store_id=int(store_id))
        if plan_id:
            query = query.filter(plan_id=int(plan_id))
        
        policies = query[:100]
        return api_response(success=True, data={
            'items': FeePolicySerializer(policies, many=True).data
        })
    
    @extend_schema(
        tags=["Wallet - Admin"],
        summary="Create fee policy (admin)",
        request=FeePolicySerializer,
        responses={
            201: FeePolicyDetailEnvelopeSerializer,
            400: ErrorEnvelopeSerializer,
        },
    )
    @method_decorator(require_permission("wallet.manage_fee_policies"))
    def post(self, request):
        serializer = FeePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()
        return api_response(
            success=True,
            data=FeePolicySerializer(policy).data,
            status_code=201
        )


class AdminFeePolicyDetailAPI(APIView):
    """Admin: Get, update, delete fee policy."""
    permission_classes = [IsAdminUser]
    
    @extend_schema(
        tags=["Wallet - Admin"],
        summary="Get fee policy details (admin)",
        responses={200: FeePolicyDetailEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.view_fee_policies"))
    def get(self, request, policy_id):
        try:
            policy = FeePolicy.objects.get(id=policy_id)
        except FeePolicy.DoesNotExist:
            return api_response(success=False, errors=["policy_not_found"], status_code=404)
        
        return api_response(success=True, data=FeePolicySerializer(policy).data)
    
    @extend_schema(
        tags=["Wallet - Admin"],
        summary="Update fee policy (admin)",
        request=FeePolicySerializer,
        responses={
            200: FeePolicyDetailEnvelopeSerializer,
            400: ErrorEnvelopeSerializer,
        },
    )
    @method_decorator(require_permission("wallet.manage_fee_policies"))
    def patch(self, request, policy_id):
        try:
            policy = FeePolicy.objects.get(id=policy_id)
        except FeePolicy.DoesNotExist:
            return api_response(success=False, errors=["policy_not_found"], status_code=404)
        
        serializer = FeePolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()
        return api_response(success=True, data=FeePolicySerializer(policy).data)
    
    @extend_schema(
        tags=["Wallet - Admin"],
        summary="Delete (deactivate) fee policy (admin)",
        responses={200: FeePolicyDetailEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.manage_fee_policies"))
    def delete(self, request, policy_id):
        try:
            policy = FeePolicy.objects.get(id=policy_id)
        except FeePolicy.DoesNotExist:
            return api_response(success=False, errors=["policy_not_found"], status_code=404)
        
        policy.is_active = False
        policy.save(update_fields=['is_active'])
        return api_response(success=True, data=FeePolicySerializer(policy).data)


# ========== NEW: Payment Allocation Query API ==========

PaymentAllocationDataSerializer = inline_serializer(
    name="PaymentAllocationData",
    fields={
        "allocation": PaymentAllocationSerializer(),
    },
)

PaymentAllocationEnvelopeSerializer = inline_serializer(
    name="PaymentAllocationEnvelope",
    fields={
        "success": serializers.BooleanField(),
        "data": PaymentAllocationDataSerializer,
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)


class OrderPaymentAllocationAPI(APIView):
    """Get payment allocation (fee split) for an order."""
    
    @extend_schema(
        tags=["Wallet - Accounting"],
        summary="Get order payment allocation",
        responses={200: PaymentAllocationEnvelopeSerializer},
    )
    @method_decorator(require_permission("wallet.view_allocations"))
    def get(self, request, store_id, order_id):
        store = require_store(request)
        tenant = require_tenant(request)
        require_merchant(request)
        if int(store.id) != int(store_id):
            return api_response(success=False, errors=["not_found"], status_code=404)
        
        try:
            allocation = PaymentAllocation.objects.get(store_id=store.id, order_id=order_id)
        except PaymentAllocation.DoesNotExist:
            return api_response(success=False, errors=["allocation_not_found"], status_code=404)
        
        return api_response(success=True, data={
            'allocation': PaymentAllocationSerializer(allocation).data
        })
