from __future__ import annotations

from typing import Optional
import ipaddress


def extract_subdomain(host: str) -> Optional[str]:
    if not host:
        return None

    host = host.strip().lower()
    if not host:
        return None

    if host.startswith("["):
        end = host.find("]")
        if end != -1:
            host = host[1:end]
        else:
            host = host.lstrip("[")
    else:
        host = host.split(":", 1)[0]

    if not host:
        return None

    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass

    if host == "localhost":
        return None

    if host.endswith(".localhost"):
        sub = host[: -len(".localhost")]
        if not sub:
            return None
        return sub.split(".", 1)[0] or None

    parts = host.split(".")
    if len(parts) < 3:
        return None

    return parts[0] or None
