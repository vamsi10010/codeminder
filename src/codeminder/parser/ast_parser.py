"""AST parser using Tree-sitter for multi-language code parsing."""

from typing import cast
from pathlib import Path
from tree_sitter_language_pack import get_parser, SupportedLanguage


class ASTParser:
    """Parse source code files into AST using Tree-sitter."""

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self.language_name = self._detect_language()
        self.source_bytes = self.file_path.read_text(encoding="utf-8").encode("utf-8")

        parser = get_parser(self.language_name)
        self.tree = parser.parse(self.source_bytes)

    def _detect_language(self) -> SupportedLanguage:
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".hxx": "cpp",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".md": "markdown",
            ".sh": "bash",
            ".bash": "bash",
            ".sql": "sql",
            ".r": "r",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".pl": "perl",
            ".pm": "perl",
            ".lua": "lua",
        }

        suffix = self.file_path.suffix.lower()
        if suffix not in extension_map:
            raise ValueError(f"Unsupported file extension: {suffix}")

        language_name = cast(SupportedLanguage, extension_map[suffix])

        return language_name

    def get_node_text(self, node) -> str:
        """Extract text content from a node."""
        return self.source_bytes[node.start_byte : node.end_byte].decode("utf-8")

    def has_syntax_errors(self) -> bool:
        """Check if tree contains syntax errors."""
        return self._has_error_nodes(self.tree.root_node)

    def _has_error_nodes(self, node) -> bool:
        if node.type == "ERROR" or node.is_missing:
            return True
        return any(self._has_error_nodes(child) for child in node.children)
