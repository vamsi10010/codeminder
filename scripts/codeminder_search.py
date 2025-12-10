"""Lightweight search entrypoint for CodeMinder.

Use this script as the target for MCP tool calls. It assumes the codebase has
already been indexed and persisted (see scripts/codeminder_index.py).
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root/src is on sys.path when running as a script
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from codeminder.config import Configuration
from codeminder.embeddings.embedder import Embedder
from codeminder.search.searcher import Searcher
from codeminder.storage.vector_db import VectorDB


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a CodeMinder search against an existing index")
    parser.add_argument("--query", required=True, help="Natural language search query")
    parser.add_argument("--limit", type=int, default=5, help="Maximum results to return")
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.0,
        help="Minimum similarity score (0-1) to include",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(".codeminder.json"),
        help="Path to CodeMinder config file",
    )
    args = parser.parse_args()

    config = Configuration.load_from_file(str(args.config))
    # Ensure we look for a persisted DB.
    config.persist_index = True

    vector_db = VectorDB(persist=config.persist_index)
    vector_db.connect()
    vector_db.create_table()
    vector_db.create_file_registry_table()

    embedder = Embedder(model_name=config.embedding_model)
    embedder.load_model()

    searcher = Searcher(vector_db, embedder)
    result = searcher.search(
        args.query,
        limit=args.limit,
        similarity_threshold=args.similarity_threshold,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
