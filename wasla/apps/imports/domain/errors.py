class ImportErrorBase(Exception):
    def __init__(self, message: str, message_key: str | None = None, field: str = "", raw_value: str = ""):
        super().__init__(message)
        self.message_key = message_key or "import.error"
        self.field = field
        self.raw_value = raw_value


class ImportValidationError(ImportErrorBase):
    pass


class ImportJobNotFoundError(ImportErrorBase):
    pass
