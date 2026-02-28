
from rest_framework import serializers
from .models import (
    Plugin,
    InstalledPlugin,
    PluginRegistration,
    PluginPermissionScope,
    PluginEventSubscription,
)

class PluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plugin
        fields = "__all__"

class InstalledPluginSerializer(serializers.ModelSerializer):
    plugin = PluginSerializer()
    class Meta:
        model = InstalledPlugin
        fields = "__all__"


class PluginRegistrationSerializer(serializers.ModelSerializer):
    plugin = PluginSerializer(read_only=True)
    plugin_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = PluginRegistration
        fields = [
            "id",
            "plugin",
            "plugin_id",
            "plugin_key",
            "entrypoint",
            "min_core_version",
            "max_core_version",
            "isolation_mode",
            "verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "plugin"]

    def create(self, validated_data):
        plugin_id = validated_data.pop("plugin_id")
        plugin = Plugin.objects.get(id=plugin_id)
        registration, _ = PluginRegistration.objects.update_or_create(
            plugin=plugin,
            defaults=validated_data,
        )
        return registration


class PluginPermissionScopeSerializer(serializers.ModelSerializer):
    plugin_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = PluginPermissionScope
        fields = ["id", "plugin", "plugin_id", "scope_code", "description"]
        read_only_fields = ["id", "plugin"]

    def create(self, validated_data):
        plugin_id = validated_data.pop("plugin_id")
        plugin = Plugin.objects.get(id=plugin_id)
        scope, _ = PluginPermissionScope.objects.get_or_create(
            plugin=plugin,
            scope_code=validated_data["scope_code"],
            defaults={"description": validated_data.get("description", "")},
        )
        if validated_data.get("description", "") and scope.description != validated_data["description"]:
            scope.description = validated_data["description"]
            scope.save(update_fields=["description"])
        return scope


class PluginEventSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PluginEventSubscription
        fields = ["id", "installed_plugin", "tenant_id", "event_key", "is_active", "created_at"]
        read_only_fields = ["id", "tenant_id", "created_at"]
