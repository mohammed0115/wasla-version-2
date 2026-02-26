# Generated manually for AI onboarding module.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("stores", "0003_store_tenant_relation"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnboardingDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("business_type", models.CharField(max_length=120)),
                ("recommended_plan", models.CharField(max_length=120)),
                ("complexity_score", models.DecimalField(decimal_places=2, max_digits=5)),
                ("decision_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_onboarding_decision",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["business_type", "recommended_plan"], name="ai_onboardi_busines_4ad231_idx"),
                    models.Index(fields=["created_at"], name="ai_onboardi_created_67db31_idx"),
                ],
            },
        ),
    ]
