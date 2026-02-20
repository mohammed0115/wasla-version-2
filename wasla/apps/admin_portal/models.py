from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AdminRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AdminPermission(models.Model):
    code = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class AdminRolePermission(models.Model):
    role = models.ForeignKey(AdminRole, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(AdminPermission, on_delete=models.CASCADE, related_name="permission_roles")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("role", "permission"), name="uq_admin_role_permission"),
        ]
        ordering = ["role__name", "permission__code"]

    def __str__(self) -> str:
        return f"{self.role.name}:{self.permission.code}"


class AdminUserRole(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_user_role")
    role = models.ForeignKey(AdminRole, on_delete=models.PROTECT, related_name="users")

    class Meta:
        ordering = ["user_id"]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.role.name}"


class AdminAuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="admin_audit_logs")
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=120)
    object_id = models.CharField(max_length=120)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip_address = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("AdminAuditLog is immutable and cannot be updated")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("AdminAuditLog is immutable and cannot be deleted")

    def __str__(self) -> str:
        return f"{self.action}:{self.object_type}:{self.object_id}"
