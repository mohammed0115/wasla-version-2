"""
Onboarding flow forms for plan selection, subdomain, and payment method.
"""

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.subscriptions.models import SubscriptionPlan
from apps.tenants.services.domain_resolution import validate_subdomain


class PlanSelectForm(forms.Form):
    """Form for selecting a subscription plan during onboarding."""
    
    plan_id = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        label="Select Plan",
        empty_label=None,
        help_text="Choose a plan to get started"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order plans by configured sort order, then price
        self.fields['plan_id'].queryset = (
            SubscriptionPlan.objects.filter(is_active=True)
            .order_by('sort_order', 'price')
        )


class SubdomainSelectForm(forms.Form):
    """Form for selecting a subdomain during onboarding."""

    _base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com") or "w-sala.com").strip().lower()

    subdomain = forms.CharField(
        max_length=30,
        min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'mystore',
            'autocomplete': 'off',
            'pattern': '[a-z0-9-]+',
            'title': 'Use only letters, numbers, hyphen',
            'inputmode': 'latin',
        }),
        label="Store Subdomain",
        help_text=f"Your store will be at: subdomain.{_base_domain}"
    )
    
    def clean_subdomain(self):
        """Validate subdomain format and uniqueness."""
        subdomain = self.cleaned_data.get('subdomain')
        if not subdomain:
            return subdomain
        
        is_valid, error_msg = validate_subdomain(subdomain)
        if not is_valid:
            raise ValidationError(error_msg)
        
        return subdomain.lower()


class PaymentMethodSelectForm(forms.Form):
    """Form for selecting payment method during checkout (PAID plans only)."""
    
    PAYMENT_METHOD_CHOICES = [
        ('stripe', 'Stripe - Credit/Debit Card'),
        ('tap', 'Tap - Arab Payments Platform'),
        ('manual', 'Manual Bank Transfer'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect,
        label="Payment Method",
        help_text="Select how you would like to pay"
    )


class ManualPaymentUploadForm(forms.Form):
    """Form for uploading proof of payment for manual transfers."""
    
    reference = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Transfer reference or receipt number',
        }),
        label="Transfer Reference/Receipt Number",
        help_text="Bank transfer reference number from your receipt"
    )
    
    receipt_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.pdf',
        }),
        label="Receipt Image or PDF (Optional)",
        help_text="Upload a screenshot or PDF of your transfer receipt"
    )
    
    notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Any additional information about your payment...',
        }),
        label="Additional Notes",
        help_text="Tell us anything relevant about your payment"
    )
