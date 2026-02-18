from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.catalog.models import Category
from apps.tenants.domain.errors import StoreDomainError, StoreValidationError
from apps.tenants.domain.policies import (
    validate_domain_format,
    validate_hex_color,
    validate_store_name,
    validate_tenant_slug,
)
from apps.tenants.domain.setup_policies import (
    PAYMENT_MODE_CHOICES,
    PAYMENT_MODE_DUMMY,
    PAYMENT_MODE_GATEWAY,
    PAYMENT_MODE_MANUAL,
    FULFILLMENT_MODE_CHOICES,
    validate_payment_settings,
    validate_shipping_settings,
)


class StoreInfoSetupForm(forms.Form):
    name = forms.CharField(max_length=200, label="Store name")
    slug = forms.CharField(max_length=63, label="Store slug (subdomain)")

    currency = forms.CharField(initial="SAR", max_length=10, required=False, widget=forms.HiddenInput)
    language = forms.CharField(initial="ar", max_length=10, required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["name", "slug"]:
            self.fields[field_name].widget.attrs.setdefault("class", "form-control")

    def clean_name(self) -> str:
        try:
            return validate_store_name(self.cleaned_data.get("name", ""))
        except StoreDomainError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_slug(self) -> str:
        raw = self.cleaned_data.get("slug", "")
        try:
            return validate_tenant_slug(raw)
        except StoreDomainError as exc:
            raise forms.ValidationError(str(exc)) from exc


class StoreSettingsForm(forms.Form):
    name = forms.CharField(max_length=200, label="Store name")
    slug = forms.CharField(max_length=63, label="Store slug (subdomain)")

    logo = forms.ImageField(required=False, label="Logo")
    primary_color = forms.CharField(required=False, max_length=7, label="Primary color")
    secondary_color = forms.CharField(required=False, max_length=7, label="Secondary color")

    currency = forms.CharField(initial="SAR", max_length=10, required=False)
    language = forms.CharField(initial="ar", max_length=10, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            if field_name in {"logo"}:
                self.fields[field_name].widget.attrs.setdefault("class", "form-control")
            elif field_name in {"currency", "language"}:
                self.fields[field_name].widget.attrs.setdefault("class", "form-control")
            else:
                self.fields[field_name].widget.attrs.setdefault("class", "form-control")

    def clean_name(self) -> str:
        try:
            return validate_store_name(self.cleaned_data.get("name", ""))
        except StoreDomainError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_slug(self) -> str:
        raw = self.cleaned_data.get("slug", "")
        try:
            return validate_tenant_slug(raw)
        except StoreDomainError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_primary_color(self) -> str:
        try:
            return validate_hex_color(self.cleaned_data.get("primary_color", ""))
        except StoreDomainError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_secondary_color(self) -> str:
        try:
            return validate_hex_color(self.cleaned_data.get("secondary_color", ""))
        except StoreDomainError as exc:
            raise forms.ValidationError(str(exc)) from exc


class CustomDomainForm(forms.Form):
    domain = forms.CharField(max_length=255, label="Custom domain")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["domain"].widget.attrs.setdefault("class", "form-control")
        self.fields["domain"].widget.attrs.setdefault("placeholder", "mystore.com")

    def clean_domain(self) -> str:
        raw = self.cleaned_data.get("domain", "")
        try:
            return validate_domain_format(raw)
        except StoreDomainError as exc:
            raise forms.ValidationError(str(exc)) from exc


class FirstProductForm(forms.Form):
    sku = forms.CharField(max_length=64, label="SKU")
    name = forms.CharField(max_length=255, label="Product name")
    price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Price",
    )
    quantity = forms.IntegerField(min_value=0, initial=1, label="Stock quantity")
    image = forms.ImageField(required=False, label="Image")
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Categories",
    )

    def __init__(self, *args, store_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if store_id is not None:
            self.fields["categories"].queryset = Category.objects.filter(store_id=store_id).order_by(
                "name"
            )

        for field_name in ["sku", "name", "price", "quantity", "image"]:
            self.fields[field_name].widget.attrs.setdefault("class", "form-control")
        self.fields["categories"].widget.attrs.setdefault("class", "form-check-input")


class PaymentSettingsForm(forms.Form):
    payment_mode = forms.ChoiceField(
        choices=PAYMENT_MODE_CHOICES,
        initial=PAYMENT_MODE_MANUAL,
        label="Payment mode",
    )
    provider_name = forms.CharField(required=False, max_length=50, label="Provider name (gateway)")
    merchant_key = forms.CharField(required=False, max_length=255, label="Merchant key / API key")
    webhook_secret = forms.CharField(required=False, max_length=255, label="Webhook secret")
    is_enabled = forms.BooleanField(required=False, initial=True, label="Enabled")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["payment_mode", "provider_name", "merchant_key", "webhook_secret"]:
            self.fields[field_name].widget.attrs.setdefault("class", "form-control")
        self.fields["payment_mode"].widget.attrs.setdefault("class", "form-select")
        self.fields["is_enabled"].widget.attrs.setdefault("class", "form-check-input")

    def clean(self):
        cleaned = super().clean()
        try:
            normalized = validate_payment_settings(
                payment_mode=cleaned.get("payment_mode") or "",
                provider_name=cleaned.get("provider_name") or "",
                merchant_key=cleaned.get("merchant_key") or "",
                webhook_secret=cleaned.get("webhook_secret") or "",
                is_enabled=cleaned.get("is_enabled", False),
            )
        except StoreValidationError as exc:
            if exc.field:
                self.add_error(exc.field, str(exc))
            else:
                self.add_error(None, str(exc))
            return cleaned

        cleaned.update(normalized)
        return cleaned


class ShippingSettingsForm(forms.Form):
    fulfillment_mode = forms.ChoiceField(
        choices=FULFILLMENT_MODE_CHOICES,
        initial="pickup",
        label="Fulfillment mode",
    )
    origin_city = forms.CharField(required=False, max_length=100, label="Origin city")
    delivery_fee_flat = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        label="Flat delivery fee",
    )
    free_shipping_threshold = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        label="Free shipping threshold",
    )
    is_enabled = forms.BooleanField(required=False, initial=True, label="Enabled")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["origin_city", "delivery_fee_flat", "free_shipping_threshold"]:
            self.fields[field_name].widget.attrs.setdefault("class", "form-control")
        self.fields["fulfillment_mode"].widget.attrs.setdefault("class", "form-select")
        self.fields["is_enabled"].widget.attrs.setdefault("class", "form-check-input")

    def clean(self):
        cleaned = super().clean()
        try:
            normalized = validate_shipping_settings(
                fulfillment_mode=cleaned.get("fulfillment_mode") or "",
                origin_city=cleaned.get("origin_city") or "",
                delivery_fee_flat=cleaned.get("delivery_fee_flat"),
                free_shipping_threshold=cleaned.get("free_shipping_threshold"),
                is_enabled=cleaned.get("is_enabled", False),
            )
        except StoreValidationError as exc:
            if exc.field:
                self.add_error(exc.field, str(exc))
            else:
                self.add_error(None, str(exc))
            return cleaned

        cleaned.update(normalized)
        return cleaned
