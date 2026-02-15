+++ b/wasla/emails/migrations/0003_create_default_global_email_settings.py
@@
+from django.db import migrations
+
+
+def create_default_global_email_settings(apps, schema_editor):
+    GlobalEmailSettings = apps.get_model("emails", "GlobalEmailSettings")
+    if GlobalEmailSettings.objects.exists():
+        return
+
+    # Create a safe default row (all required fields have defaults in the model)
+    # Keep enabled=False to avoid sending emails unintentionally in new environments.
+    GlobalEmailSettings.objects.create(enabled=False)
+
+
+class Migration(migrations.Migration):
+    dependencies = [
+        ("emails", "0002_globalemailsettings_globalemailsettingsauditlog"),
+    ]
+
+    operations = [
+        migrations.RunPython(create_default_global_email_settings, reverse_code=migrations.RunPython.noop),
+    ]
