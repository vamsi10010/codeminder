"""One-shot indexer for CodeMinder.

Run this ahead of Codex/Gemini so the codebase is pre-indexed and persisted.
"""

import asyncio
import json
import sys
from pathlib import Path

# Ensure repo root/src is on sys.path when running as a script
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from codeminder.config import Configuration
from codeminder.server import IndexingService


async def main() -> None:
    config = Configuration(max_search_results=10)

    # Force persistence so the index can be reused by external callers.
    config.persist_index = True

    service = IndexingService(config)
    await service.initialize()
    summary = await service.index_codebase()

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
