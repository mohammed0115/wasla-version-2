from __future__ import annotations

from datetime import timedelta
import random
import time

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.admin_portal.forms import ManualPaymentForm
from apps.observability.models import RequestPerformanceLog
from apps.payments.models import PaymentAttempt, WebhookEvent
from apps.settlements.models import Invoice, InvoiceLine, SettlementRecord
from apps.stores.models import Store
from apps.subscriptions.models import PaymentTransaction, StoreSubscription, SubscriptionPlan
from apps.subscriptions.services.payment_transaction_service import PaymentTransactionService
from apps.tenants.models import Tenant
from apps.tenants.models import StoreProfile
from apps.tenants.services.provisioning import provision_store_after_payment

from .decorators import admin_permission_required
from .utils import log_admin_action
from apps.security.audit import log_security_event
from apps.security.models import SecurityAuditLog


ADMIN_2FA_CODE_KEY = "admin_portal_otp_code"
ADMIN_2FA_EXPIRES_AT_KEY = "admin_portal_otp_expires_at"
ADMIN_2FA_PENDING_USER_ID_KEY = "admin_portal_pending_user_id"


def _generate_otp_code() -> str:
	return f"{random.randint(0, 999999):06d}"


def _store_admin_otp(request, user) -> int:
	ttl_seconds = int(getattr(settings, "ADMIN_PORTAL_2FA_TTL_SECONDS", 300) or 300)
	code = _generate_otp_code()
	expires_at = int(time.time()) + ttl_seconds
	request.session[ADMIN_2FA_CODE_KEY] = code
	request.session[ADMIN_2FA_EXPIRES_AT_KEY] = expires_at
	request.session[ADMIN_2FA_PENDING_USER_ID_KEY] = user.id
	request.session.modified = True

	send_mail(
		subject="Wasla Admin Portal verification code",
		message=f"Your admin verification code is: {code}\n\nCode expires in {ttl_seconds // 60} minutes.",
		from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "Wasla <info@w-sala.com>"),
		recipient_list=[user.email],
		fail_silently=False,
	)
	return expires_at


def _clear_admin_otp(request) -> None:
	for key in (ADMIN_2FA_CODE_KEY, ADMIN_2FA_EXPIRES_AT_KEY, ADMIN_2FA_PENDING_USER_ID_KEY):
		if key in request.session:
			del request.session[key]
	request.session.modified = True


def _verify_admin_otp(request, code: str) -> bool:
	saved_code = (request.session.get(ADMIN_2FA_CODE_KEY) or "").strip()
	expires_at = int(request.session.get(ADMIN_2FA_EXPIRES_AT_KEY, 0) or 0)
	if not saved_code or int(time.time()) > expires_at:
		return False
	return saved_code == (code or "").strip()


def _get_client_ip(request) -> str:
	xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
	if xff:
		return xff.split(",")[0].strip()
	return request.META.get("REMOTE_ADDR", "")


def _throttle_keys(ip: str):
	return f"admin_portal:login_fail:{ip}", f"admin_portal:login_block:{ip}"


def _provision_platform_domain(tenant: Tenant) -> bool:
	base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "") or "").strip().lower()
	if not base_domain:
		return False

	preferred = f"store{tenant.id}"
	candidate = preferred
	suffix = 1
	while Tenant.objects.exclude(id=tenant.id).filter(subdomain=candidate).exists():
		suffix += 1
		candidate = f"{preferred}-{suffix}"

	full_domain = f"{candidate}.{base_domain}"
	changed = (tenant.subdomain != candidate) or (tenant.domain != full_domain)
	if changed:
		tenant.subdomain = candidate
		tenant.domain = full_domain
		tenant.save(update_fields=["subdomain", "domain", "updated_at"])
	return changed


def _finalize_setup_for_tenant(tenant: Tenant) -> bool:
	changed = False
	now = timezone.now()

	if not tenant.setup_completed or tenant.setup_step != 4:
		tenant.setup_completed = True
		tenant.setup_completed_at = tenant.setup_completed_at or now
		tenant.setup_step = 4
		tenant.save(update_fields=["setup_completed", "setup_completed_at", "setup_step", "updated_at"])
		changed = True

	profile = StoreProfile.objects.filter(tenant=tenant).first()
	if profile and (not profile.is_setup_complete or int(profile.setup_step or 1) != 4):
		profile.is_setup_complete = True
		profile.setup_step = 4
		profile.save(update_fields=["is_setup_complete", "setup_step", "updated_at"])
		changed = True

	return changed


