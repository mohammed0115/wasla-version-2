"""
Merchant dashboard views for wallet management.
Provides templates context for merchants to view balance, transactions, and withdrawals.
"""
from decimal import Decimal
from django.views.generic import TemplateView, ListView, FormView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.db.models import Q, Sum
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

from apps.stores.models import Store
from apps.orders.models import Order
from .models import Wallet, WalletTransaction, WithdrawalRequest, JournalEntry
from .services.wallet_service import WalletService
from .forms import WithdrawalRequestForm


class MerchantWalletMixin(LoginRequiredMixin):
    """
    Mixin to ensure user has access to a store's wallet.
    Sets the store object in the view context.
    """
    
    def get_store(self):
        """Get the merchant's store."""
        store_id = self.kwargs.get('store_id')
        return get_object_or_404(Store, id=store_id, owner=self.request.user)
    
    def get_wallet(self):
        """Get the store's wallet."""
        store = self.get_store()
        return get_object_or_404(Wallet, store=store)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.get_store()
        context['wallet'] = self.get_wallet()
        context['currency'] = 'USD'  # TODO: Get from store settings
        return context


class WalletSummaryView(MerchantWalletMixin, TemplateView):
    """
    Merchant wallet dashboard summary.
    Shows available balance, pending balance, total balance.
    Displays recent transactions and pending withdrawals.
    """
    template_name = 'dashboard/wallet/summary.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = context['store']
        wallet = context['wallet']
        
        # Get recent journal entries (last 10)
        recent_entries = JournalEntry.objects.filter(
            store=store
        ).order_by('-created_at')[:10]
        
        # Get pending withdrawals
        pending_withdrawals = WithdrawalRequest.objects.filter(
            store=store,
            status__in=['pending', 'approved']
        ).order_by('-requested_at')[:5]
        
        # Calculate effective available (available - pending withdrawals)
        pending_amount = pending_withdrawals.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        effective_available = wallet.available_balance - pending_amount
        
        context.update({
            'recent_entries': recent_entries,
            'pending_withdrawals': pending_withdrawals,
            'effective_available': max(Decimal('0.00'), effective_available),
        })
        
        return context


class WalletLedgerView(MerchantWalletMixin, ListView):
    """
    Full journal ledger view with filtering.
    Shows all transactions with double-entry details.
    """
    template_name = 'dashboard/wallet/ledger.html'
    context_object_name = 'entries'
    paginate_by = 25
    
    def get_queryset(self):
        store = self.get_store()
        queryset = JournalEntry.objects.filter(store=store).order_by('-entry_date', '-created_at')
        
        # Filter by entry type
        entry_type = self.request.GET.get('entry_type')
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(entry_date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(entry_date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['entry_types'] = [
            ('payment_captured', _('Payment Captured')),
            ('order_delivered', _('Order Delivered')),
            ('refund', _('Refund')),
            ('withdrawal', _('Withdrawal')),
            ('adjustment', _('Adjustment')),
        ]
        context['selected_entry_type'] = self.request.GET.get('entry_type', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        return context


class JournalEntryDetailView(MerchantWalletMixin, DetailView):
    """
    Detailed view of a specific journal entry with all lines.
    """
    model = JournalEntry
    template_name = 'dashboard/wallet/journal_entry_detail.html'
    context_object_name = 'entry'
    
    def get_object(self, queryset=None):
        store = self.get_store()
        entry_id = self.kwargs.get('entry_id')
        return get_object_or_404(JournalEntry, id=entry_id, store=store)


class WithdrawalRequestView(MerchantWalletMixin, FormView):
    """
    Form view for creating a new withdrawal request.
    """
    template_name = 'dashboard/wallet/withdrawal_request.html'
    form_class = WithdrawalRequestForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wallet = context['wallet']
        store = context['store']
        
        # Calculate available balance (minus pending withdrawals)
        pending_amount = WithdrawalRequest.objects.filter(
            store=store,
            status__in=['pending', 'approved']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        available_balance = wallet.available_balance
        effective_available = available_balance - pending_amount
        
        context.update({
            'available_balance': available_balance,
            'pending_balance': wallet.pending_balance,
            'effective_available': max(Decimal('0.00'), effective_available),
            'max_withdrawal_amount': max(Decimal('0.00'), effective_available),
            'min_withdrawal_amount': Decimal('10.00'),  # TODO: Get from settings
            'bank_account': getattr(store.owner, 'bank_account', None),
            'recent_withdrawals': WithdrawalRequest.objects.filter(
                store=store,
                status__in=['paid', 'approved']
            ).order_by('-requested_at')[:3]
        })
        
        return context
    
    def form_valid(self, form):
        store = self.get_store()
        
        # Create withdrawal request
        withdrawal = WalletService.request_withdrawal(
            store=store,
            amount=form.cleaned_data['amount'],
            note=form.cleaned_data.get('note', ''),
            requested_by=self.request.user
        )
        
        messages.success(
            self.request,
            _('Withdrawal request submitted successfully. Reference: {}').format(
                withdrawal.reference_code
            )
        )
        
        return redirect('wallet:dashboard_wallet_withdrawals', store_id=store.id)
    
    def get_success_url(self):
        return reverse_lazy('wallet:dashboard_wallet_withdrawals', kwargs={'store_id': self.get_store().id})


class WithdrawalsListView(MerchantWalletMixin, ListView):
    """
    List view for all withdrawal requests for a merchant.
    Shows history with status and filters.
    """
    template_name = 'dashboard/wallet/withdrawals.html'
    context_object_name = 'withdrawals'
    paginate_by = 20
    
    def get_queryset(self):
        store = self.get_store()
        queryset = WithdrawalRequest.objects.filter(store=store).order_by('-requested_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = context['store']
        wallet = context['wallet']
        
        # Calculate totals
        pending_withdrawals = WithdrawalRequest.objects.filter(
            store=store,
            status__in=['pending', 'approved']
        )
        paid_withdrawals = WithdrawalRequest.objects.filter(
            store=store,
            status='paid'
        )
        
        pending_amount = pending_withdrawals.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_withdrawn = paid_withdrawals.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        effective_available = wallet.available_balance - pending_amount
        
        context.update({
            'pending_count': pending_withdrawals.count(),
            'effective_available': max(Decimal('0.00'), effective_available),
            'total_withdrawn': total_withdrawn,
            'statuses': [
                ('all', _('All')),
                ('pending', _('Pending')),
                ('approved', _('Approved')),
                ('paid', _('Paid')),
                ('rejected', _('Rejected')),
            ],
            'selected_status': self.request.GET.get('status', 'all'),
        })
        
        return context


# API Context Providers (for use in API responses alongside template rendering)

def get_wallet_summary_context(store):
    """
    Helper function to get wallet summary context.
    Used by both template views and API views.
    """
    wallet = Wallet.objects.get(store=store)
    
    recent_entries = JournalEntry.objects.filter(
        store=store
    ).order_by('-created_at')[:10]
    
    pending_withdrawals = WithdrawalRequest.objects.filter(
        store=store,
        status__in=['pending', 'approved']
    ).order_by('-requested_at')[:5]
    
    pending_amount = pending_withdrawals.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    return {
        'wallet': wallet,
        'recent_entries': recent_entries,
        'pending_withdrawals': pending_withdrawals,
        'effective_available': max(Decimal('0.00'), wallet.available_balance - pending_amount),
    }
