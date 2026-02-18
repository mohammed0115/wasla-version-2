from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re

from .models import Store, StoreSettings


class MerchantRegistrationForm(forms.Form):
    """Form for merchant registration."""

    full_name = forms.CharField(
        max_length=255,
        required=True,
        label=_("Full Name"),
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": _("Your full name"),
            "autocomplete": "name",
        })
    )

    business_name = forms.CharField(
        max_length=255,
        required=True,
        label=_("Business Name"),
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": _("Business or store name"),
        })
    )

    phone_number = forms.CharField(
        max_length=20,
        required=True,
        label=_("Phone Number"),
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": _("+966 50 xxx xxxx"),
            "autocomplete": "tel",
        })
    )

    commercial_registration = forms.CharField(
        max_length=50,
        required=False,
        label=_("Commercial Registration"),
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": _("CR number (optional)"),
        })
    )

    agree_terms = forms.BooleanField(
        required=True,
        label=_("I agree to terms and conditions"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    def clean_phone_number(self):
        phone = self.cleaned_data["phone_number"].strip()
        # Basic validation - should start with +966 or 0
        if not re.match(r'^[\+0][0-9\s\-]{7,}$', phone):
            raise ValidationError(_("Enter a valid phone number"))
        return phone


class StoreBasicInfoForm(forms.ModelForm):
    """Form for basic store information (Step 1 of setup wizard)."""

    class Meta:
        model = Store
        fields = ["name", "description", "category", "logo"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("Store name"),
                "maxlength": "255",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "placeholder": _("Brief description of your store"),
                "rows": 4,
            }),
            "category": forms.Select(attrs={
                "class": "form-select",
            }),
            "logo": forms.FileInput(attrs={
                "class": "form-control",
                "accept": "image/*",
            }),
        }

    CATEGORY_CHOICES = [
        ("", _("Select a category")),
        ("fashion", _("Fashion & Clothing")),
        ("beauty", _("Beauty & Cosmetics")),
        ("home", _("Home & Furniture")),
        ("electronics", _("Electronics")),
        ("food", _("Food & Beverages")),
        ("sports", _("Sports & Outdoors")),
        ("toys", _("Toys & Games")),
        ("books", _("Books & Media")),
        ("handmade", _("Handmade & Crafts")),
        ("other", _("Other")),
    ]

    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        required=True,
        label=_("Business Category"),
        widget=forms.Select(attrs={"class": "form-select"})
    )


class StoreDomainForm(forms.ModelForm):
    """Form for domain configuration (Step 4 of setup wizard)."""

    class Meta:
        model = Store
        fields = ["subdomain"]
        widgets = {
            "subdomain": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("mystore"),
                "maxlength": "255",
                "pattern": "[a-z0-9-]+",
            }),
        }

    def clean_subdomain(self):
        subdomain = self.cleaned_data["subdomain"].strip().lower()
        
        # Validate format
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', subdomain) and not re.match(r'^[a-z0-9]$', subdomain):
            raise ValidationError(
                _("Subdomain can only contain lowercase letters, numbers, and hyphens. "
                  "It must start and end with a letter or number.")
            )

        # Check if already taken
        if Store.objects.filter(subdomain=subdomain).exists():
            raise ValidationError(_("This subdomain is already taken."))

        # Reserved subdomains
        reserved = {"admin", "api", "www", "mail", "ftp", "test", "demo", "staging"}
        if subdomain in reserved:
            raise ValidationError(_("This subdomain is reserved."))

        return subdomain


class StoreSettingsForm(forms.ModelForm):
    """Form for store settings."""

    class Meta:
        model = StoreSettings
        fields = [
            "notify_on_order",
            "notify_email",
            "low_stock_threshold",
            "settlement_frequency",
        ]
        widgets = {
            "notify_on_order": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notify_email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": _("Email for notifications"),
            }),
            "low_stock_threshold": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "max": "10000",
            }),
            "settlement_frequency": forms.Select(attrs={"class": "form-select"}),
        }
