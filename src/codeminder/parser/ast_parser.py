"""AST parser using Tree-sitter for multi-language code parsing."""

from typing import cast
from pathlib import Path
from tree_sitter import Tree
from tree_sitter_language_pack import get_parser, SupportedLanguage


class ASTParser:
    """Parse source code files into AST using Tree-sitter."""

    @classmethod
    def parse_file(cls, file_path: Path | str) -> Tree:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        source_bytes = file_path.read_bytes()
        language_name = cast(SupportedLanguage, cls.detect_language(file_path))
        parser = get_parser(language_name)
        tree = parser.parse(source_bytes)
        return tree

    @classmethod
    def detect_language(cls, file_path: Path | str) -> str:
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

        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        if suffix not in extension_map:
            raise ValueError(f"Unsupported file extension: {suffix}")

        return extension_map[suffix]
