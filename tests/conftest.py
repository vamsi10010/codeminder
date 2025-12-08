"""Shared pytest fixtures for all tests."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create temporary directory for test isolation."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_config_dict():
    """Sample configuration dictionary."""
    return {
        "codebase_path": "/home/user/project",
        "embedding_model": "jinaai/jina-embeddings-v2-base-code",
        "vector_db_path": ".codeminder/vector_db",
        "token_limit": 2048,
        "concurrency_limit": 4,
        "debounce_ms": 500,
        "excluded_patterns": [
            "**/__pycache__/**",
            "**/*.pyc",
            "**/.git/**",
            "**/node_modules/**",
            "**/.venv/**",
        ],
    }


@pytest.fixture
def simple_python_file():
    """Simple Python file content for testing."""
    return '''
def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


class Calculator:
    """Simple calculator class."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b
'''


@pytest.fixture
def complex_python_file():
    """Complex Python file with nested structures."""
    return '''
import os
from typing import List, Dict, Optional

class DataProcessor:
    """Process and validate data."""

    def __init__(self, config: Dict):
        self.config = config
        self.results = []

    def validate_and_process(self, data: List[Dict]) -> Dict:
        """Validate input and process data."""
        if not data:
            raise ValueError("Empty data provided")

        processed_count = 0
        errors = []

        for idx, item in enumerate(data):
            try:
                if self._validate_item(item):
                    result = self._process_item(item)
                    self.results.append(result)
                    processed_count += 1
            except Exception as e:
                errors.append({"index": idx, "error": str(e)})

        return {
            "processed": processed_count,
            "total": len(data),
            "errors": errors,
        }

    def _validate_item(self, item: Dict) -> bool:
        """Validate single item."""
        required_keys = ["id", "value", "type"]
        return all(key in item for key in required_keys)

    def _process_item(self, item: Dict) -> Dict:
        """Process single item."""
        return {
            "id": item["id"],
            "value": item["value"] * 2,
            "processed": True,
        }
'''


@pytest.fixture
def python_file_with_syntax_error():
    """Python file with syntax error."""
    return """
def broken_function():
    print("Missing closing quote)
    return True

class BrokenClass:
    def method(self)
        pass
"""
