from __future__ import annotations

import hashlib


def generate_idempotency_key(order_id: int, client_token: str) -> str:
    token = (client_token or "").strip()
    if not token:
        raise ValueError("client_token is required to generate idempotency key")
    raw = f"{order_id}:{token}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
