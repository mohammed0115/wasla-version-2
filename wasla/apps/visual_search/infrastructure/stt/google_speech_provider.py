from __future__ import annotations

import base64

import requests
from django.conf import settings


class GoogleSpeechProvider:
    code = "google_speech"

    def __init__(self):
        self.api_key = getattr(settings, "GOOGLE_SPEECH_API_KEY", "") or ""
        self.timeout = int(getattr(settings, "AI_TIMEOUT_SECONDS", 15))

    def transcribe(
        self,
        *,
        audio_bytes: bytes,
        content_type: str | None = None,
        language: str | None = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("Google Speech API key not configured.")
        if not audio_bytes:
            raise ValueError("Audio payload is empty.")

        language_code = (language or "ar-SA").strip() or "ar-SA"
        request_url = f"https://speech.googleapis.com/v1/speech:recognize?key={self.api_key}"

        payload = {
            "config": {
                "languageCode": language_code,
                "enableAutomaticPunctuation": True,
            },
            "audio": {
                "content": base64.b64encode(audio_bytes).decode("utf-8"),
            },
        }

        response = requests.post(request_url, json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise ValueError("Google Speech transcription failed.")

        data = response.json() if response.content else {}
        results = data.get("results") or []
        transcripts: list[str] = []
        for item in results:
            alternatives = item.get("alternatives") or []
            if not alternatives:
                continue
            transcript = str(alternatives[0].get("transcript") or "").strip()
            if transcript:
                transcripts.append(transcript)

        return " ".join(transcripts).strip()
