"""Errors raised by services; messages must be fixed, safe public text."""


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        details: list[dict[str, str]] | None = None,
    ) -> None:
        """Details contain fixed public reason codes/field names, never raw values or exceptions."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = [dict(detail) for detail in details] if details is not None else []
