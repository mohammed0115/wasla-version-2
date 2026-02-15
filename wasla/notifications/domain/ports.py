from __future__ import annotations

from typing import Protocol


class EmailGateway(Protocol):
    name: str

    def send_email(self, *, subject: str, body: str, to_email: str, from_email: str) -> None: ...

