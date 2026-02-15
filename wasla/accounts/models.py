from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")

    # Registration
    phone_country = models.CharField(max_length=8, default="+966")
    phone_number = models.CharField(max_length=32, blank=True)

    # Persona / onboarding (Salla-like)
    country = models.CharField(max_length=32, blank=True)                 # e.g. "SA"
    legal_entity = models.CharField(max_length=64, blank=True)            # e.g. "مؤسسة"
    has_existing_business = models.CharField(max_length=16, blank=True)   # "yes"/"no"
    selling_channel = models.CharField(max_length=64, blank=True)         # e.g. "Instagram"
    category_main = models.CharField(max_length=128, blank=True)
    category_sub = models.CharField(max_length=128, blank=True)
    plan = models.ForeignKey("stores.Plan", null=True, blank=True, on_delete=models.SET_NULL)


    persona_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile({self.user_id})"


# Backwards-compatible alias for older modules/tests.
# Some patches referenced `AccountProfile` before the model was renamed to `Profile`.
AccountProfile = Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)