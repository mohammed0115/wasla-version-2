from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

def input_attrs(extra=None):
    base = {"class": "salla-input", "autocomplete": "off"}
    if extra:
        base.update(extra)
    return base

def select_attrs(extra=None):
    base = {"class": "salla-select"}
    if extra:
        base.update(extra)
    return base

COUNTRY_CHOICES = [
    ("SA", "السعودية"),
    ("AE", "الإمارات"),
    ("KW", "الكويت"),
    ("BH", "البحرين"),
    ("QA", "قطر"),
    ("OM", "عُمان"),
]

PHONE_COUNTRY_CHOICES = [
    ("+966", "🇸🇦 +966"),
    ("+971", "🇦🇪 +971"),
    ("+965", "🇰🇼 +965"),
    ("+973", "🇧🇭 +973"),
    ("+974", "🇶🇦 +974"),
    ("+968", "🇴🇲 +968"),
]

LEGAL_ENTITY_CHOICES = [
    ("individual", "فرد"),
    ("institution", "مؤسسة"),
    ("company", "شركة"),
    ("other", "أخرى"),
]

HAS_EXISTING_CHOICES = [
    ("yes", "نعم"),
    ("no", "لا"),
]

SELLING_CHANNEL_CHOICES = [
    ("none", "لا أبيع حالياً"),
    ("instagram", "إنستغرام"),
    ("snapchat", "سناب شات"),
    ("tiktok", "تيك توك"),
    ("whatsapp", "واتساب"),
    ("marketplace", "منصة/سوق إلكتروني"),
    ("store", "متجر إلكتروني خاص"),
]

CATEGORY_MAIN = [
    ("cosmetics", "مستحضرات التجميل والعناية"),
    ("jewelry", "مجوهرات"),
    ("agriculture", "زراع"),
    ("home_supplies", "مستلزمات المنزل"),
    ("electronics", "إلكترونيات"),
    ("accessories_gifts", "الاكسسوارات و الهدايا"),
    ("arts_music", "الفنون والموسيقى"),
    ("books_education", "الكتب والتعليم"),
    ("services", "خدمات"),
    ("health_wellness", "صحة ولياقة"),
    ("digital_products", "منتجات رقمية"),
    ("cars", "سيارات"),
    ("pets", "حيوانات"),
    ("food_restaurants", "المطاعم والمقاهي"),
    ("charity", "جمعية خيرية"),
    ("toys", "ألعاب"),
    ("medical_clinic", "عيادة طبية"),
]
SUBCATEGORY_MAP = {
    "electronics": [
        ("phones", "الهواتف الذكية ومستلزماتها"),
        ("computers", "الكمبيوترات والأجهزة المحمولة وملحقاتها"),
        ("cameras", "الكاميرات الرقمية وملحقاتها"),
        ("tvs", "التلفزيونات"),
        ("speakers", "السماعات"),
        ("home_appliances", "الأجهزة المنزلية"),
    ]
}


class RegisterForm(forms.Form):
    full_name = forms.CharField(label="الاسم", max_length=120, widget=forms.TextInput(attrs=input_attrs({"placeholder":"اسمك"})))
    email = forms.EmailField(label="البريد الإلكتروني", widget=forms.EmailInput(attrs=input_attrs({"placeholder":"name@example.com"})))
    phone_country = forms.ChoiceField(label="الدولة", choices=PHONE_COUNTRY_CHOICES, widget=forms.Select(attrs=select_attrs()))
    phone_number = forms.CharField(label="رقم الجوال", max_length=32, widget=forms.TextInput(attrs=input_attrs({"placeholder":"5XXXXXXXX"})))
    password = forms.CharField(label="كلمة المرور", widget=forms.PasswordInput(attrs=input_attrs({"placeholder":"••••••••"})))

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("هذا البريد مسجل مسبقاً.")
        return email

class LoginForm(forms.Form):
    email = forms.EmailField(label="البريد الإلكتروني", widget=forms.EmailInput(attrs=input_attrs({"placeholder":"name@example.com"})))
    password = forms.CharField(label="كلمة المرور", widget=forms.PasswordInput(attrs=input_attrs({"placeholder":"••••••••"})))

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        password = cleaned.get("password")
        if not email or not password:
            return cleaned
        user = authenticate(username=email.lower().strip(), password=password)
        if not user:
            raise ValidationError("بيانات الدخول غير صحيحة.")
        if not user.is_active:
            raise ValidationError("الحساب غير مفعّل. تحقّق من رمز التفعيل.")
        cleaned["user"] = user
        return cleaned

class OTPForm(forms.Form):
    otp_attrs = {"maxlength": "1", "inputmode": "numeric", "autocomplete": "one-time-code"}
    d1 = forms.CharField(max_length=1, widget=forms.TextInput(attrs={"class": "", **otp_attrs}))
    d2 = forms.CharField(max_length=1, widget=forms.TextInput(attrs={"class": "", **otp_attrs}))
    d3 = forms.CharField(max_length=1, widget=forms.TextInput(attrs={"class": "", **otp_attrs}))
    d4 = forms.CharField(max_length=1, widget=forms.TextInput(attrs={"class": "", **otp_attrs}))


    def code(self) -> str:
        return f"{self.cleaned_data['d1']}{self.cleaned_data['d2']}{self.cleaned_data['d3']}{self.cleaned_data['d4']}"

class PersonaCountryForm(forms.Form):
    country = forms.ChoiceField(label="اختر بلدك", choices=COUNTRY_CHOICES)

class PersonaLegalForm(forms.Form):
    legal_entity = forms.ChoiceField(label="ما هو الكيان القانوني؟", choices=LEGAL_ENTITY_CHOICES)

class PersonaExistingForm(forms.Form):
    has_existing_business = forms.ChoiceField(label="هل تجارتك قائمة؟", choices=HAS_EXISTING_CHOICES)

class PersonaChannelForm(forms.Form):
    selling_channel = forms.ChoiceField(label="أين تبيع حالياً؟", choices=SELLING_CHANNEL_CHOICES)

class PersonaCategoryMainForm(forms.Form):
    category_main = forms.ChoiceField(label="اختر نشاطك التجاري", choices=CATEGORY_MAIN)