"""
Forms for the billing web interface.

This module defines Django forms for:
- Payment method management
- Plan changes
- Invoice actions
- Grace period requests
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models_billing import PaymentMethod, BillingPlan


class PaymentMethodForm(forms.Form):
    """
    Form for adding or updating a payment method.
    Supports credit card and bank account payment methods.
    """
    
    # Payment method type
    METHOD_TYPE_CHOICES = [
        ('card', 'Credit/Debit Card'),
        ('bank', 'Bank Account'),
    ]
    
    method_type = forms.ChoiceField(
        choices=METHOD_TYPE_CHOICES,
        widget=forms.RadioSelect,
        label='Payment Method Type',
        help_text='Select how you would like to pay'
    )
    
    # Credit Card Fields
    card_number = forms.CharField(
        max_length=19,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '1234 5678 9012 3456',
            'data-mask': 'card',
            'class': 'form-control',
            'autocomplete': 'cc-number',
        }),
        label='Card Number',
        help_text='16 digits without spaces or hyphens'
    )
    
    cardholder_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'John Doe',
            'class': 'form-control',
            'autocomplete': 'cc-name',
        }),
        label='Cardholder Name',
    )
    
    expiry_date = forms.CharField(
        max_length=5,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'MM/YY',
            'data-mask': 'expiry',
            'class': 'form-control',
            'autocomplete': 'cc-exp',
        }),
        label='Expiry Date',
        help_text='Month/Year (MM/YY)'
    )
    
    cvc = forms.CharField(
        max_length=4,
        required=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': '123',
            'data-mask': 'cvc',
            'class': 'form-control',
            'autocomplete': 'cc-csc',
        }),
        label='CVV/CVC',
        help_text='3 or 4 digit security code'
    )
    
    # Bank Account Fields
    account_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '1234567890',
            'class': 'form-control',
        }),
        label='Account Number',
        help_text='Bank account number without hyphens'
    )
    
    bank_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Your Bank Name',
            'class': 'form-control',
        }),
        label='Bank Name',
    )
    
    # Additional options
    save_for_later = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Save this payment method for future payments'
    )
    
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='I authorize Wasla to charge this payment method for my subscription'
    )
    
    def clean(self):
        """
        Validate that appropriate fields are filled based on payment method type.
        """
        cleaned_data = super().clean()
        method_type = cleaned_data.get('method_type')
        
        if method_type == 'card':
            # Card validation
            card_number = cleaned_data.get('card_number', '').replace(' ', '')
            cardholder_name = cleaned_data.get('cardholder_name', '').strip()
            expiry_date = cleaned_data.get('expiry_date', '').strip()
            cvc = cleaned_data.get('cvc', '').strip()
            
            if not card_number:
                self.add_error('card_number', 'Card number is required')
            elif not self._validate_card_number(card_number):
                self.add_error('card_number', 'Invalid card number format')
            
            if not cardholder_name:
                self.add_error('cardholder_name', 'Cardholder name is required')
            
            if not expiry_date:
                self.add_error('expiry_date', 'Expiry date is required')
            elif not self._validate_expiry_date(expiry_date):
                self.add_error('expiry_date', 'Invalid expiry date (use MM/YY format)')
            
            if not cvc:
                self.add_error('cvc', 'CVV/CVC is required')
            elif not cvc.isdigit() or len(cvc) < 3:
                self.add_error('cvc', 'Invalid CVV/CVC')
        
        elif method_type == 'bank':
            # Bank account validation
            account_number = cleaned_data.get('account_number', '').strip()
            bank_name = cleaned_data.get('bank_name', '').strip()
            
            if not account_number:
                self.add_error('account_number', 'Account number is required')
            elif not account_number.isdigit():
                self.add_error('account_number', 'Account number must contain only digits')
            
            if not bank_name:
                self.add_error('bank_name', 'Bank name is required')
        
        return cleaned_data
    
    @staticmethod
    def _validate_card_number(card_number):
        """Validate card number using Luhn algorithm."""
        if not card_number.isdigit():
            return False
        
        if len(card_number) < 13 or len(card_number) > 19:
            return False
        
        # Luhn algorithm
        def luhn_checksum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10
        
        return luhn_checksum(card_number) == 0
    
    @staticmethod
    def _validate_expiry_date(expiry_date):
        """Validate expiry date format and ensure it's not expired."""
        import datetime
        
        if '/' not in expiry_date:
            return False
        
        try:
            parts = expiry_date.split('/')
            if len(parts) != 2:
                return False
            
            month, year = int(parts[0]), int(parts[1])
            
            # Validate month
            if month < 1 or month > 12:
                return False
            
            # Validate year (assuming 2-digit year in 21st century)
            if year < 24 or year > 99:  # 2024-2099
                return False
            
            # Check if expired
            current_year = datetime.datetime.now().year % 100
            current_month = datetime.datetime.now().month
            
            if year < current_year or (year == current_year and month < current_month):
                return False
            
            return True
        except (ValueError, IndexError):
            return False


