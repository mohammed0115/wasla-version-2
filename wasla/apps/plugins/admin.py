
from django.contrib import admin
from .models import InstalledPlugin, Plugin, PluginActivationLog

admin.site.register(Plugin)
admin.site.register(InstalledPlugin)
admin.site.register(PluginActivationLog)
