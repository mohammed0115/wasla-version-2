
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from ..models import Plugin, InstalledPlugin, PluginRegistration, PluginPermissionScope, PluginEventSubscription
from ..services.plugin_service import PluginService
from ..services.installation_service import PluginInstallationService
from ..services.lifecycle_service import PluginLifecycleService
from ..serializers import (
    PluginSerializer,
    InstalledPluginSerializer,
    PluginRegistrationSerializer,
    PluginPermissionScopeSerializer,
    PluginEventSubscriptionSerializer,
)
from apps.security.rbac import require_permission
from apps.tenants.guards import require_store, require_tenant


def _assert_superuser(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        raise PermissionDenied("Superuser access required")

class PluginListAPI(APIView):
    @method_decorator(require_permission("plugins.view_plugins"))
    def get(self, request):
        plugins = PluginService.list_available_plugins()
        return Response(PluginSerializer(plugins, many=True).data)

class PluginInstallAPI(APIView):
    @method_decorator(require_permission("plugins.install_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginInstallationService.install_plugin(
                store.id,
                plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_201_CREATED)


class PluginEnableAPI(APIView):
    @method_decorator(require_permission("plugins.enable_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginLifecycleService.enable_plugin(
                store_id=store.id,
                plugin=plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_200_OK)


class PluginDisableAPI(APIView):
    @method_decorator(require_permission("plugins.disable_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginLifecycleService.disable_plugin(
                store_id=store.id,
                plugin=plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_200_OK)


class PluginUninstallAPI(APIView):
    @method_decorator(require_permission("plugins.uninstall_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        plugin = Plugin.objects.filter(id=request.data.get("plugin_id")).first()
        if not plugin:
            return Response({"detail": "Plugin not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            installed = PluginLifecycleService.uninstall_plugin(
                store_id=store.id,
                plugin=plugin,
                actor_user_id=request.user.id if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InstalledPluginSerializer(installed).data, status=status.HTTP_200_OK)


class PluginRegistryListCreateAPI(APIView):
    def get(self, request):
        _assert_superuser(request)
        queryset = PluginRegistration.objects.select_related("plugin").order_by("plugin_key")
        return Response(PluginRegistrationSerializer(queryset, many=True).data)

    def post(self, request):
        _assert_superuser(request)
        serializer = PluginRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        registration = serializer.save()
        return Response(PluginRegistrationSerializer(registration).data, status=status.HTTP_201_CREATED)


class PluginRegistryDetailAPI(APIView):
    def patch(self, request, registration_id):
        _assert_superuser(request)
        registration = PluginRegistration.objects.filter(id=registration_id).select_related("plugin").first()
        if not registration:
            return Response({"detail": "Registration not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = PluginRegistrationSerializer(registration, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        registration = serializer.save()
        return Response(PluginRegistrationSerializer(registration).data)


class PluginScopeListCreateAPI(APIView):
    def get(self, request, plugin_id):
        _assert_superuser(request)
        scopes = PluginPermissionScope.objects.filter(plugin_id=plugin_id).order_by("scope_code")
        return Response(PluginPermissionScopeSerializer(scopes, many=True).data)

    def post(self, request, plugin_id):
        _assert_superuser(request)
        payload = dict(request.data)
        payload["plugin_id"] = plugin_id
        serializer = PluginPermissionScopeSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        scope = serializer.save()
        return Response(PluginPermissionScopeSerializer(scope).data, status=status.HTTP_201_CREATED)


class PluginScopeDeleteAPI(APIView):
    def delete(self, request, scope_id):
        _assert_superuser(request)
        scope = PluginPermissionScope.objects.filter(id=scope_id).first()
        if not scope:
            return Response(status=status.HTTP_204_NO_CONTENT)
        scope.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PluginEventSubscriptionListCreateAPI(APIView):
    @method_decorator(require_permission("plugins.enable_plugin"))
    def get(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        subs = PluginEventSubscription.objects.filter(
            tenant_id=tenant.id,
            installed_plugin__store_id=store.id,
        ).select_related("installed_plugin", "installed_plugin__plugin").order_by("event_key")
        return Response(PluginEventSubscriptionSerializer(subs, many=True).data)

    @method_decorator(require_permission("plugins.enable_plugin"))
    def post(self, request, store_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        installed_plugin_id = request.data.get("installed_plugin")
        installed = InstalledPlugin.objects.filter(
            id=installed_plugin_id,
            store_id=store.id,
            tenant_id=tenant.id,
            status="active",
        ).first()
        if not installed:
            return Response({"detail": "Active installed plugin not found"}, status=status.HTTP_400_BAD_REQUEST)

        event_key = (request.data.get("event_key") or "").strip()
        if not event_key:
            return Response({"detail": "event_key is required"}, status=status.HTTP_400_BAD_REQUEST)

        sub, _ = PluginEventSubscription.objects.get_or_create(
            installed_plugin=installed,
            event_key=event_key,
            defaults={"tenant_id": tenant.id, "is_active": True},
        )
        if sub.tenant_id != tenant.id:
            return Response({"detail": "Tenant mismatch"}, status=status.HTTP_400_BAD_REQUEST)

        if sub.is_active is False:
            sub.is_active = True
            sub.save(update_fields=["is_active"])

        return Response(PluginEventSubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)


class PluginEventSubscriptionToggleAPI(APIView):
    @method_decorator(require_permission("plugins.enable_plugin"))
    def patch(self, request, store_id, subscription_id):
        store = require_store(request)
        tenant = require_tenant(request)
        if int(store_id) != int(store.id):
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        sub = PluginEventSubscription.objects.filter(
            id=subscription_id,
            tenant_id=tenant.id,
            installed_plugin__store_id=store.id,
        ).first()
        if not sub:
            return Response({"detail": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND)

        is_active = bool(request.data.get("is_active", True))
        if sub.is_active != is_active:
            sub.is_active = is_active
            sub.save(update_fields=["is_active"])

        return Response(PluginEventSubscriptionSerializer(sub).data)
