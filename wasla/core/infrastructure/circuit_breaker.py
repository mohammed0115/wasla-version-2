from __future__ import annotations

import time
from dataclasses import dataclass
from django.core.cache import cache


class CircuitOpenError(Exception):
    """Raised when circuit is open and calls are blocked."""


@dataclass(frozen=True)
class CircuitBreakerConfig:
    failure_threshold: int = 5
    reset_timeout: int = 60  # seconds


class CircuitBreaker:
    """
    Simple cache-backed circuit breaker.

    State is stored in cache keys:
    - <name>:state -> "closed" | "open"
    - <name>:failures -> int
    - <name>:open_until -> epoch seconds
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

    def _key(self, suffix: str) -> str:
        return f"cb:{self.name}:{suffix}"

    def allow_request(self) -> bool:
        state = cache.get(self._key("state"), "closed")
        if state != "open":
            return True
        open_until = cache.get(self._key("open_until"), 0)
        if time.time() >= open_until:
            # half-open: allow a single request by closing temporarily
            cache.set(self._key("state"), "closed", timeout=self.config.reset_timeout)
            cache.set(self._key("failures"), 0, timeout=self.config.reset_timeout)
            return True
        return False

    def record_success(self) -> None:
        cache.set(self._key("state"), "closed", timeout=self.config.reset_timeout)
        cache.set(self._key("failures"), 0, timeout=self.config.reset_timeout)

    def record_failure(self) -> None:
        failures = int(cache.get(self._key("failures"), 0)) + 1
        cache.set(self._key("failures"), failures, timeout=self.config.reset_timeout)
        if failures >= self.config.failure_threshold:
            cache.set(self._key("state"), "open", timeout=self.config.reset_timeout)
            cache.set(
                self._key("open_until"),
                int(time.time() + self.config.reset_timeout),
                timeout=self.config.reset_timeout,
            )

    def call(self, func, *args, **kwargs):
        if not self.allow_request():
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        try:
            result = func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        else:
            self.record_success()
            return result

