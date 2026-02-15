from __future__ import annotations


class SmsError(Exception):
    """Base exception for SMS module."""


class SmsValidationError(SmsError):
    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


class SmsConfigurationError(SmsError):
    pass


class SmsGatewayError(SmsError):
    def __init__(self, message: str, *, provider: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class SmsSchedulingNotSupportedError(SmsError):
    pass

