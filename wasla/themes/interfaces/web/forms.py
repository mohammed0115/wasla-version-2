from django import forms


class BrandingForm(forms.Form):
    theme_code = forms.CharField(required=False, max_length=50)
    logo_file = forms.ImageField(required=False)
    primary_color = forms.CharField(required=False, max_length=7)
    secondary_color = forms.CharField(required=False, max_length=7)
    accent_color = forms.CharField(required=False, max_length=7)
    font_family = forms.CharField(required=False, max_length=80)
