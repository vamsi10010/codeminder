"""Adaptive code chunker using AST-based "Largest Valid Node" strategy."""

from typing import List

from codeminder.parser.ast_parser import ASTParser
from codeminder.parser.token_counter import count_tokens
from codeminder.storage.models import CodeChunk


class Chunker:
    """Adaptive code chunker using "Largest Valid Node" algorithm."""

    def __init__(self, token_limit: int = 2048):
        self.token_limit = token_limit

    def chunk(self, parser: ASTParser) -> List[CodeChunk]:
        """Chunk the parsed file into logical code units."""
        chunks: List[CodeChunk] = []
        cursor = parser.tree.walk()
        self._chunk_with_cursor(parser, cursor, chunks)
        return sorted(chunks, key=lambda c: c.start_line)

    def _chunk_with_cursor(self, parser: ASTParser, cursor, chunks: List[CodeChunk]) -> None:
        """Recursively chunk using TreeCursor for efficient traversal."""
        node = cursor.node

        if not node.is_named:
            return

        node_text = parser.get_node_text(node)
        token_count = count_tokens(node_text)

        if token_count <= self.token_limit:
            chunks.append(self._create_chunk(parser, node, node_text, token_count))
            return

        if not cursor.goto_first_child():
            chunks.append(self._create_chunk(parser, node, node_text, token_count))
            return

        while True:
            self._chunk_with_cursor(parser, cursor, chunks)
            if not cursor.goto_next_sibling():
                break

        cursor.goto_parent()

    def _create_chunk(self, parser: ASTParser, node, text: str, token_count: int) -> CodeChunk:
        """Create a CodeChunk from an AST node."""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        context_path = f"{parser.file_path.name}:{start_line}-{end_line}"

        return CodeChunk(
            source_code=text,
            context_path=context_path,
            start_line=start_line,
            end_line=end_line,
            token_count=token_count,
            node_type=node.type,
            language=parser.language_name,
        )
