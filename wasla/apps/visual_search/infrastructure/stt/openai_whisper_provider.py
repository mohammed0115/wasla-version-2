from __future__ import annotations

import io

import requests
from django.conf import settings


class OpenAIWhisperProvider:
    code = "openai_whisper"

    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        self.model = getattr(settings, "OPENAI_WHISPER_MODEL", "whisper-1")
        self.timeout = int(getattr(settings, "AI_TIMEOUT_SECONDS", 15))

    def transcribe(
        self,
        *,
        audio_bytes: bytes,
        content_type: str | None = None,
        language: str | None = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured.")
        if not audio_bytes:
            raise ValueError("Audio payload is empty.")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {
            "file": ("voice_input.wav", io.BytesIO(audio_bytes), content_type or "audio/wav"),
        }
        data = {
            "model": self.model,
            "response_format": "json",
        }
        language_value = (language or "").strip()
        if language_value:
            data["language"] = language_value.split("-")[0]

        response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise ValueError("OpenAI Whisper transcription failed.")

        payload = response.json() if response.content else {}
        return str(payload.get("text") or "").strip()
