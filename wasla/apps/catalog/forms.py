"""Forms for product and variant management in merchant dashboard."""

from django import forms
from django.forms import inlineformset_factory, modelformset_factory

from apps.catalog.models import Category, Product, ProductOption, ProductOptionGroup, ProductVariant


class ProductForm(forms.ModelForm):
    """Form for product creation/editing."""

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
        label="Categories",
    )

    class Meta:
        model = Product
        fields = ["sku", "name", "price", "description_ar", "description_en", "is_active"]
        widgets = {
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. TEE-BASE"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Product name"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "description_ar": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "description_en": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, store_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store_id:
            self.fields["categories"].queryset = Category.objects.filter(store_id__in=[0, int(store_id)]).order_by("name")
        else:
            self.fields["categories"].queryset = Category.objects.filter(store_id=0).order_by("name")


class ProductOptionGroupForm(forms.ModelForm):
    """Form for product option group (Color, Size, etc)."""

    class Meta:
        model = ProductOptionGroup
        fields = ["name", "is_required", "position"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Color, Size, etc"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }


class ProductOptionForm(forms.ModelForm):
    """Form for individual option value (Red, Blue, Small, Large, etc)."""

    class Meta:
        model = ProductOption
        fields = ["value"]
        widgets = {
            "value": forms.TextInput(attrs={"class": "form-control", "placeholder": "Option value"}),
        }


class ProductVariantForm(forms.ModelForm):
    """Form for product variant (specific color+size combination)."""

    # M2M field for options
    options = forms.ModelMultipleChoiceField(
        queryset=ProductOption.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Options",
    )

    class Meta:
        model = ProductVariant
        fields = ["sku", "price_override", "stock_quantity", "is_active", "options"]
        widgets = {
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. TEE-RED-M"}),
            "price_override": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.01", "placeholder": "Leave blank to use product price"}
            ),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, store_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store_id:
            # Filter options to only show those from this store's option groups
            self.fields["options"].queryset = ProductOption.objects.filter(group__store_id=store_id)


# Formsets for inline management
ProductOptionFormSet = inlineformset_factory(
    ProductOptionGroup,
    ProductOption,
    form=ProductOptionForm,
    extra=1,
    can_delete=True,
)

ProductVariantFormSet = modelformset_factory(
    ProductVariant,
    form=ProductVariantForm,
    extra=1,
    can_delete=True,
)
