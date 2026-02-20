#!/usr/bin/env python
"""Create a test staff user for admin portal access."""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = "admin"
email = "admin@wasla.local"
password = "admin123"

# Delete existing user if exists
User.objects.filter(username=username).delete()

# Create staff user
user = User.objects.create_user(
    username=username,
    email=email,
    password=password,
    is_staff=True,
    is_superuser=True
)

print(f"✓ Staff user created successfully:")
print(f"  Username: {username}")
print(f"  Password: {password}")
print(f"  Staff:    {user.is_staff}")
print(f"  Admin Portal URL: http://localhost:8000/admin-portal/")
