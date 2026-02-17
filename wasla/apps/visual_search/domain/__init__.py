"""
Domain Layer

Core business logic and entities, independent of frameworks:
- entities.py: Main domain entities (ProductEmbedding, etc.)
- errors.py: Custom domain exceptions
- value_objects.py: Immutable value objects
"""

from .errors import InvalidImageError, NoResultsFoundError, VisualSearchError

__all__ = [
    "InvalidImageError",
    "NoResultsFoundError",
    "VisualSearchError",
]
