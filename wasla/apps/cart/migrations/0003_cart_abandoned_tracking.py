"""Add abandoned cart tracking to Cart model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0003_cartitem_variant"),
    ]

    operations = [
        migrations.AddField(
            model_name="cart",
            name="abandoned_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When cart was marked as abandoned (24h+ without activity)",
            ),
        ),
        migrations.AddField(
            model_name="cart",
            name="reminder_sent",
            field=models.BooleanField(
                default=False,
                help_text="Whether reminder email has been sent",
            ),
        ),
        migrations.AddField(
            model_name="cart",
            name="reminder_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When reminder email was sent",
            ),
        ),
        migrations.AddIndex(
            model_name="cart",
            index=models.Index(fields=["abandoned_at"], name="cart_abandoned_at_idx"),
        ),
        migrations.AddIndex(
            model_name="cart",
            index=models.Index(fields=["reminder_sent"], name="cart_reminder_sent_idx"),
        ),
    ]
