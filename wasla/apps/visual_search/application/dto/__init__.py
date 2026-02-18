"""
Data Transfer Objects

Defines DTOs for inter-layer communication.
"""

from .visual_search_dto import (
    VisualSearchQueryDTO,
    VisualSearchResponseDTO,
    VisualSearchResultDTO,
)

__all__ = [
    "VisualSearchQueryDTO",
    "VisualSearchResponseDTO",
    "VisualSearchResultDTO",
]