@never_cache
@ensure_csrf_cookie
def login_view(request):
	if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
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
	otp_required = bool(request.session.get(ADMIN_2FA_PENDING_USER_ID_KEY))
	otp_remaining = max(0, int(request.session.get(ADMIN_2FA_EXPIRES_AT_KEY, 0) or 0) - int(time.time()))
	if request.method == 'POST':
		action = (request.POST.get('action') or 'password').strip().lower()

		if action in {'verify_otp', 'resend_otp'} and request.session.get(ADMIN_2FA_PENDING_USER_ID_KEY):
			pending_user_id = request.session.get(ADMIN_2FA_PENDING_USER_ID_KEY)
			user = authenticate(request, username=request.POST.get('username', ''), password=request.POST.get('password', ''))
			try:
				pending_user_id = int(pending_user_id)
			except (TypeError, ValueError):
				pending_user_id = None

			pending_user = None
			if pending_user_id:
				from django.contrib.auth import get_user_model
				pending_user = get_user_model().objects.filter(id=pending_user_id).first()
				if pending_user and not (pending_user.is_staff or pending_user.is_superuser):
					pending_user = None

			if action == 'resend_otp' and pending_user is not None:
				_store_admin_otp(request, pending_user)
				otp_required = True
				otp_remaining = max(0, int(request.session.get(ADMIN_2FA_EXPIRES_AT_KEY, 0) or 0) - int(time.time()))
				log_security_event(
					request=request,
					event_type=SecurityAuditLog.EVENT_ADMIN_2FA,
					outcome=SecurityAuditLog.OUTCOME_SUCCESS,
					metadata={'action': 'resend_otp'},
					user=pending_user,
				)
			else:
				code = (request.POST.get('otp_code') or '').strip()
				if pending_user is not None and _verify_admin_otp(request, code):
					cache.delete(fail_key)
					cache.delete(block_key)
					_clear_admin_otp(request)
					login(request, pending_user)
					log_security_event(
						request=request,
						event_type=SecurityAuditLog.EVENT_ADMIN_2FA,
						outcome=SecurityAuditLog.OUTCOME_SUCCESS,
						metadata={'action': 'verify_otp'},
						user=pending_user,
					)
					next_url = request.GET.get('next', '/admin-portal/')
					return redirect(next_url)
				error = 'رمز التحقق غير صحيح أو منتهي الصلاحية.'
				otp_required = True
				otp_remaining = max(0, int(request.session.get(ADMIN_2FA_EXPIRES_AT_KEY, 0) or 0) - int(time.time()))
				log_security_event(
					request=request,
					event_type=SecurityAuditLog.EVENT_ADMIN_2FA,
					outcome=SecurityAuditLog.OUTCOME_FAILURE,
					metadata={'action': 'verify_otp'},
					user=pending_user,
				)
		else:
			username = request.POST.get('username')
			password = request.POST.get('password')
			user = authenticate(request, username=username, password=password)

			if user is not None and (user.is_staff or user.is_superuser):
				two_fa_enabled = bool(getattr(settings, 'ADMIN_PORTAL_2FA_ENABLED', False))
				if two_fa_enabled and user.email:
					_store_admin_otp(request, user)
					otp_required = True
					otp_remaining = max(0, int(request.session.get(ADMIN_2FA_EXPIRES_AT_KEY, 0) or 0) - int(time.time()))
					log_security_event(
						request=request,
						event_type=SecurityAuditLog.EVENT_LOGIN,
						outcome=SecurityAuditLog.OUTCOME_SUCCESS,
						metadata={'phase': 'password_ok_otp_required'},
						user=user,
					)
				else:
					cache.delete(fail_key)
					cache.delete(block_key)
					login(request, user)
					log_security_event(
						request=request,
						event_type=SecurityAuditLog.EVENT_LOGIN,
						outcome=SecurityAuditLog.OUTCOME_SUCCESS,
						metadata={'phase': 'direct_login'},
						user=user,
					)
					next_url = request.GET.get('next', '/admin-portal/')
					return redirect(next_url)
			else:
				failed_attempts = cache.get(fail_key, 0) + 1
				cache.set(fail_key, failed_attempts, timeout=600)
				if failed_attempts >= 5:
					cache.set(block_key, True, timeout=600)
					error = 'تم تجاوز عدد المحاولات المسموح به. تم الحظر لمدة 10 دقائق.'
				else:
					error = 'بيانات الدخول غير صحيحة أو ليس لديك صلاحية الوصول.'
				log_security_event(
					request=request,
					event_type=SecurityAuditLog.EVENT_LOGIN,
					outcome=SecurityAuditLog.OUTCOME_FAILURE,
					metadata={'phase': 'password'},
				)

	return render(request, 'admin_portal/login.html', {
		'error': error,
		'otp_required': otp_required,
		'otp_remaining': otp_remaining,
	})


@login_required(login_url='/admin-portal/login/')
def logout_view(request):
	logout(request)
	return redirect('/admin-portal/login/')


