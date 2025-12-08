import tiktoken
from typing import Optional


_encoding: Optional[tiktoken.Encoding] = None


def get_encoding() -> tiktoken.Encoding:
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def count_tokens(text: str) -> int:
    encoding = get_encoding()
    return len(encoding.encode(text))


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    encoding = get_encoding()
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return text

    truncated_tokens = tokens[:max_tokens]
    return encoding.decode(truncated_tokens)
