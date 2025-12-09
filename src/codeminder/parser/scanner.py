"""File scanner for discovering code files in the codebase."""

import os
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)


class FileScanner:
    """Scan codebase directory for code files to index."""

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        ".py",  # Python
    }

    # Patterns to exclude from scanning
    EXCLUDED_PATTERNS = {
        # Python
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".Python",
        # Virtual environments
        "venv",
        ".venv",
        "env",
        ".env",
        "virtualenv",
        # Version control
        ".git",
        ".svn",
        ".hg",
        ".bzr",
        # IDE/Editor
        ".vscode",
        ".idea",
        ".eclipse",
        ".settings",
        # Build artifacts
        "build",
        "dist",
        "*.egg-info",
        ".eggs",
        # Dependencies
        "node_modules",
        "vendor",
        # OS
        ".DS_Store",
        "Thumbs.db",
        # Test coverage
        ".coverage",
        "htmlcov",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    def __init__(self, codebase_path: str):
        """Initialize scanner with codebase root path.

        Args:
            codebase_path: Root directory to scan for code files.
        """
        self.codebase_path = Path(codebase_path).resolve()
        if not self.codebase_path.exists():
            raise ValueError(f"Codebase path does not exist: {codebase_path}")
        if not self.codebase_path.is_dir():
            raise ValueError(f"Codebase path is not a directory: {codebase_path}")

    def scan(self) -> list[Path]:
        """Recursively scan codebase for supported code files.

        Returns:
            List of absolute Path objects for discovered code files.
        """
        logger.info(f"Scanning codebase: {self.codebase_path}")
        discovered_files: list[Path] = []

        for root, dirs, files in os.walk(self.codebase_path):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if not self._is_excluded(d)]

            # Filter files by extension and exclusion patterns
            for file in files:
                file_path = Path(root) / file
                if self._should_include(file_path):
                    discovered_files.append(file_path)

        logger.info(f"Discovered {len(discovered_files)} code files")
        return sorted(discovered_files)

    def _should_include(self, file_path: Path) -> bool:
        """Check if file should be included in scan.

        Args:
            file_path: Path to check.

        Returns:
            True if file should be indexed, False otherwise.
        """
        # Check extension
        if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
            return False

        # Check exclusion patterns
        if self._is_excluded(file_path.name):
            return False

        # Check if any parent directory is excluded
        try:
            relative_path = file_path.relative_to(self.codebase_path)
            for part in relative_path.parts[:-1]:  # Exclude filename itself
                if self._is_excluded(part):
                    return False
        except ValueError:
            # File is not relative to codebase_path
            return False

        return True

    def _is_excluded(self, name: str) -> bool:
        """Check if a filename or directory matches exclusion patterns.

        Args:
            name: Filename or directory name to check.

        Returns:
            True if name matches exclusion pattern, False otherwise.
        """
        # Direct match
        if name in self.EXCLUDED_PATTERNS:
            return True

        # Pattern match (simple glob-style with * wildcard)
        for pattern in self.EXCLUDED_PATTERNS:
            if "*" in pattern:
                # Simple wildcard matching
                prefix, suffix = pattern.split("*", 1)
                if name.startswith(prefix) and name.endswith(suffix):
                    return True

        return False

    def get_relative_path(self, absolute_path: Path) -> str:
        """Convert absolute path to relative path from codebase root.

        Args:
            absolute_path: Absolute path to file.

        Returns:
            Relative path as string.
        """
        try:
            return str(absolute_path.relative_to(self.codebase_path))
        except ValueError:
            # Fallback to name if not relative to codebase
            return absolute_path.name
