from django.db import models

# Create your models here.
class Plan(models.Model):
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=8, decimal_places=2)
    is_popular = models.BooleanField(default=False)
    is_free = models.BooleanField(default=False)
