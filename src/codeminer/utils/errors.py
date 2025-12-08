from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    CONFIG_ERROR = "CONFIG_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"
    EMBEDDING_ERROR = "EMBEDDING_ERROR"
    WATCHER_ERROR = "WATCHER_ERROR"
    INDEX_NOT_READY = "INDEX_NOT_READY"
    SEARCH_ERROR = "SEARCH_ERROR"


class CodeMinderError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: Optional[dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code.value}] {message}")

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }


class ConfigError(CodeMinderError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.CONFIG_ERROR, message, details)


class ParseError(CodeMinderError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.PARSE_ERROR, message, details)


class DBUnavailableError(CodeMinderError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.DB_UNAVAILABLE, message, details)


class EmbeddingError(CodeMinderError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.EMBEDDING_ERROR, message, details)


class WatcherError(CodeMinderError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.WATCHER_ERROR, message, details)


class IndexNotReadyError(CodeMinderError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.INDEX_NOT_READY, message, details)


class SearchError(CodeMinderError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.SEARCH_ERROR, message, details)
