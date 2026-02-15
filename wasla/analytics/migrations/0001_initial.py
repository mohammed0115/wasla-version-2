from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(db_index=True)),
                ("event_name", models.CharField(max_length=120)),
                (
                    "actor_type",
                    models.CharField(
                        choices=[
                            ("ANON", "Anon"),
                            ("CUSTOMER", "Customer"),
                            ("MERCHANT", "Merchant"),
                            ("ADMIN", "Admin"),
                        ],
                        default="ANON",
                        max_length=20,
                    ),
                ),
                ("actor_id_hash", models.CharField(blank=True, default="", max_length=64)),
                ("session_key_hash", models.CharField(blank=True, default="", max_length=64)),
                ("object_type", models.CharField(blank=True, default="", max_length=50)),
                ("object_id", models.CharField(blank=True, default="", max_length=64)),
                ("properties_json", models.JSONField(blank=True, default=dict)),
                ("user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("ip_hash", models.CharField(blank=True, default="", max_length=64)),
                ("occurred_at", models.DateTimeField()),
            ],
            options={
                "indexes": [
                    models.Index(fields=["tenant_id", "event_name", "occurred_at"], name="analytics_ev_tenant_event_time_idx"),
                    models.Index(fields=["tenant_id", "occurred_at"], name="analytics_ev_tenant_time_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Experiment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("key", models.CharField(max_length=120, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("RUNNING", "Running"),
                            ("PAUSED", "Paused"),
                            ("ENDED", "Ended"),
                        ],
                        default="DRAFT",
                        max_length=20,
                    ),
                ),
                ("variants_json", models.JSONField(blank=True, default=dict)),
                ("start_at", models.DateTimeField(blank=True, null=True)),
                ("end_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ExperimentAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(db_index=True)),
                ("actor_id_hash", models.CharField(blank=True, default="", max_length=64)),
                ("session_key_hash", models.CharField(blank=True, default="", max_length=64)),
                ("variant", models.CharField(max_length=20)),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("experiment", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="assignments", to="analytics.experiment")),
            ],
            options={
                "indexes": [models.Index(fields=["tenant_id", "assigned_at"], name="analytics_assignment_tenant_time_idx")],
            },
        ),
        migrations.CreateModel(
            name="RecommendationSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(db_index=True)),
                ("context", models.CharField(max_length=40)),
                ("object_id", models.CharField(blank=True, default="", max_length=64)),
                ("recommended_ids_json", models.JSONField(blank=True, default=list)),
                ("strategy", models.CharField(default="RULES_V1", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["tenant_id", "context", "created_at"], name="analytics_rec_tenant_context_time_idx")],
            },
        ),
        migrations.CreateModel(
            name="RiskAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(db_index=True)),
                ("order_id", models.IntegerField(db_index=True)),
                ("score", models.PositiveSmallIntegerField(default=0)),
                (
                    "level",
                    models.CharField(
                        choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High")],
                        default="LOW",
                        max_length=10,
                    ),
                ),
                ("reasons_json", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["tenant_id", "created_at"], name="analytics_risk_tenant_time_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="experimentassignment",
            constraint=models.UniqueConstraint(fields=("experiment", "actor_id_hash", "session_key_hash"), name="uq_experiment_assignment_identity"),
        ),
        migrations.AddConstraint(
            model_name="riskassessment",
            constraint=models.UniqueConstraint(fields=("tenant_id", "order_id"), name="uq_risk_tenant_order"),
        ),
    ]
