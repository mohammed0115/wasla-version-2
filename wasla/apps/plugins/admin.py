
from django.contrib import admin
from .models import (
	InstalledPlugin,
	Plugin,
	PluginActivationLog,
	PluginEventDelivery,
	PluginEventSubscription,
	PluginPermissionScope,
	PluginRegistration,
)

admin.site.register(Plugin)
admin.site.register(InstalledPlugin)
admin.site.register(PluginActivationLog)
admin.site.register(PluginRegistration)
admin.site.register(PluginPermissionScope)
admin.site.register(PluginEventSubscription)
admin.site.register(PluginEventDelivery)
