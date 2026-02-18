from django.contrib import admin
from django.utils import timezone
from django.template.response import TemplateResponse
from django.urls import path

from apps.accounts.models import Profile
from apps.subscriptions.models import StoreSubscription

from .models import (
    StoreDomain,
    StorePaymentSettings,
    StoreProfile,
    StoreShippingSettings,
    Tenant,
    TenantAuditLog,
    TenantMembership,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "slug",
        "name",
        "is_active",
        "is_published",
        "currency",
        "language",
        "setup_completed",
        "setup_step",
        "activated_at",
        "deactivated_at",
    )
    list_filter = ("is_active", "currency", "language")
    search_fields = ("slug", "name", "domain", "subdomain")
    ordering = ("id",)
    exclude = ("setup_step", "setup_completed", "setup_completed_at")
    actions = ("activate_stores", "deactivate_stores")

    @admin.action(description="Activate selected stores")
    def activate_stores(self, request, queryset):
        now = timezone.now()
        queryset.update(is_active=True, activated_at=now, deactivated_at=None)

    @admin.action(description="Deactivate selected stores")
    def deactivate_stores(self, request, queryset):
        now = timezone.now()
        queryset.update(is_active=False, deactivated_at=now)


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("tenant__slug", "tenant__name", "user__username", "user__email")
    ordering = ("-id",)


@admin.register(StoreProfile)
class StoreProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "owner",
        "store_info_completed",
        "setup_step",
        "is_setup_complete",
        "created_at",
    )
    list_filter = ("store_info_completed", "setup_step", "is_setup_complete")
    search_fields = ("tenant__slug", "tenant__name", "owner__username", "owner__email")
    ordering = ("-id",)


@admin.register(StoreDomain)
class StoreDomainAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "domain", "status", "verified_at", "last_check_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("domain", "tenant__slug", "tenant__name")
    ordering = ("-id",)


@admin.register(StorePaymentSettings)
class StorePaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "mode", "provider_name", "is_enabled", "updated_at")
    list_filter = ("mode", "is_enabled")
    search_fields = ("tenant__slug", "tenant__name", "provider_name")
    ordering = ("-id",)


@admin.register(StoreShippingSettings)
class StoreShippingSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "fulfillment_mode", "origin_city", "is_enabled", "updated_at")
    list_filter = ("fulfillment_mode", "is_enabled")
    search_fields = ("tenant__slug", "tenant__name", "origin_city")
    ordering = ("-id",)


@admin.register(TenantAuditLog)
class TenantAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("tenant__slug", "actor", "details")
    ordering = ("-created_at",)


