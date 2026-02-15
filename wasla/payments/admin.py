from django.contrib import admin

from payments.models import PaymentProviderSettings


@admin.register(PaymentProviderSettings)
class PaymentProviderSettingsAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider_code", "display_name", "is_enabled", "updated_at")
    list_filter = ("is_enabled", "provider_code")
    search_fields = ("tenant__name", "tenant__slug", "provider_code", "display_name")

    def has_module_permission(self, request) -> bool:
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None) -> bool:
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request) -> bool:
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None) -> bool:
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None) -> bool:
        return bool(request.user and request.user.is_superuser)
