"""Domain error taxonomy and exception definitions for Hina."""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    POLICY_DENIED = "POLICY_DENIED"
    MEMORY_UNAVAILABLE = "MEMORY_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class HinaError(Exception):
    """Base domain exception for HINA system."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code


class AuthRequiredError(HinaError):
    def __init__(
        self,
        message: str = "Authentication credentials required",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ErrorCode.AUTH_REQUIRED, message, details, status_code=401)


class ForbiddenError(HinaError):
    def __init__(
        self, message: str = "Access forbidden", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(ErrorCode.FORBIDDEN, message, details, status_code=403)


class InvalidSchemaError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.INVALID_SCHEMA, message, details, status_code=422)


class PolicyDeniedError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.POLICY_DENIED, message, details, status_code=403)


class ConfirmationRequiredError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.CONFIRMATION_REQUIRED, message, details, status_code=403)


class ProviderUnavailableError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.PROVIDER_UNAVAILABLE, message, details, status_code=503)


class ToolTimeoutError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.TOOL_TIMEOUT, message, details, status_code=504)


class SandboxTimeoutError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.SANDBOX_TIMEOUT, message, details, status_code=504)


class DeviceOfflineError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.DEVICE_OFFLINE, message, details, status_code=503)


class MemoryUnavailableError(HinaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.MEMORY_UNAVAILABLE, message, details, status_code=503)
