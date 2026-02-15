from django.contrib import admin

from .models import StoreBranding, Theme


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name_key", "is_active")
    search_fields = ("code", "name_key")


@admin.register(StoreBranding)
class StoreBrandingAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "theme_code", "primary_color", "secondary_color", "accent_color", "updated_at")
    search_fields = ("store_id", "theme_code")
