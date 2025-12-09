"""Adaptive code chunker using AST-based "Largest Valid Node" strategy."""

from typing import List

from tree_sitter import Tree

from codeminder.parser.ast_parser import ASTParser
from codeminder.parser.token_counter import count_tokens
from codeminder.storage.models import CodeChunk, File


class Chunker:
    """Adaptive code chunker using "Largest Valid Node" algorithm."""

    def __init__(self, token_limit: int = 2048):
        self.token_limit = token_limit

    def chunk(self, file: File) -> List[CodeChunk]:
        """Chunk the parsed file into logical code units."""
        chunks: List[CodeChunk] = []
        tree = ASTParser.parse_file(file.absolute_path)
        cursor = tree.walk()
        self._chunk_with_cursor(tree, file, cursor, chunks)
        file.chunk_count = len(chunks)
        return sorted(chunks, key=lambda c: c.start_line)

    def _chunk_with_cursor(self, tree: Tree, file: File, cursor, chunks: List[CodeChunk]) -> None:
        """Recursively chunk using TreeCursor for efficient traversal."""
        node = cursor.node

        if not node.is_named:
            return

        node_text = node.text.decode("utf-8")
        token_count = count_tokens(node_text)

        if token_count <= self.token_limit:
            chunks.append(self._create_chunk(file, node, node_text, token_count))
            return

        if not cursor.goto_first_child():
            chunks.append(self._create_chunk(file, node, node_text, token_count))
            return

        while True:
            self._chunk_with_cursor(tree, file, cursor, chunks)
            if not cursor.goto_next_sibling():
                break

        cursor.goto_parent()

    def _create_chunk(self, file: File, node, text: str, token_count: int) -> CodeChunk:
        """Create a CodeChunk from an AST node."""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        context_path = f"{file.relative_path}:{start_line}-{end_line}"

        return CodeChunk(
            file_id=file.file_id,
            source_code=text,
            context_path=context_path,
            start_line=start_line,
            end_line=end_line,
            token_count=token_count,
            node_type=node.type,
        )
