from django.contrib import admin

from ai.models import AIProductEmbedding, AIRequestLog


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "feature", "provider", "status", "latency_ms", "created_at")
    list_filter = ("feature", "status", "provider")
    search_fields = ("store_id",)


@admin.register(AIProductEmbedding)
class AIProductEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "product_id", "provider", "updated_at")
    list_filter = ("provider",)
    search_fields = ("store_id", "product_id")
