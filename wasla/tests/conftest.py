import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    """Active user with auto-created Profile (signal)."""
    User = get_user_model()
    u = User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        password="Passw0rd!",
        first_name="Test User",
        is_active=True,
    )
    return u


@pytest.fixture
def auth_client(client, user):
    """Django test client logged-in as the fixture user."""
    client.force_login(user)
    return client
