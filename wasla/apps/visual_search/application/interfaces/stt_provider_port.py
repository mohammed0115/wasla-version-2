from __future__ import annotations

from typing import Protocol


class SpeechToTextProviderPort(Protocol):
    code: str

    def transcribe(
        self,
        *,
        audio_bytes: bytes,
        content_type: str | None = None,
        language: str | None = None,
    ) -> str:
        ...
