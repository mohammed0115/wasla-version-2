from __future__ import annotations

from apps.catalog.models import Category


DEFAULT_GLOBAL_CATEGORIES = [
    "Fashion",
    "Beauty",
    "Electronics",
    "Home",
    "Sports",
    "Kids",
    "Groceries",
]


def ensure_global_categories() -> list[Category]:
    """Seed global categories (store_id=0) once for onboarding choices."""
    existing = list(Category.objects.filter(store_id=0).order_by("name"))
    if existing:
        return existing

    created: list[Category] = []
    for name in DEFAULT_GLOBAL_CATEGORIES:
        category, _ = Category.objects.get_or_create(store_id=0, name=name)
        created.append(category)
    return list(Category.objects.filter(store_id=0).order_by("name"))


def get_global_categories() -> list[Category]:
    """Return global categories for onboarding/business selection."""
    return list(Category.objects.filter(store_id=0).order_by("name"))
