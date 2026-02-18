from __future__ import annotations


class EmailError(Exception):
    pass


class EmailValidationError(EmailError):
    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


class EmailGatewayError(EmailError):
    pass

