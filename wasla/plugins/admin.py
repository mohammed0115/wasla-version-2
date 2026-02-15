
from django.contrib import admin
from .models import Plugin, InstalledPlugin

admin.site.register(Plugin)
admin.site.register(InstalledPlugin)
