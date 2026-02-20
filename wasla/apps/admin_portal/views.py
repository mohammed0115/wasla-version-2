from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.payments.models import PaymentAttempt, WebhookEvent
from apps.settlements.models import Invoice, InvoiceLine, SettlementRecord
from apps.stores.models import Store
from apps.tenants.models import Tenant

from .decorators import admin_permission_required
from .utils import log_admin_action


def _get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _throttle_keys(ip: str):
    return f"admin_portal:login_fail:{ip}", f"admin_portal:login_block:{ip}"


def login_view(request):
    """Staff login page with simple per-IP throttling."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('/admin-portal/')

    ip = _get_client_ip(request)
    fail_key, block_key = _throttle_keys(ip)

    if cache.get(block_key):
        return render(
            request,
            'admin_portal/login.html',
            {'error': 'تم حظر تسجيل الدخول مؤقتًا. حاول مرة أخرى بعد 10 دقائق.'},
            status=429,
        )

    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            cache.delete(fail_key)
            cache.delete(block_key)
            login(request, user)
            next_url = request.GET.get('next', '/admin-portal/')
            return redirect(next_url)

        failed_attempts = cache.get(fail_key, 0) + 1
        cache.set(fail_key, failed_attempts, timeout=600)
        if failed_attempts >= 5:
            cache.set(block_key, True, timeout=600)
            error = 'تم تجاوز عدد المحاولات المسموح به. تم الحظر لمدة 10 دقائق.'
        else:
            error = 'بيانات الدخول غير صحيحة أو ليس لديك صلاحية الوصول.'

    return render(request, 'admin_portal/login.html', {'error': error})


@login_required(login_url='/admin-portal/login/')
def logout_view(request):
    logout(request)
    return redirect('/admin-portal/login/')


@admin_permission_required(["TENANTS_VIEW", "STORES_VIEW"], require_all=True)
def dashboard_view(request):
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    cache_key = "admin_portal:kpis:v1"
    kpis = cache.get(cache_key)
    if not kpis:
        payments_30d = PaymentAttempt.objects.filter(created_at__gte=last_30_days)
        paid_30d = payments_30d.filter(status=PaymentAttempt.STATUS_PAID)

        kpis = {
            'total_tenants': Tenant.objects.count(),
            'total_stores': Store.objects.count(),
            'total_payments_30d': payments_30d.count(),
            'successful_payments_30d': paid_30d.count(),
            'revenue_30d': paid_30d.aggregate(total=Sum('amount'))['total'] or 0,
            'pending_settlements': SettlementRecord.objects.filter(status=SettlementRecord.STATUS_PENDING).count(),
            'total_invoices': Invoice.objects.count(),
            'webhooks_30d': WebhookEvent.objects.filter(received_at__gte=last_30_days).count(),
        }
        cache.set(cache_key, kpis, timeout=60)

    recent_payments = (
        PaymentAttempt.objects.select_related('store')
        .only('id', 'amount', 'status', 'created_at', 'store__name')
        .order_by('-created_at')[:10]
    )
    recent_webhooks = (
        WebhookEvent.objects
        .only('id', 'provider', 'event_id', 'status', 'received_at')
        .order_by('-received_at')[:10]
    )

    context = {
        **kpis,
        'recent_payments': recent_payments,
        'recent_webhooks': recent_webhooks,
    }
    return render(request, 'admin_portal/dashboard.html', context)


@admin_permission_required("TENANTS_VIEW")
def tenants_view(request):
    tenants = (
        Tenant.objects
        .only('id', 'name', 'slug', 'is_active', 'created_at', 'activated_at', 'deactivated_at')
        .annotate(
            store_count=Count('stores', distinct=True),
            payment_count=Count('stores__payment_attempts', distinct=True),
        )
        .order_by('-created_at')
    )

    tenants_page = Paginator(tenants, 25).get_page(request.GET.get('page', 1))
    return render(request, 'admin_portal/tenants.html', {'tenants': tenants_page})


@admin_permission_required("TENANTS_VIEW")
def tenant_detail_view(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    return render(request, 'admin_portal/tenant_detail.html', {'tenant': tenant})


@admin_permission_required("TENANTS_EDIT")
def tenant_set_active_view(request, tenant_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    tenant = get_object_or_404(Tenant, id=tenant_id)
    activate = request.POST.get('active') == '1'

    before = {
        'is_active': tenant.is_active,
        'activated_at': tenant.activated_at.isoformat() if tenant.activated_at else None,
        'deactivated_at': tenant.deactivated_at.isoformat() if tenant.deactivated_at else None,
    }

    with transaction.atomic():
        tenant.is_active = activate
        now = timezone.now()
        if activate:
            tenant.activated_at = now
            tenant.deactivated_at = None
            action = 'TENANT_ACTIVATE'
        else:
            tenant.deactivated_at = now
            action = 'TENANT_DEACTIVATE'
        tenant.save(update_fields=['is_active', 'activated_at', 'deactivated_at', 'updated_at'])

        after = {
            'is_active': tenant.is_active,
            'activated_at': tenant.activated_at.isoformat() if tenant.activated_at else None,
            'deactivated_at': tenant.deactivated_at.isoformat() if tenant.deactivated_at else None,
        }
        log_admin_action(request, action, tenant, before, after)

    return redirect('admin_portal:tenants')


@admin_permission_required("STORES_VIEW")
def stores_view(request):
    stores = (
        Store.objects.select_related('tenant')
        .only('id', 'name', 'slug', 'status', 'created_at', 'tenant__name')
        .annotate(payment_count=Count('payment_attempts', distinct=True))
        .order_by('-created_at')
    )

    stores_page = Paginator(stores, 25).get_page(request.GET.get('page', 1))
    return render(request, 'admin_portal/stores.html', {'stores': stores_page})


@admin_permission_required("STORES_VIEW")
def store_detail_view(request, store_id):
    store = get_object_or_404(Store.objects.select_related('tenant', 'owner'), id=store_id)
    return render(request, 'admin_portal/store_detail.html', {'store': store})


@admin_permission_required("STORES_EDIT")
def store_set_active_view(request, store_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    store = get_object_or_404(Store, id=store_id)
    activate = request.POST.get('active') == '1'

    before = {'status': store.status}

    with transaction.atomic():
        store.status = Store.STATUS_ACTIVE if activate else Store.STATUS_INACTIVE
        store.save(update_fields=['status', 'updated_at'])

        after = {'status': store.status}
        action = 'STORE_ACTIVATE' if activate else 'STORE_DEACTIVATE'
        log_admin_action(request, action, store, before, after)

    return redirect('admin_portal:stores')


@admin_permission_required("FINANCE_VIEW")
def payments_view(request):
    payments = (
        PaymentAttempt.objects.select_related('store')
        .only('id', 'provider', 'amount', 'status', 'idempotency_key', 'created_at', 'store__name')
        .order_by('-created_at')
    )

    status = request.GET.get('status')
    provider = request.GET.get('provider')

    if status:
        payments = payments.filter(status=status)
    if provider:
        payments = payments.filter(provider=provider)

    payments_page = Paginator(payments, 25).get_page(request.GET.get('page', 1))
    return render(request, 'admin_portal/payments.html', {
        'payments': payments_page,
        'status_filter': status,
        'provider_filter': provider,
    })


@admin_permission_required("FINANCE_VIEW")
def settlements_view(request):
    settlements = (
        SettlementRecord.objects.select_related('store')
        .only(
            'id', 'gross_amount', 'wasla_fee', 'net_amount', 'status', 'created_at',
            'store__name',
        )
        .order_by('-created_at')
    )

    status = request.GET.get('status')
    if status:
        settlements = settlements.filter(status=status)

    settlements_page = Paginator(settlements, 25).get_page(request.GET.get('page', 1))
    return render(request, 'admin_portal/settlements.html', {
        'settlements': settlements_page,
        'status_filter': status,
    })


@admin_permission_required("FINANCE_VIEW")
def invoices_view(request):
    invoices = (
        Invoice.objects.select_related('tenant')
        .only(
            'id', 'tenant__name', 'year', 'month', 'total_operations',
            'total_wasla_fee', 'status', 'created_at', 'updated_at',
        )
        .annotate(line_count=Count('lines', distinct=True))
        .order_by('-year', '-month', '-created_at')
    )

    invoices_page = Paginator(invoices, 25).get_page(request.GET.get('page', 1))
    return render(request, 'admin_portal/invoices.html', {'invoices': invoices_page})


@admin_permission_required("FINANCE_MARK_INVOICE_PAID")
def invoice_mark_paid_view(request, invoice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    invoice = get_object_or_404(Invoice, id=invoice_id)
    before = {'status': invoice.status}

    with transaction.atomic():
        invoice.status = Invoice.STATUS_PAID
        invoice.save(update_fields=['status', 'updated_at'])

        linked_settlement_ids = list(
            InvoiceLine.objects.filter(invoice=invoice).values_list('settlement_id', flat=True)
        )
        if linked_settlement_ids:
            SettlementRecord.objects.filter(id__in=linked_settlement_ids).update(status=SettlementRecord.STATUS_PAID)

        after = {'status': invoice.status, 'linked_settlements_paid': len(linked_settlement_ids)}
        log_admin_action(request, 'INVOICE_MARK_PAID', invoice, before, after)

    return redirect('admin_portal:invoices')


@admin_permission_required("WEBHOOKS_VIEW")
def webhooks_view(request):
    webhooks = (
        WebhookEvent.objects
        .only('id', 'provider', 'event_id', 'status', 'received_at')
        .order_by('-received_at')
    )

    provider = request.GET.get('provider')
    status = request.GET.get('status')

    if provider:
        webhooks = webhooks.filter(provider=provider)
    if status:
        webhooks = webhooks.filter(status=status)

    webhooks_page = Paginator(webhooks, 25).get_page(request.GET.get('page', 1))
    return render(request, 'admin_portal/webhooks.html', {
        'webhooks': webhooks_page,
        'provider_filter': provider,
        'status_filter': status,
    })
