"""
Forms for wallet operations.
"""
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import WithdrawalRequest


class WithdrawalRequestForm(forms.ModelForm):
    """
    Form for creating a new withdrawal request.
    """
    amount = forms.DecimalField(
        label=_('Withdrawal Amount'),
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '0.00',
            'step': '0.01',
        })
    )
    
    note = forms.CharField(
        label=_('Note (Optional)'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Add a note for this withdrawal request...'),
        })
    )
    
    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'note']
    
    def clean_amount(self):
        """Validate withdrawal amount."""
        amount = self.cleaned_data.get('amount')
        
        if amount and amount <= Decimal('0.00'):
            raise ValidationError(_('Withdrawal amount must be greater than zero.'))
        
        return amount
    
    def clean_note(self):
        """Clean and validate note field."""
        note = self.cleaned_data.get('note', '').strip()
        
        if note and len(note) > 1000:
            raise ValidationError(_('Note cannot exceed 1000 characters.'))
        
        return note
