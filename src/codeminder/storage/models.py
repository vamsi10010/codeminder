from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4


class ParseStatus(str, Enum):
    SUCCESS = "SUCCESS"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class File:
    file_id: UUID = field(default_factory=uuid4)
    absolute_path: str = ""
    relative_path: str = ""
    language: str = ""
    last_modified: datetime = field(default_factory=datetime.now)
    last_indexed: datetime = field(default_factory=datetime.now)
    parse_status: ParseStatus = ParseStatus.SUCCESS
    error_message: Optional[str] = None
    chunk_count: int = 0

    def to_dict(self) -> dict:
        return {
            "file_id": str(self.file_id),
            "absolute_path": self.absolute_path,
            "relative_path": self.relative_path,
            "language": self.language,
            "last_modified": self.last_modified.isoformat(),
            "last_indexed": self.last_indexed.isoformat(),
            "parse_status": self.parse_status.value,
            "error_message": self.error_message,
            "chunk_count": self.chunk_count,
        }


@dataclass
class CodeChunk:
    chunk_id: UUID = field(default_factory=uuid4)
    file_id: UUID = field(default_factory=uuid4)
    source_code: str = ""
    context_path: str = ""
    start_line: int = 0
    end_line: int = 0
    token_count: int = 0
    node_type: str = ""
    sequence_number: int = 0
    language: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "chunk_id": str(self.chunk_id),
            "file_id": str(self.file_id),
            "source_code": self.source_code,
            "context_path": self.context_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "token_count": self.token_count,
            "node_type": self.node_type,
            "sequence_number": self.sequence_number,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Embedding:
    embedding_id: UUID = field(default_factory=uuid4)
    chunk_id: UUID = field(default_factory=uuid4)
    vector: List[float] = field(default_factory=list)
    model_version: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "embedding_id": str(self.embedding_id),
            "chunk_id": str(self.chunk_id),
            "vector": self.vector,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat(),
        }
