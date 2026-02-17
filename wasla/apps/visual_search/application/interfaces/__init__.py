"""
Interfaces (Ports)

Defines abstract interfaces for dependency injection.
These ports are implemented in the infrastructure layer.
"""

from .repository_port import VisualSearchRepositoryPort

__all__ = ["VisualSearchRepositoryPort"]
