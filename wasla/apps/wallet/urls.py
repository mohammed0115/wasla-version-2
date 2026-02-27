
from django.urls import path
try:
    from .views.api import (
        WalletDetailAPI,
        WalletSummaryAPI,
        MerchantWithdrawalRequestAPI,
        JournalLedgerAPI,
        JournalEntryDetailAPI,
        OrderPaymentAllocationAPI,
        AdminApproveWithdrawalAPI,
        AdminMarkWithdrawalPaidAPI,
        AdminRejectWithdrawalAPI,
        WalletLedgerIntegrityAPI,
        AdminFeePolicyListCreateAPI,
        AdminFeePolicyDetailAPI,
    )
    from .views.merchant import (
        WalletSummaryView,
        WalletLedgerView,
        JournalEntryDetailView,
        WithdrawalRequestView,
        WithdrawalsListView,
    )
except Exception:
    urlpatterns = []
else:
    urlpatterns = [
    # ========== Merchant Dashboard Views ==========
    path("dashboard/stores/<int:store_id>/wallet/", WalletSummaryView.as_view(), name="dashboard_wallet_summary"),
    path("dashboard/stores/<int:store_id>/wallet/ledger/", WalletLedgerView.as_view(), name="dashboard_wallet_ledger"),
    path("dashboard/stores/<int:store_id>/wallet/ledger/<int:entry_id>/", JournalEntryDetailView.as_view(), name="dashboard_wallet_ledger_detail"),
    path("dashboard/stores/<int:store_id>/wallet/withdrawal/request/", WithdrawalRequestView.as_view(), name="dashboard_wallet_withdrawal_request"),
    path("dashboard/stores/<int:store_id>/wallet/withdrawals/", WithdrawalsListView.as_view(), name="dashboard_wallet_withdrawals"),
    
    # ========== Merchant Wallet APIs ==========
    path("stores/<int:store_id>/wallet/", WalletDetailAPI.as_view(), name="wallet-detail"),
    path("stores/<int:store_id>/wallet/summary/", WalletSummaryAPI.as_view(), name="wallet-summary"),
    path("stores/<int:store_id>/wallet/withdrawals/", MerchantWithdrawalRequestAPI.as_view(), name="wallet-withdrawals"),
    
    # ========== Merchant Ledger APIs ==========
    path("stores/<int:store_id>/wallet/ledger/", JournalLedgerAPI.as_view(), name="wallet-ledger"),
    path("stores/<int:store_id>/wallet/ledger/<int:entry_id>/", JournalEntryDetailAPI.as_view(), name="wallet-ledger-detail"),
    path("stores/<int:store_id>/wallet/orders/<int:order_id>/allocation/", OrderPaymentAllocationAPI.as_view(), name="order-allocation"),
    
    # ========== Admin Withdrawal APIs ==========
    path("admin/wallet/withdrawals/<int:withdrawal_id>/approve/", AdminApproveWithdrawalAPI.as_view(), name="admin-withdrawal-approve"),
    path("admin/wallet/withdrawals/<int:withdrawal_id>/reject/", AdminRejectWithdrawalAPI.as_view(), name="admin-withdrawal-reject"),
    path("admin/wallet/withdrawals/<int:withdrawal_id>/paid/", AdminMarkWithdrawalPaidAPI.as_view(), name="admin-withdrawal-paid"),
    
    # ========== Admin System APIs ==========
    path("admin/wallet/ledger-integrity/<int:store_id>/", WalletLedgerIntegrityAPI.as_view(), name="admin-ledger-integrity"),
    
    # ========== Admin Fee Policy APIs ==========
    path("admin/wallet/fee-policies/", AdminFeePolicyListCreateAPI.as_view(), name="admin-fee-policies"),
    path("admin/wallet/fee-policies/<int:policy_id>/", AdminFeePolicyDetailAPI.as_view(), name="admin-fee-policy-detail"),
    ]