@admin_permission_required(["portal.tenants.view", "portal.stores.view"], require_all=True)
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


@admin_permission_required("portal.tenants.view")
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


@admin_permission_required("portal.tenants.view")
def tenant_detail_view(request, tenant_id):
	tenant = get_object_or_404(Tenant, id=tenant_id)
	return render(request, 'admin_portal/tenant_detail.html', {'tenant': tenant})


@admin_permission_required("portal.tenants.manage")
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


@admin_permission_required("portal.tenants.manage")
def tenant_publish_view(request, tenant_id):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	tenant = get_object_or_404(Tenant, id=tenant_id)
	action = (request.POST.get('action') or '').strip().lower()
	should_publish = action == 'publish'

	before = {'is_published': tenant.is_published}

	with transaction.atomic():
		tenant.is_published = should_publish
		tenant.save(update_fields=['is_published', 'updated_at'])

		subscription_changed = False
		domain_changed = False
		setup_changed = False
		if should_publish:
			latest_subscription = (
				StoreSubscription.objects.select_related('plan')
				.filter(store_id=tenant.id)
				.order_by('-created_at', '-end_date')
				.first()
			)
			if latest_subscription and latest_subscription.status != 'active':
				latest_subscription.status = 'active'
				today = timezone.now().date()
				if latest_subscription.end_date and latest_subscription.end_date < today:
					cycle = getattr(latest_subscription.plan, 'billing_cycle', 'monthly')
					extension_days = 365 if cycle == 'yearly' else 30
					latest_subscription.end_date = today + timedelta(days=extension_days)
					latest_subscription.save(update_fields=['status', 'end_date'])
				else:
					latest_subscription.save(update_fields=['status'])
				subscription_changed = True

			domain_changed = _provision_platform_domain(tenant)
			setup_changed = _finalize_setup_for_tenant(tenant)

		after = {'is_published': tenant.is_published}
		if subscription_changed:
			after['subscription_status'] = 'active'
		if domain_changed:
			after['platform_domain'] = tenant.domain
		if setup_changed:
			after['setup_completed'] = True
		log_admin_action(
			request,
			'TENANT_PUBLISH' if should_publish else 'TENANT_UNPUBLISH',
			tenant,
			before,
			after,
		)

	return redirect('admin_portal:tenants')


@admin_permission_required("portal.stores.view")
def stores_view(request):
	stores = (
		Store.objects.select_related('tenant')
		.only('id', 'name', 'slug', 'status', 'created_at', 'tenant__name')
		.annotate(payment_count=Count('payment_attempts', distinct=True))
		.order_by('-created_at')
	)

	stores_page = Paginator(stores, 25).get_page(request.GET.get('page', 1))
	return render(request, 'admin_portal/stores.html', {'stores': stores_page})


@admin_permission_required("portal.stores.view")
def store_detail_view(request, store_id):
	store = get_object_or_404(Store.objects.select_related('tenant', 'owner'), id=store_id)
	return render(request, 'admin_portal/store_detail.html', {'store': store})


@admin_permission_required("portal.stores.manage")
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


@admin_permission_required("portal.payments.view")
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


@admin_permission_required("portal.settlements.view")
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


@admin_permission_required("portal.settlements.view")
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


@admin_permission_required("portal.settlements.approve")
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


@admin_permission_required("portal.audit.view")
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


@admin_permission_required("portal.payments.view")
def payment_transactions_view(request):
	transactions = (
		PaymentTransaction.objects.select_related('tenant', 'plan')
		.order_by('-created_at')
	)
	tenants = Tenant.objects.only('id', 'name', 'slug').order_by('name')

	status_filter = (request.GET.get('status') or '').strip()
	tenant_filter = (request.GET.get('tenant') or '').strip()

	if status_filter:
		transactions = transactions.filter(status=status_filter)
	if tenant_filter.isdigit():
		transactions = transactions.filter(tenant_id=int(tenant_filter))

	transactions_page = Paginator(transactions, 25).get_page(request.GET.get('page', 1))
	return render(request, 'admin_portal/payment_transactions.html', {
		'transactions': transactions_page,
		'tenants': tenants,
		'status_filter': status_filter,
		'tenant_filter': tenant_filter,
	})


