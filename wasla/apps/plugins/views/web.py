"""
Django web views for plugin management in the admin portal.
Renders HTML templates for superuser plugin registry management.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import (
    Plugin,
    InstalledPlugin,
    PluginRegistration,
    PluginPermissionScope,
    PluginEventSubscription,
    PluginEventDelivery,
)
from apps.stores.models import Store
from apps.tenants.models import Tenant


def admin_required(view_func):
    """Decorator to check if user is admin/superuser."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('admin_portal:login')
        if not request.user.is_staff or not request.user.is_superuser:
            return HttpResponseForbidden("You do not have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@admin_required
def plugins_dashboard_view(request):
    """Display plugin management dashboard."""
    context = {
        'page': 'plugins',
        'total_plugins': Plugin.objects.count(),
        'total_registrations': PluginRegistration.objects.filter(verified=True).count(),
        'total_installed': InstalledPlugin.objects.filter(is_enabled=True).count(),
        'recent_registrations': PluginRegistration.objects.order_by('-created_at')[:5],
        'recent_installs': InstalledPlugin.objects.order_by('-created_at')[:5],
    }
    return render(request, 'admin_portal/plugins/dashboard.html', context)


@login_required
@admin_required
def plugin_registry_list_view(request):
    """List all plugin registrations."""
    registrations = PluginRegistration.objects.select_related('plugin').order_by('-created_at')
    
    # Filtering
    search = request.GET.get('search', '').strip()
    if search:
        registrations = registrations.filter(
            Q(plugin__name__icontains=search) |
            Q(plugin_key__icontains=search) |
            Q(entrypoint__icontains=search)
        )
    
    verified = request.GET.get('verified', '').strip()
    if verified == 'yes':
        registrations = registrations.filter(verified=True)
    elif verified == 'no':
        registrations = registrations.filter(verified=False)
    
    # Annotate with scope and subscription counts
    registrations = registrations.annotate(
        scope_count=Count('pluginpermissionscope'),
        subscription_count=Count('plugineventsubscription')
    )
    
    context = {
        'page': 'plugins',
        'registrations': registrations,
        'search': search,
        'verified_filter': verified,
    }
    return render(request, 'admin_portal/plugins/registry_list.html', context)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def plugin_registry_create_view(request):
    """Create new plugin registration."""
    if request.method == 'POST':
        try:
            plugin_id = request.POST.get('plugin_id')
            plugin = get_object_or_404(Plugin, id=plugin_id)
            
            # Check if registration already exists
            existing = PluginRegistration.objects.filter(plugin=plugin).first()
            if existing:
                messages.warning(request, f"Registration already exists for {plugin.name}.")
                return redirect('admin_portal:plugin_registry_detail', registration_id=existing.id)
            
            # Create registration
            registration = PluginRegistration.objects.create(
                plugin=plugin,
                plugin_key=request.POST.get('plugin_key', plugin.key),
                entrypoint=request.POST.get('entrypoint', 'apps.plugins.builtins'),
                min_core_version=request.POST.get('min_core_version', '1.0.0'),
                max_core_version=request.POST.get('max_core_version', ''),
                isolation_mode=request.POST.get('isolation_mode', 'STANDARD'),
                verified=False,
            )
            
            messages.success(request, f"Registration created for {plugin.name}. Please verify to enable.")
            return redirect('admin_portal:plugin_registry_detail', registration_id=registration.id)
        except Plugin.DoesNotExist:
            messages.error(request, "Plugin not found.")
        except Exception as e:
            messages.error(request, f"Error creating registration: {str(e)}")
    
    context = {
        'page': 'plugins',
        'available_plugins': Plugin.objects.exclude(
            pluginregistration__in=PluginRegistration.objects.all()
        ),
    }
    return render(request, 'admin_portal/plugins/registry_create.html', context)


@login_required
@admin_required
def plugin_registry_detail_view(request, registration_id):
    """View and edit plugin registration."""
    registration = get_object_or_404(PluginRegistration, id=registration_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'verify':
            registration.verified = True
            registration.verified_at = timezone.now()
            registration.verified_by = request.user
            registration.save()
            messages.success(request, f"Registration verified for {registration.plugin.name}.")
        
        elif action == 'reject':
            registration.verified = False
            registration.verified_by = None
            registration.save()
            messages.success(request, "Registration rejected.")
        
        elif action == 'update':
            registration.min_core_version = request.POST.get('min_core_version', registration.min_core_version)
            registration.max_core_version = request.POST.get('max_core_version', registration.max_core_version)
            registration.isolation_mode = request.POST.get('isolation_mode', registration.isolation_mode)
            registration.save()
            messages.success(request, "Registration updated.")
        
        elif action == 'delete':
            registration.delete()
            messages.success(request, "Registration deleted.")
            return redirect('admin_portal:plugin_registry_list')
        
        return redirect('admin_portal:plugin_registry_detail', registration_id=registration.id)
    
    # Get scopes and subscriptions
    scopes = PluginPermissionScope.objects.filter(registration=registration)
    subscriptions = PluginEventSubscription.objects.filter(registration=registration)
    
    context = {
        'page': 'plugins',
        'registration': registration,
        'scopes': scopes,
        'subscriptions': subscriptions,
        'isolation_modes': [
            ('STANDARD', 'Standard'),
            ('ISOLATED', 'Isolated'),
            ('PRIVILEGED', 'Privileged'),
        ],
    }
    return render(request, 'admin_portal/plugins/registry_detail.html', context)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def plugin_scopes_view(request, registration_id):
    """Manage permission scopes for a plugin."""
    registration = get_object_or_404(PluginRegistration, id=registration_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_scope':
            scope_code = request.POST.get('scope_code', '').strip()
            description = request.POST.get('description', '').strip()
            
            if not scope_code:
                messages.error(request, "Scope code is required.")
            else:
                scope, created = PluginPermissionScope.objects.get_or_create(
                    registration=registration,
                    scope_code=scope_code,
                    defaults={'description': description}
                )
                if created:
                    messages.success(request, f"Scope '{scope_code}' added.")
                else:
                    messages.warning(request, f"Scope '{scope_code}' already exists.")
        
        elif action == 'delete_scope':
            scope_id = request.POST.get('scope_id')
            scope = get_object_or_404(PluginPermissionScope, id=scope_id, registration=registration)
            scope.delete()
            messages.success(request, f"Scope '{scope.scope_code}' deleted.")
        
        return redirect('admin_portal:plugin_scopes', registration_id=registration.id)
    
    scopes = PluginPermissionScope.objects.filter(registration=registration).order_by('scope_code')
    
    context = {
        'page': 'plugins',
        'registration': registration,
        'scopes': scopes,
        'preset_scopes': [
            'plugin.lifecycle.enable',
            'plugin.lifecycle.disable',
            'plugin.lifecycle.uninstall',
            'plugin.webhooks.manage',
            'plugin.events.subscribe',
            'plugin.data.read',
            'plugin.data.write',
        ],
    }
    return render(request, 'admin_portal/plugins/scopes.html', context)


@login_required
@admin_required
def plugin_subscriptions_view(request):
    """View event subscriptions across tenants."""
    subscriptions = PluginEventSubscription.objects.select_related(
        'registration', 'tenant', 'store'
    ).order_by('-created_at')
    
    # Filtering
    registration_id = request.GET.get('registration', '').strip()
    if registration_id:
        subscriptions = subscriptions.filter(registration_id=registration_id)
    
    tenant_id = request.GET.get('tenant', '').strip()
    if tenant_id:
        subscriptions = subscriptions.filter(tenant_id=tenant_id)
    
    store_id = request.GET.get('store', '').strip()
    if store_id:
        subscriptions = subscriptions.filter(store_id=store_id)
    
    # Get filter options
    registrations = PluginRegistration.objects.filter(verified=True).order_by('plugin__name')
    tenants = Tenant.objects.order_by('name')
    stores = Store.objects.order_by('name')
    
    context = {
        'page': 'plugins',
        'subscriptions': subscriptions,
        'registrations': registrations,
        'tenants': tenants,
        'stores': stores,
        'selected_registration': registration_id,
        'selected_tenant': tenant_id,
        'selected_store': store_id,
    }
    return render(request, 'admin_portal/plugins/subscriptions.html', context)


@login_required
@admin_required
def plugin_event_deliveries_view(request, registration_id=None):
    """View event delivery history."""
    deliveries = PluginEventDelivery.objects.select_related(
        'event_subscription__registration',
        'event_subscription__tenant',
        'event_subscription__store'
    ).order_by('-created_at')
    
    # Filtering
    if registration_id:
        deliveries = deliveries.filter(event_subscription__registration_id=registration_id)
    
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        deliveries = deliveries.filter(status=status_filter.upper())
    
    event_key = request.GET.get('event_key', '').strip()
    if event_key:
        deliveries = deliveries.filter(event_key__icontains=event_key)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(deliveries, 50)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)
    
    context = {
        'page': 'plugins',
        'page_obj': page_obj,
        'status_filter': status_filter,
        'event_key': event_key,
        'registration_id': registration_id,
        'status_choices': [
            ('QUEUED', 'Queued'),
            ('DELIVERED', 'Delivered'),
            ('SKIPPED', 'Skipped'),
            ('FAILED', 'Failed'),
        ],
    }
    return render(request, 'admin_portal/plugins/event_deliveries.html', context)


@login_required
@admin_required
def installed_plugins_view(request):
    """List installed plugins across stores."""
    installed = InstalledPlugin.objects.select_related(
        'store', 'plugin'
    ).order_by('-created_at')
    
    # Filtering
    store_id = request.GET.get('store', '').strip()
    if store_id:
        installed = installed.filter(store_id=store_id)
    
    enabled_filter = request.GET.get('enabled', '').strip()
    if enabled_filter == 'yes':
        installed = installed.filter(is_enabled=True)
    elif enabled_filter == 'no':
        installed = installed.filter(is_enabled=False)
    
    # Get filter options
    stores = Store.objects.order_by('name')
    
    context = {
        'page': 'plugins',
        'installed': installed,
        'stores': stores,
        'selected_store': store_id,
        'enabled_filter': enabled_filter,
    }
    return render(request, 'admin_portal/plugins/installed.html', context)
