import pytest
from django.urls import reverse

from accounts.models import Profile
from tenants.models import TenantMembership, StoreProfile
from subscriptions.models import StoreSubscription


@pytest.mark.django_db
def test_profile_created_for_user(user):
    assert Profile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_persona_steps_and_plan_creates_tenant_membership_and_subscription(auth_client, user):
    # Simulate persona steps by posting to each endpoint
    auth_client.post(reverse("accounts:persona_welcome"))

    auth_client.post(reverse("accounts:persona_country"), {"country": "SA"})
    auth_client.post(reverse("accounts:persona_legal"), {"legal_entity": "individual"})
    auth_client.post(reverse("accounts:persona_existing"), {"has_existing_business": "no"})
    auth_client.post(reverse("accounts:persona_channel"), {"selling_channel": "Instagram"})
    auth_client.post(
        reverse("accounts:persona_category_main"),
        {"category_main": "Electronics", "category_sub": "Mobiles"},
    )

    # Choose plan (creates Tenant + owner membership + subscription)
    resp = auth_client.post(
        reverse("accounts:persona_plans"),
        {"billing_cycle": "monthly", "plan_id": ""},
        follow=False,
    )
    assert resp.status_code in (302, 303)

    p = Profile.objects.get(user=user)
    assert p.plan is not None
    assert p.persona_completed is True

    membership = TenantMembership.objects.filter(user=user, role="owner", is_active=True).select_related("tenant").first()
    assert membership is not None

    store = membership.tenant
    assert StoreProfile.objects.filter(tenant=store, owner=user).exists()

    assert StoreSubscription.objects.filter(store_id=store.id).exists()
