from django.contrib.auth import get_user_model
from apps.admin_portal.models import AdminUserRole

User = get_user_model()
u = User.objects.get(username="admin")

print("is_staff:", u.is_staff)
print("has_role:", AdminUserRole.objects.filter(user=u).exists())
if AdminUserRole.objects.filter(user=u).exists():
    print("role:", u.admin_user_role.role.name)