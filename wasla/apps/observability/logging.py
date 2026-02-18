from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from typing import Any


request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[int | None] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
path_var: ContextVar[str | None] = ContextVar("path", default=None)
method_var: ContextVar[str | None] = ContextVar("method", default=None)


def bind_request_context(*, request_id: str, tenant_id: int | None, user_id: int | None, path: str, method: str):
    request_id_var.set(request_id)
    tenant_id_var.set(tenant_id)
    user_id_var.set(user_id)
    path_var.set(path)
    method_var.set(method)


def clear_request_context():
    request_id_var.set(None)
    tenant_id_var.set(None)
    user_id_var.set(None)
    path_var.set(None)
    method_var.set(None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": int(time.time() * 1000),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": request_id_var.get(),
            "tenant_id": tenant_id_var.get(),
            "user_id": user_id_var.get(),
            "path": path_var.get(),
            "method": method_var.get(),
        }
        for key in ("status_code", "latency_ms", "error_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)