def qa_dashboard_view(request):
    """QA dashboard: verify registration→store→wizard→subscription linkage.

    Adds admin-only utilities:
    - Build/Update AI index for a store (POST).
    - Run Visual Search KPI sampling (POST).
    - Seed demo products + images for quick demos (POST).
    """
    from django.contrib import messages
    from django.core.management import call_command
    from django.http import HttpResponseRedirect
    import io as _io

    # Handle actions
    if request.method == "POST":
        action = request.POST.get("action")
        tenant_id = request.POST.get("tenant_id")
        try:
            tenant_id_int = int(tenant_id) if tenant_id else None
        except (TypeError, ValueError):
            tenant_id_int = None

        if action in {"index_products", "run_kpi"} and not tenant_id_int:
            messages.error(request, "Invalid tenant id.")
            return HttpResponseRedirect(request.path)

        if action == "index_products":
            try:
                from apps.tenants.domain.tenant_context import TenantContext
                from apps.ai.application.use_cases.index_product_embeddings import (
                    IndexProductEmbeddingsCommand,
                    IndexProductEmbeddingsUseCase,
                )

                t = Tenant.objects.get(id=tenant_id_int)
                owner_membership = (
                    TenantMembership.objects.filter(tenant=t, role="owner", is_active=True)
                    .select_related("user")
                    .first()
                )
                owner = owner_membership.user if owner_membership else None
                force = request.POST.get("force") == "1"

                cmd = IndexProductEmbeddingsCommand(
                    tenant_ctx=TenantContext(
                        tenant_id=t.id,
                        currency=getattr(t, "currency", "SAR") or "SAR",
                        user_id=getattr(owner, "id", None),
                    ),
                    force=force,
                )
                out = IndexProductEmbeddingsUseCase.execute(cmd)
                messages.success(
                    request,
                    f"Index updated for store #{t.id} ({t.slug}). Indexed={out.get('indexed')} skipped={out.get('skipped')} provider={out.get('provider')}.",
                )
            except Exception as e:
                messages.error(request, f"Indexing failed: {e}")
            return HttpResponseRedirect(request.path)

        if action == "run_kpi":
            try:
                samples = int(request.POST.get("samples") or 10)
                top_n = int(request.POST.get("top_n") or 12)
                buf = _io.StringIO()
                call_command(
                    "ai_kpi_visual_search",
                    "--store-id",
                    str(tenant_id_int),
                    "--samples",
                    str(samples),
                    "--top-n",
                    str(top_n),
                    stdout=buf,
                )
                report = (buf.getvalue() or "").strip()
                messages.success(request, f"KPI done for store #{tenant_id_int}.\n{report[:800]}")
            except Exception as e:
                messages.error(request, f"KPI failed: {e}")
            return HttpResponseRedirect(request.path)

        if action == "seed_demo":
            try:
                count = int(request.POST.get("count") or 24)
                reset = request.POST.get("reset") == "1"
                with_inventory = request.POST.get("with_inventory") == "1"
                buf = _io.StringIO()
                call_command(
                    "seed_demo_products",
                    "--store-id",
                    str(tenant_id_int),
                    "--count",
                    str(count),
                    *( ["--reset"] if reset else []),
                    *( ["--with-inventory"] if with_inventory else []),
                    stdout=buf,
                )
                report = (buf.getvalue() or "").strip()
                messages.success(request, f"Seeded demo products for store #{tenant_id_int}.\n{report[:800]}")
            except Exception as e:
                messages.error(request, f"Seeding failed: {e}")
            return HttpResponseRedirect(request.path)

        messages.warning(request, "Unknown action.")
        return HttpResponseRedirect(request.path)

    tenants_qs = (
        Tenant.objects.all()
        .prefetch_related("memberships__user__profile", "store_profile")
        .order_by("id")
    )

    subs = StoreSubscription.objects.filter(store_id__in=[t.id for t in tenants_qs]).select_related("plan")
    subs_map = {s.store_id: s for s in subs}

    rows = []
    for t in tenants_qs:
        owner_membership = next(
            (m for m in getattr(t, "memberships").all() if m.role == "owner" and m.is_active),
            None,
        )
        owner = owner_membership.user if owner_membership else None
        profile = getattr(owner, "profile", None) if owner else None
        store_profile = getattr(t, "store_profile", None)
        sub = subs_map.get(t.id)

        rows.append(
            {
                "tenant": t,
                "owner": owner,
                "profile": profile,
                "store_profile": store_profile,
                "subscription": sub,
            }
        )

    stats = {
        "tenants": tenants_qs.count(),
        "with_owner": sum(1 for r in rows if r["owner"] is not None),
        "with_subscription": sum(1 for r in rows if r["subscription"] is not None),
        "setup_completed": sum(1 for r in rows if r["tenant"].setup_completed),
    }

    return TemplateResponse(
        request,
        "admin/qa_dashboard.html",
        {
            "title": "QA Dashboard",
            "rows": rows,
            "stats": stats,
        },
    )

def _inject_qa_dashboard_url():
    """Add /admin/qa-dashboard/ under the default admin site."""
    original_get_urls = admin.site.get_urls

    def get_urls():
        urls = original_get_urls()
        custom = [
            path(
                "qa-dashboard/",
                admin.site.admin_view(qa_dashboard_view),
                name="qa-dashboard",
            )
        ]
        return custom + urls

    admin.site.get_urls = get_urls


_inject_qa_dashboard_url()
