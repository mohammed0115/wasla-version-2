"""
Visual Search Module

Provides image-based product search functionality using embeddings and similarity matching.

Structure:
- domain/: Core business entities and domain errors
- application/: Use cases and DTOs for orchestration
- infrastructure/: Django models and repositories
- presentation/: Web views and API endpoints

Quick Import:
    from apps.visual_search.models import ProductEmbedding
    from apps.visual_search.application.usecases import VisualSearchUseCase
"""

default_app_config = "apps.visual_search.apps.VisualSearchConfig"
