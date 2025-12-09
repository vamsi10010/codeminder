import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Configuration(BaseModel):
    codebase_path: str = Field(default=".", description="Path to the codebase to index")
    chunking_strategy: str = Field(
        default="ast",
        description="Chunking strategy: 'ast' for syntax-aware or 'line' for token-based",
    )
    embedding_model: str = Field(
        default="jinaai/jina-embeddings-v2-base-code",
        description="sentence-transformers model name",
    )
    token_limit: int = Field(
        default=2048, ge=1, le=8192, description="Maximum tokens per chunk"
    )
    max_search_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of search results to return",
    )
    concurrency_limit: int = Field(
        default=4, ge=1, le=16, description="Number of files to process in parallel"
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

    @field_validator("chunking_strategy")
    @classmethod
    def validate_chunking_strategy(cls, v: str) -> str:
        valid_strategies = {"ast", "line"}
        lower_v = v.lower()
        if lower_v not in valid_strategies:
            raise ValueError(
                f"Invalid chunking strategy: {v}. Must be one of {valid_strategies}"
            )
        return lower_v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper_v

    @field_validator("token_limit")
    @classmethod
    def validate_token_limit_range(cls, v: int) -> int:
        """Validate token limit is in reasonable range.

        Note: Actual model max_seq_length validation happens when embedder loads the model,
        as we don't want to download the model during config validation.
        """
        if v < 512:
            raise ValueError("Token limit must be at least 512")
        if v > 8192:
            raise ValueError("Token limit cannot exceed 8192")
        return v

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
