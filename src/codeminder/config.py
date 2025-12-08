import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator
from sentence_transformers import SentenceTransformer


class Configuration(BaseModel):
    codebase_path: str = Field(default=".", description="Path to the codebase to index")
    embedding_model: str = Field(
        default="jinaai/jina-embeddings-v2-base-code",
        description="sentence-transformers model name",
    )
    token_limit: int = Field(default=2048, ge=1, le=8192, description="Maximum tokens per chunk")
    max_search_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of search results to return",
    )
    concurrency_limit: int = Field(
        default=4, ge=1, le=16, description="Number of files to process in parallel"
    )
    debounce_ms: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="File watcher debounce delay in milliseconds",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    persist_index: bool = Field(
        default=True, description="Whether to persist the vector index to disk"
    )

    @field_validator("codebase_path")
    @classmethod
    def validate_codebase_path(cls, v: str) -> str:
        path = Path(v).resolve()
        if not path.exists():
            raise ValueError(f"Codebase path does not exist: {v}")
        if not path.is_dir():
            raise ValueError(f"Codebase path is not a directory: {v}")
        return str(path)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper_v

    @model_validator(mode="after")
    def validate_token_limit(self) -> "Configuration":
        model = SentenceTransformer(self.embedding_model, trust_remote_code=True)
        max_length = model.get_max_seq_length()
        if max_length is None:
            raise ValueError("Could not determine model's maximum sequence length")
        elif self.token_limit > max_length:
            raise ValueError(
                f"Token limit {self.token_limit} exceeds model's maximum sequence length of {max_length}"
            )
        return self

    @classmethod
    def load_from_file(cls, config_path: str = ".codeminder.json") -> "Configuration":
        path = Path(config_path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def save_to_file(self, config_path: str = ".codeminder.json") -> None:
        with open(config_path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)
