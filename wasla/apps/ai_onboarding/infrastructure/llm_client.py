from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError


@dataclass(frozen=True)
class LLMResult:
    rationale: str
    suggested_categories: list[str]
    suggested_theme_key: str
    confidence: int


class LLMClientError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: int,
        max_tokens: int,
        model: str = "gpt-5-mini",
    ):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.model = model

    def generate_recommendation(
        self,
        *,
        business_type: str,
        country: str,
        language: str,
        baseline_decision: dict,
    ) -> LLMResult:
        prompt = self._build_prompt(
            business_type=business_type,
            country=country,
            language=language,
            baseline_decision=baseline_decision,
        )

        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": self.max_tokens,
        }

        req = urlrequest.Request(
            "https://api.openai.com/v1/responses",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with urlrequest.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise LLMClientError(str(exc)) from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"Invalid JSON response: {exc}") from exc

        text_payload = self._extract_text_payload(parsed)
        try:
            structured = json.loads(text_payload)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"LLM non-JSON payload: {exc}") from exc

        return self._validate_structured_output(structured)

    @staticmethod
    def _build_prompt(*, business_type: str, country: str, language: str, baseline_decision: dict) -> str:
        return (
            "You are Wasla AI onboarding recommendation assistant.\n"
            "Brand tone: professional, concise, Saudi market friendly Arabic (Fusha + Saudi-friendly).\n"
            "Return JSON ONLY with this exact schema:\n"
            "{\n"
            '  "rationale": "...",\n'
            '  "suggested_categories": ["..."],\n'
            '  "suggested_theme_key": "...",\n'
            '  "confidence": 0\n'
            "}\n"
            "No markdown, no explanation outside JSON.\n"
            f"Input:\n business_type={business_type}\n country={country}\n language={language}\n"
            f"baseline_decision={json.dumps(baseline_decision, ensure_ascii=False)}\n"
            "Constraints: keep categories <=10 elements and confidence 0-100."
        )

    @staticmethod
    def _extract_text_payload(parsed: dict) -> str:
        if isinstance(parsed.get("output_text"), str) and parsed["output_text"].strip():
            return parsed["output_text"].strip()

        output = parsed.get("output") or []
        for item in output:
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()

        raise LLMClientError("No textual output in LLM response")

    @staticmethod
    def _validate_structured_output(data: dict) -> LLMResult:
        if not isinstance(data, dict):
            raise LLMClientError("LLM output must be an object")

        rationale = data.get("rationale")
        suggested_categories = data.get("suggested_categories")
        suggested_theme_key = data.get("suggested_theme_key")
        confidence = data.get("confidence")

        if not isinstance(rationale, str) or not rationale.strip():
            raise LLMClientError("Invalid rationale")
        if not isinstance(suggested_categories, list):
            raise LLMClientError("Invalid suggested_categories")

        cleaned_categories: list[str] = []
        for category in suggested_categories[:10]:
            if isinstance(category, str) and category.strip():
                cleaned_categories.append(category.strip())

        if not isinstance(suggested_theme_key, str) or not suggested_theme_key.strip():
            raise LLMClientError("Invalid suggested_theme_key")

        if not isinstance(confidence, int) or confidence < 0 or confidence > 100:
            raise LLMClientError("Invalid confidence")

        return LLMResult(
            rationale=rationale.strip(),
            suggested_categories=cleaned_categories,
            suggested_theme_key=suggested_theme_key.strip(),
            confidence=confidence,
        )
