"""Chunker factory for creating appropriate chunking strategy."""

from typing import Union

from .ast_chunker import ASTChunker
from .line_chunker import LineChunker


def create_chunker(
    strategy: str, token_limit: int = 2048
) -> Union[ASTChunker, LineChunker]:
    """Create a chunker based on the specified strategy.

    Args:
        strategy: Chunking strategy - "ast" for syntax-aware or "line" for token-based
        token_limit: Maximum tokens per chunk

    Returns:
        ASTChunker or LineChunker instance

    Raises:
        ValueError: If strategy is not "ast" or "line"
    """
    if strategy == "ast":
        return ASTChunker(token_limit)
    elif strategy == "line":
        return LineChunker(token_limit)
    else:
        raise ValueError(
            f"Invalid chunking strategy: {strategy}. Must be 'ast' or 'line'"
        )
