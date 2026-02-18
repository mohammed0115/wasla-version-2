"""
Infrastructure Layer

Django-specific implementations and external service integrations.

Exports:
- ProductEmbedding: Django ORM model for product embeddings
- DjangoVisualSearchRepository: Repository implementation
"""

from .models import ProductEmbedding
from .repositories import DjangoVisualSearchRepository

__all__ = ["ProductEmbedding", "DjangoVisualSearchRepository"]
