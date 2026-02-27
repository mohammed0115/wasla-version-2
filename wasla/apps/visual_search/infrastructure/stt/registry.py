from __future__ import annotations

from django.conf import settings

from apps.visual_search.infrastructure.stt.google_speech_provider import GoogleSpeechProvider
from apps.visual_search.infrastructure.stt.openai_whisper_provider import OpenAIWhisperProvider


def get_stt_provider():
    provider = (getattr(settings, "VISUAL_SEARCH_STT_PROVIDER", "openai_whisper") or "openai_whisper").strip().lower()
    if provider in {"google", "google_speech", "google-speech"}:
        return GoogleSpeechProvider()
    if provider in {"openai", "openai_whisper", "whisper"}:
        return OpenAIWhisperProvider()
    raise ValueError("Unsupported STT provider")
