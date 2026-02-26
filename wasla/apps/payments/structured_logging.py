from __future__ import annotations

import json
import logging

logger = logging.getLogger("payments.structured")


def log_payment_structured(
    *,
    event: str,
    store_id: int | None,
    order_id: int | None,
    provider: str,
    idempotency_key: str,
    status: str,
    duration_ms: int = 0,
    extra: dict | None = None,
) -> None:
    payload = {
        "event": event,
        "store_id": store_id,
        "order_id": order_id,
        "provider": provider,
        "idempotency_key": idempotency_key,
        "status": status,
        "duration_ms": duration_ms,
    }
    if extra:
        payload.update(extra)
    logger.info(json.dumps(payload, default=str, separators=(",", ":")))
