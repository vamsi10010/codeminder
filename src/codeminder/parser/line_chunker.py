"""Line-based code chunker using token-count sliding window strategy."""

from ..parser.token_counter import count_tokens
from ..storage.models import CodeChunk, File


class LineChunker:
    """Simple line-based chunker that splits by raw token count.

    Does not use AST parsing. Faster but may split code mid-function or mid-statement.
    Each chunk has node_type="line_chunk" to indicate it may not be syntactically complete.
    """

    def __init__(self, token_limit: int = 2048):
        self.token_limit = token_limit

    def chunk(self, file: File) -> list[CodeChunk]:
        """Chunk the file by line boundaries and token count."""
        chunks: list[CodeChunk] = []

        with open(file.absolute_path, encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            file.chunk_count = 0
            return chunks

        current_lines: list[str] = []
        current_start_line = 1
        current_token_count = 0

        for line_num, line in enumerate(lines, start=1):
            line_tokens = count_tokens(line)

            if current_token_count + line_tokens > self.token_limit and current_lines:
                chunk = self._create_chunk(
                    file,
                    current_lines,
                    current_start_line,
                    line_num - 1,
                    current_token_count,
                )
                chunks.append(chunk)
                current_lines = []
                current_start_line = line_num
                current_token_count = 0

            current_lines.append(line)
            current_token_count += line_tokens

        if current_lines:
            chunk = self._create_chunk(
                file,
                current_lines,
                current_start_line,
                len(lines),
                current_token_count,
            )
            chunks.append(chunk)

        file.chunk_count = len(chunks)
        return chunks

    def _create_chunk(
        self,
        file: File,
        lines: list[str],
        start_line: int,
        end_line: int,
        token_count: int,
    ) -> CodeChunk:
        """Create a CodeChunk from accumulated lines."""
        source_code = "".join(lines).rstrip()
        context_path = f"{file.relative_path}:{start_line}-{end_line}"

        return CodeChunk(
            file_id=file.file_id,
            source_code=source_code,
            context_path=context_path,
            start_line=start_line,
            end_line=end_line,
            token_count=token_count,
            node_type="line_chunk",
        )
