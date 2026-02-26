"""Retry logic with exponential backoff for payment provider API calls."""
from __future__ import annotations

import time
from typing import TypeVar, Callable, Any

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        initial_delay_ms: int = 100,
        max_delay_ms: int = 5000,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.exponential_base = exponential_base
        self.jitter = jitter


class RetryableError(Exception):
    """Base class for errors that should trigger retry."""
    pass


class PaymentProviderRetry:
    """Retry executor with exponential backoff for provider API calls."""

    @staticmethod
    def execute_with_retry(
        *,
        operation: Callable[[], T],
        operation_name: str = "provider_operation",
        config: RetryConfig | None = None,
        should_retry: Callable[[Exception], bool] | None = None,
        on_retry: Callable[[int, Exception], None] | None = None,
        before_retry: Callable[[int, Exception], None] | None = None,
        on_final_failure: Callable[[int, Exception], None] | None = None,
    ) -> T:
        """
        Execute operation with retry logic.
        
        Args:
            operation: The function to execute
            config: Retry configuration
            should_retry: Function to determine if exception should trigger retry
            on_retry: Callback on each retry attempt
            
        Returns:
            Result of operation
            
        Raises:
            Last exception if all retries exhausted
        """
        if config is None:
            config = RetryConfig()
        
        if should_retry is None:
            should_retry = PaymentProviderRetry._default_should_retry
        
        last_error: Exception | None = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                
                if attempt >= config.max_attempts:
                    if on_final_failure:
                        on_final_failure(attempt, exc)
                    raise
                
                if not should_retry(exc):
                    raise
                
                # Calculate delay with exponential backoff
                delay_ms = min(
                    config.initial_delay_ms * (config.exponential_base ** (attempt - 1)),
                    config.max_delay_ms,
                )
                
                # Add jitter to prevent thundering herd
                if config.jitter:
                    import random
                    jitter_factor = 0.5 + random.random()  # 0.5 to 1.5
                    delay_ms *= jitter_factor
                
                if on_retry:
                    on_retry(attempt, exc)
                if before_retry:
                    before_retry(attempt + 1, exc)
                
                time.sleep(delay_ms / 1000.0)
        
        # Should not reach here, but satisfy type checker
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected retry state")

    @staticmethod
    def _default_should_retry(exc: Exception) -> bool:
        """Default logic for determining if exception should trigger retry."""
        # Retry on network errors, timeouts, rate limits
        exc_name = exc.__class__.__name__.lower()
        exc_msg = str(exc).lower()
        
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "429",
            "502",
            "503",
            "504",
        ]
        
        for pattern in retryable_patterns:
            if pattern in exc_name or pattern in exc_msg:
                return True
        
        # Don't retry on explicit client errors (4xx except 429)
        if "400" in exc_msg or "401" in exc_msg or "403" in exc_msg or "404" in exc_msg:
            return False
        
        # Retry on explicitly marked errors
        if isinstance(exc, RetryableError):
            return True

        # Default to retry for transient/unknown provider failures.
        return True
