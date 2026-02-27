from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.subscriptions.models import SubscriptionPlan, PaymentTransaction
from apps.tenants.models import Tenant


class ManualPaymentForm(forms.Form):
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.filter(is_active=True).order_by("name"),
        label="Tenant",
    )
    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(is_active=True).order_by("price", "name", "billing_cycle"),
        label="Plan",
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Amount",
    )
    currency = forms.CharField(max_length=10, initial="SAR", label="Currency", required=False)
    reference = forms.CharField(max_length=120, required=False, label="Reference")
    status = forms.ChoiceField(
        choices=PaymentTransaction.STATUS_CHOICES,
        initial=PaymentTransaction.STATUS_PENDING,
        label="Status",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")
