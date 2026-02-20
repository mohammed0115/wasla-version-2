#!/usr/bin/env python
"""Create test data for the admin portal demo."""

import os
import sys
import django
import uuid
from decimal import Decimal
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tenants.models import Tenant
from apps.stores.models import Store
from apps.payments.models import PaymentAttempt, WebhookEvent
from apps.settlements.models import SettlementRecord
from apps.orders.models import Order
from apps.customers.models import Customer
from django.contrib.auth import get_user_model

User = get_user_model()

print("Creating test data...")

# Get or create owner user
owner_user, _ = User.objects.get_or_create(
    username='store_owner',
    defaults={
        'email': 'owner@test.com',
        'is_active': True
    }
)

# Create test tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='test-merchant',
    defaults={
        'name': 'Test Merchant Co.',
        'is_active': True
    }
)
print(f"✓ Tenant: {tenant.name}")

# Create test store
store, _ = Store.objects.get_or_create(
    slug='test-store',
    defaults={
        'tenant': tenant,
        'owner': owner_user,
        'name': 'Test Store',
        'subdomain': 'test-store',
        'status': Store.STATUS_ACTIVE
    }
)
print(f"✓ Store: {store.name}")

# Create test customer
customer, _ = Customer.objects.get_or_create(
    email='customer@test.com',
    store_id=store.id,
    defaults={
        'full_name': 'Test Customer'
    }
)

# Create payment attempts (simplified - without settlements since PaymentAttempt needs Order)
now = datetime.now()
print("Creating webhook events...")

# Create webhook events for demo
for i in range(20):
    received_at = now - timedelta(days=i, hours=i)
    provider = ['tap', 'stripe', 'paypal'][i % 3]
    status_choice = ['processed', 'received', 'failed'][i % 3]
    
    WebhookEvent.objects.create(
        provider=provider,
        event_id=f'evt_{uuid.uuid4().hex[:16]}',
        payload={'type': 'payment.succeeded' if i % 2 == 0 else 'payment.failed'},
        status=status_choice
    )

print(f"✓ Created 20 webhook events")
print("\n✅ Test data created successfully!")
print(f"\nYou can now access the admin portal at:")
print(f"  http://localhost:8000/admin-portal/")
print(f"\nLogin credentials:")
print(f"  Username: admin")
print(f"  Password: admin123")
