from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ai_onboarding", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("stores", "0003_store_tenant_relation"),
        ("subscriptions", "0005_default_plan_features"),
    ]

    operations = [
        migrations.DeleteModel(
            name="OnboardingDecision",
        ),
        migrations.CreateModel(
            name="OnboardingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("country", models.CharField(default="SA", max_length=10)),
                ("language", models.CharField(default="ar", max_length=10)),
                ("device_type", models.CharField(default="web", max_length=32)),
                ("business_type", models.CharField(max_length=64)),
                ("expected_products", models.PositiveIntegerField(blank=True, null=True)),
                ("expected_orders_per_day", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "store",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="onboarding_profiles", to="stores.store"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="onboarding_profiles", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "created_at"], name="ai_onboardi_user_id_5bc773_idx"),
                    models.Index(fields=["business_type", "country"], name="ai_onboardi_busines_a1a7ba_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProvisioningActionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.CharField(default="", max_length=120)),
                ("action", models.CharField(max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("success", "Success"), ("failed", "Failed")], default="success", max_length=20)),
                ("error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "profile",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="provisioning_action_logs", to="ai_onboarding.onboardingprofile"),
                ),
                (
                    "store",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="provisioning_action_logs", to="stores.store"),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store", "created_at"], name="ai_onboardi_store_i_ec53e1_idx"),
                    models.Index(fields=["action", "status"], name="ai_onboardi_action_40f0dc_idx"),
                    models.Index(fields=["idempotency_key"], name="ai_onboardi_idempot_ee96f5_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProvisioningRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.CharField(max_length=120)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="provisioning_requests", to="ai_onboarding.onboardingprofile"),
                ),
                (
                    "store",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="provisioning_requests", to="stores.store"),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["idempotency_key"], name="ai_onboardi_idempot_8f91cf_idx"),
                    models.Index(fields=["status", "created_at"], name="ai_onboardi_status_9dc8d9_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("profile", "idempotency_key"), name="uq_provisioning_profile_idempotency_key"),
                ],
            },
        ),
        migrations.CreateModel(
            name="OnboardingDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("recommended_plan_code", models.CharField(default="BASIC", max_length=32)),
                ("needs_variants", models.BooleanField(default=False)),
                ("recommended_theme", models.CharField(default="default", max_length=100)),
                ("recommended_categories", models.JSONField(blank=True, default=list)),
                ("shipping_profile", models.JSONField(blank=True, default=dict)),
                ("complexity_score", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("rationale", models.TextField(blank=True, default="")),
                ("llm_used", models.BooleanField(default=False)),
                ("llm_confidence", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "profile",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="decision", to="ai_onboarding.onboardingprofile"),
                ),
                (
                    "recommended_plan",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="onboarding_decisions", to="subscriptions.subscriptionplan"),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["recommended_plan_code", "complexity_score"], name="ai_onboardi_recomme_3a6d58_idx"),
                    models.Index(fields=["created_at"], name="ai_onboardi_created_1456d4_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("profile",), name="uq_onboarding_decision_profile"),
                ],
            },
        ),
    ]
