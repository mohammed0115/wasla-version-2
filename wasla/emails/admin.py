from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied

from emails.application.services.crypto import CredentialCrypto
from emails.models import EmailLog, GlobalEmailSettings, GlobalEmailSettingsAuditLog


class GlobalEmailSettingsAdminForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Leave empty to keep existing password. Required for SMTP/SendGrid/Mailgun.",
        label="Password / API Key",
    )

    class Meta:
        model = GlobalEmailSettings
        fields = ("provider", "host", "port", "username", "password", "from_email", "use_tls", "enabled")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.password_encrypted:
            self.fields["password"].initial = "********"

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and GlobalEmailSettings.objects.exists():
            raise forms.ValidationError("Only one GlobalEmailSettings row is allowed.")
        return cleaned

    def clean_password(self):
        value = (self.cleaned_data.get("password") or "").strip()
        if value == "********":
            return None
        return value


@admin.register(GlobalEmailSettings)
class GlobalEmailSettingsAdmin(admin.ModelAdmin):
    form = GlobalEmailSettingsAdminForm
    list_display = ("provider", "from_email", "enabled", "updated_at")
    list_filter = ("provider", "enabled")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied
        password = form.cleaned_data.get("password")
        if password is None:
            pass
        elif password == "":
            obj.password_encrypted = ""
        else:
            obj.password_encrypted = CredentialCrypto.encrypt_text(password)
        super().save_model(request, obj, form, change)
        GlobalEmailSettingsAuditLog.objects.create(
            action="updated" if change else "created",
            actor=getattr(request.user, "username", "") or "superadmin",
            metadata={
                "provider": obj.provider,
                "enabled": obj.enabled,
                "from_email": obj.from_email,
                "host": obj.host,
                "port": obj.port,
                "username": obj.username,
            },
        )


@admin.register(GlobalEmailSettingsAuditLog)
class GlobalEmailSettingsAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("actor",)
    ordering = ("-created_at",)
    readonly_fields = ("action", "actor", "created_at", "metadata")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "to_email", "template_key", "status", "provider", "created_at", "sent_at")
    list_filter = ("status", "provider", "template_key")
    search_fields = ("tenant__slug", "to_email", "subject", "idempotency_key", "provider_message_id")
    ordering = ("-created_at",)