class PlanChangeForm(forms.Form):
    """
    Form for changing subscription plan.
    """
    
    new_plan_id = forms.UUIDField(
        widget=forms.HiddenInput(),
        label='New Plan'
    )
    
    confirm_change = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='I confirm this plan change'
    )
    
    def __init__(self, *args, available_plans=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if available_plans:
            self.available_plan_ids = [p.id for p in available_plans]
    
    def clean(self):
        """
        Validate that the selected plan exists and is available.
        """
        cleaned_data = super().clean()
        new_plan_id = cleaned_data.get('new_plan_id')
        
        if new_plan_id and hasattr(self, 'available_plan_ids'):
            if new_plan_id not in self.available_plan_ids:
                raise ValidationError(
                    _('Selected plan is not available.'),
                    code='invalid_plan'
                )
        
        return cleaned_data


class InvoicePaymentForm(forms.Form):
    """
    Form for paying an invoice.
    """
    
    payment_method_id = forms.UUIDField(
        widget=forms.HiddenInput(),
        label='Payment Method'
    )
    
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.HiddenInput(),
        label='Amount'
    )
    
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='I authorize this payment'
    )
    
    def clean(self):
        """Validate payment information."""
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        
        if amount and amount <= 0:
            raise ValidationError(
                _('Payment amount must be greater than zero.'),
                code='invalid_amount'
            )
        
        return cleaned_data


class GracePeriodRequestForm(forms.Form):
    """
    Form for requesting a grace period extension.
    """
    
    DAYS_CHOICES = [
        (3, '3 days'),
        (5, '5 days'),
        (7, '7 days'),
        (14, '14 days'),
    ]
    
    requested_days = forms.ChoiceField(
        choices=DAYS_CHOICES,
        widget=forms.RadioSelect,
        label='How many additional days do you need?',
    )
    
    reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Please tell us why you need more time (optional)',
            'class': 'form-control',
        }),
        label='Reason (optional)',
        help_text='Help us understand your situation'
    )
    
    def clean_requested_days(self):
        """Validate requested days."""
        requested_days = self.cleaned_data.get('requested_days')
        try:
            days = int(requested_days)
            if days not in [3, 5, 7, 14]:
                raise ValidationError(
                    _('Please select a valid duration.'),
                    code='invalid_days'
                )
            return days
        except (ValueError, TypeError):
            raise ValidationError(
                _('Invalid duration selected.'),
                code='invalid_days'
            )


class SubscriptionCancellationForm(forms.Form):
    """
    Form for cancelling a subscription.
    """
    
    CANCELLATION_REASONS = [
        ('too_expensive', 'Too expensive'),
        ('not_needed', 'No longer needed'),
        ('poor_support', 'Poor customer support'),
        ('switching_service', 'Switching to another service'),
        ('technical_issues', 'Technical issues'),
        ('other', 'Other reason'),
    ]
    
    reason = forms.ChoiceField(
        choices=CANCELLATION_REASONS,
        widget=forms.RadioSelect,
        label='Why are you cancelling?',
        help_text='Your feedback helps us improve'
    )
    
    additional_feedback = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Please provide additional feedback (optional)',
            'class': 'form-control',
        }),
        label='Additional feedback (optional)',
    )
    
    confirm_cancellation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='I understand that my subscription will be cancelled at the end of the current billing period'
    )


class InvoiceFilterForm(forms.Form):
    """
    Form for filtering invoices.
    """
    
    STATUS_CHOICES = [
        ('all', 'All Statuses'),
        ('issued', 'Issued'),
        ('overdue', 'Overdue'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        label='Status'
    )
    
    overdue_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Show only overdue invoices'
    )
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search invoice number...',
            'class': 'form-control',
        }),
        label='Search'
    )
