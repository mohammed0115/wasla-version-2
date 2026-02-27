"""
Retry and resilience wrapper for payment provider API calls.

Implements:
- Exponential backoff
- Request/response logging
- Fault tolerance
- Idempotency propagation
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional

from django.utils import timezone
from django.db import transaction

from apps.payments.security import RetryStrategy, log_payment_event

logger = logging.getLogger(__name__)


def execute_with_retry(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: int = 1,
    operation_name: str = "payment_operation",
    store_id: Optional[int] = None,
    order_id: Optional[int] = None,
    payment_attempt_id: Optional[int] = None,
    **kwargs,
) -> Any:
    """
    Execute a function with exponential backoff retry strategy.
    
    Retries on transient exceptions (timeout, connection error).
    Fails fast on permanent errors.
    
    Args:
        func: Callable to execute
        *args: Positional arguments to func
        max_retries: Maximum number of retries
        initial_delay: Initial retry delay in seconds
        operation_name: Name of operation for logging
        store_id: Store ID for logging context
        order_id: Order ID for logging context
        payment_attempt_id: PaymentAttempt ID to update
        **kwargs: Keyword arguments to func
    
    Returns:
        Function result
    
    Raises:
        Exception: On permanent failure or exhausted retries
    """
    retry_count = 0
    last_exception = None
    
    while retry_count <= max_retries:
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log success
            log_payment_event(
                event_type=operation_name,
                store_id=store_id or 0,
                order_id=order_id or 0,
                provider=kwargs.get("provider", "unknown"),
                status="success",
                idempotency_key=kwargs.get("idempotency_key", ""),
                duration_ms=duration_ms,
            )
            
            # Update payment attempt if provided
            if payment_attempt_id:
                _update_payment_attempt(
                    payment_attempt_id,
                    retry_count=retry_count,
                    status="confirmation_pending",
                )
            
            return result
        
        except Exception as e:
            last_exception = e
            
            # Check if error is retryable
            if not _is_retryable_error(e):
                log_payment_event(
                    event_type=operation_name,
                    store_id=store_id or 0,
                    order_id=order_id or 0,
                    provider=kwargs.get("provider", "unknown"),
                    status="failed",
                    idempotency_key=kwargs.get("idempotency_key", ""),
                    error=str(e),
                )
                raise
            
            retry_count += 1
            
            if retry_count > max_retries:
                log_payment_event(
                    event_type=f"{operation_name}_failed_after_retries",
                    store_id=store_id or 0,
                    order_id=order_id or 0,
                    provider=kwargs.get("provider", "unknown"),
                    status="exhausted_retries",
                    idempotency_key=kwargs.get("idempotency_key", ""),
                    error=str(e),
                    metadata={
                        "retry_count": retry_count,
                        "max_retries": max_retries,
                    },
                )
                raise
            
            # Calculate backoff
            next_retry = RetryStrategy.calculate_next_retry(
                retry_count - 1,
                initial_delay=initial_delay,
            )
            wait_seconds = (next_retry - timezone.now()).total_seconds()
            
            logger.warning(
                f"{operation_name} failed (attempt {retry_count}/{max_retries}), "
                f"retrying in {wait_seconds:.1f}s: {str(e)}"
            )
            
            # Update payment attempt with retry info
            if payment_attempt_id:
                _update_payment_attempt(
                    payment_attempt_id,
                    retry_count=retry_count,
                    next_retry_after=next_retry,
                    last_error=str(e),
                    status="retry_pending",
                )
            
            # Wait before retry
            time.sleep(wait_seconds)
    
    raise last_exception


def _is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception is retryable.
    
    Retryable:
    - Timeout exceptions
    - Connection errors
    - HTTP 5xx errors
    - Rate limiting (429)
    
    Non-retryable:
    - Authentication errors (401, 403)
    - Validation errors (400, 422)
    - Not found (404)
    -Permanent failures
    """
    exception_name = type(exception).__name__.lower()
    exception_str = str(exception).lower()
    
    # Retryable patterns
    retryable_patterns = [
        "timeout",
        "connection",
        "network",
        "socket",
        "unavailable",
        "service_unavailable",
        "http_504",
        "http_503",
        "http_502",
        "500",
        "503",
        "429",  # Rate limiting
        "temporarily",
        "try_again",
    ]
    
    for pattern in retryable_patterns:
        if pattern in exception_name or pattern in exception_str:
            return True
    
    # Non-retryable patterns (fail fast)
    non_retryable_patterns = [
        "authentication",
        "unauthorized",
        "forbidden",
        "invalid",
        "malformed",
        "not found",
        "404",
        "401",
        "403",
        "400",
        "422",
        "card_declined",
        "insufficient_funds",
    ]
    
    for pattern in non_retryable_patterns:
        if pattern in exception_name or pattern in exception_str:
            return False
    
    # Default: retryable (be conservative)
    return True


@transaction.atomic
def _update_payment_attempt(
    payment_attempt_id: int,
    retry_count: int = 0,
    next_retry_after: Optional[datetime] = None,
    last_error: str = "",
    status: Optional[str] = None,
) -> None:
    """
    Update PaymentAttempt with retry information.
    
    Args:
        payment_attempt_id: PaymentAttempt ID
        retry_count: New retry count
        next_retry_after: Next retry datetime
        last_error: Error message if any
        status: New status if provided
    """
    try:
        from apps.payments.models import PaymentAttempt
        
        attempt = PaymentAttempt.objects.select_for_update().get(
            id=payment_attempt_id
        )
        
        attempt.retry_count = retry_count
        
        if next_retry_after:
            attempt.next_retry_after = next_retry_after
            attempt.retry_pending = True
        
        if last_error:
            attempt.raw_response["last_error"] = last_error
        
        if status:
            attempt.status = status
        
        attempt.last_retry_at = timezone.now()
        attempt.save(
            update_fields=[
                "retry_count",
                "next_retry_after",
                "retry_pending",
                "last_retry_at",
                "raw_response",
                "status",
            ]
        )
    
    except Exception as e:
        logger.exception(f"Error updating payment attempt {payment_attempt_id}: {e}")


async def execute_async_with_retry(
    coro: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: int = 1,
    **kwargs,
) -> Any:
    """
    Execute async function with retry.
    
    Async version of execute_with_retry.
    
    Args:
        coro: Async callable
        *args: Positional arguments
        max_retries: Maximum retries
        initial_delay: Initial delay
        **kwargs: Keyword arguments
    
    Returns:
        Coroutine result
    """
    retry_count = 0
    last_exception = None
    
    while retry_count <= max_retries:
        try:
            return await coro(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if not _is_retryable_error(e):
                raise
            
            retry_count += 1
            
            if retry_count > max_retries:
                raise
            
            next_retry = RetryStrategy.calculate_next_retry(retry_count - 1, initial_delay)
            wait_seconds = (next_retry - timezone.now()).total_seconds()
            
            logger.warning(
                f"Async operation failed (attempt {retry_count}/{max_retries}), "
                f"retrying in {wait_seconds:.1f}s: {str(e)}"
            )
            
            await asyncio.sleep(wait_seconds)
    
    raise last_exception


def with_retry(
    max_retries: int = 3,
    initial_delay: int = 1,
    operation_name: str = "",
):
    """
    Decorator for functions that need retry logic.
    
    Usage:
        @with_retry(max_retries=3, operation_name="initiate_payment")
        def initiate_payment(self, amount):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation = operation_name or func.__name__
            return execute_with_retry(
                func,
                *args,
                max_retries=max_retries,
                initial_delay=initial_delay,
                operation_name=operation,
                **kwargs,
            )
        return wrapper
    return decorator