@admin_permission_required("portal.payments.manage")
def payment_transaction_create_view(request):
	form = ManualPaymentForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		cleaned = form.cleaned_data
		status = cleaned['status']
		tenant = cleaned['tenant']

		tx = PaymentTransactionService.record_manual_payment(
			tenant=tenant,
			plan=cleaned['plan'],
			amount=cleaned['amount'],
			currency=(cleaned.get('currency') or 'SAR').strip().upper() or 'SAR',
			reference=(cleaned.get('reference') or '').strip(),
			status=status,
			recorded_by=request.user,
		)

		if status == PaymentTransaction.STATUS_PAID:
			owner = getattr(getattr(tenant, 'store_profile', None), 'owner', None)
			if owner is not None:
				provision_store_after_payment(merchant=owner, plan=cleaned['plan'], payment=tx)
			messages.success(request, 'Payment approved and store provisioning executed.')
		else:
			messages.success(request, 'Manual payment was recorded as pending.')

		return redirect('admin_portal:payment_transactions')

	return render(request, 'admin_portal/payment_transaction_create.html', {'form': form})


@admin_permission_required("portal.payments.manage")
def payment_transaction_approve_create_store_view(request, transaction_id: int):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	tx = get_object_or_404(PaymentTransaction.objects.select_related('tenant', 'plan'), id=transaction_id)
	if tx.status == PaymentTransaction.STATUS_PAID:
		messages.info(request, 'Payment is already approved.')
		return redirect('admin_portal:payment_transactions')

	if tx.status in {PaymentTransaction.STATUS_FAILED, PaymentTransaction.STATUS_CANCELLED}:
		messages.error(request, 'Cannot approve a failed or cancelled payment.')
		return redirect('admin_portal:payment_transactions')

	owner = getattr(getattr(tx.tenant, 'store_profile', None), 'owner', None)
	if owner is None:
		messages.error(request, 'Tenant owner was not found. Please assign owner first.')
		return redirect('admin_portal:payment_transactions')

	with transaction.atomic():
		tx.status = PaymentTransaction.STATUS_PAID
		tx.paid_at = timezone.now()
		if tx.recorded_by_id is None:
			tx.recorded_by = request.user
			update_fields = ['status', 'paid_at', 'recorded_by']
		else:
			update_fields = ['status', 'paid_at']
		tx.save(update_fields=update_fields)
		provision_store_after_payment(merchant=owner, plan=tx.plan, payment=tx)

	messages.success(request, 'Payment approved and store created/activated successfully.')
	return redirect('admin_portal:payment_transactions')


@admin_permission_required("portal.subscriptions.view")
def subscriptions_view(request):
	subscriptions = StoreSubscription.objects.select_related('plan').order_by('-created_at')
	plans = SubscriptionPlan.objects.only('id', 'name').order_by('name')

	status_filter = (request.GET.get('status') or '').strip()
	plan_filter = (request.GET.get('plan') or '').strip()

	if status_filter:
		subscriptions = subscriptions.filter(status=status_filter)
	if plan_filter.isdigit():
		subscriptions = subscriptions.filter(plan_id=int(plan_filter))

	subscriptions_page = Paginator(subscriptions, 25).get_page(request.GET.get('page', 1))
	return render(request, 'admin_portal/subscriptions.html', {
		'subscriptions': subscriptions_page,
		'plans': plans,
		'status_filter': status_filter,
		'plan_filter': plan_filter,
	})


@admin_permission_required("portal.audit.view")
def performance_monitoring_view(request):
	logs = RequestPerformanceLog.objects.all().order_by('-created_at')
	stores = Store.objects.only('id', 'name').order_by('name')

	store_filter = (request.GET.get('store') or '').strip()
	endpoint_filter = (request.GET.get('endpoint') or '').strip()
	date_from = (request.GET.get('date_from') or '').strip()
	date_to = (request.GET.get('date_to') or '').strip()
	slow_only = (request.GET.get('slow_only') or '').strip() in ('1', 'true', 'on')

	if store_filter.isdigit():
		logs = logs.filter(store_id=int(store_filter))
	if endpoint_filter:
		logs = logs.filter(endpoint__icontains=endpoint_filter)
	if date_from:
		logs = logs.filter(created_at__date__gte=date_from)
	if date_to:
		logs = logs.filter(created_at__date__lte=date_to)
	if slow_only:
		logs = logs.filter(is_slow=True)

	summary = logs.aggregate(
		total_requests=Count('id'),
		avg_response_ms=Avg('response_time_ms'),
		avg_query_count=Avg('db_query_count'),
	)

	total = summary.get('total_requests') or 0
	cache_hits = logs.filter(cache_hit=True).count()
	cache_hit_rate = round((cache_hits / total) * 100, 2) if total else 0

	logs_page = Paginator(logs, 50).get_page(request.GET.get('page', 1))

	return render(request, 'admin_portal/performance_monitoring.html', {
		'logs': logs_page,
		'stores': stores,
		'summary': summary,
		'cache_hit_rate': cache_hit_rate,
		'store_filter': store_filter,
		'endpoint_filter': endpoint_filter,
		'date_from': date_from,
		'date_to': date_to,
		'slow_only': slow_only,
	})
