from __future__ import annotations

from django.conf import settings

from .google_provider import GoogleProvider
from .openai_provider import OpenAIProvider


def get_provider():
    provider = (getattr(settings, "AI_PROVIDER", "openai") or "openai").lower()
    if provider == "google":
        return GoogleProvider()
    return OpenAIProvider()
