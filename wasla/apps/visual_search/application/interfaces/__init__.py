"""
Interfaces (Ports)

Defines abstract interfaces for dependency injection.
These ports are implemented in the infrastructure layer.
"""

from .repository_port import VisualSearchRepositoryPort
from .stt_provider_port import SpeechToTextProviderPort

__all__ = ["VisualSearchRepositoryPort", "SpeechToTextProviderPort"]
