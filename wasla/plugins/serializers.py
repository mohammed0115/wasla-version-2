
from rest_framework import serializers
from .models import Plugin, InstalledPlugin

class PluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plugin
        fields = "__all__"

class InstalledPluginSerializer(serializers.ModelSerializer):
    plugin = PluginSerializer()
    class Meta:
        model = InstalledPlugin
        fields = "__all__"
