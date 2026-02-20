from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update a staff/superuser for admin portal"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--email", default="admin@wasla.local")
        parser.add_argument("--password", default="admin123")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        email = options["email"]
        password = options["password"]

        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save(update_fields=["email", "is_staff", "is_superuser", "password"])

        state = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Staff user {state}: {username}"))
