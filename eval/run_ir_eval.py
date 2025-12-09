"""Simple IR evaluation for CodeMinder search.

Runs an index over a codebase, executes a golden set of queries,
and reports IR metrics (success rate, precision@k, MRR).
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from codeminder.config import Configuration
from codeminder.search.searcher import Searcher
from codeminder.server import IndexingService


def load_golden(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Golden queries must be a list")
    return data


def success_at_k(results: list[dict[str, Any]], relevant_paths: set[str], k: int) -> bool:
    for result in results[:k]:
        rel_path = result["file"]["relative_path"]
        if any(rel_path.endswith(target) for target in relevant_paths):
            return True
    return False


def mrr(results: list[dict[str, Any]], relevant_paths: set[str]) -> float:
    for idx, result in enumerate(results, start=1):
        rel_path = result["file"]["relative_path"]
        if any(rel_path.endswith(target) for target in relevant_paths):
            return 1.0 / idx
    return 0.0


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run IR eval against CodeMinder searcher")
    parser.add_argument(
        "--codebase",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "sample_project",
        help="Path to codebase to index",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path(__file__).parent / "golden_queries.json",
        help="Path to golden queries JSON",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformers model name",
    )
    parser.add_argument("--max-results", type=int, default=5, help="Top-k to return")
    parser.add_argument("--token-limit", type=int, default=512, help="Max tokens per chunk")
    args = parser.parse_args()

    golden = load_golden(args.golden)

    config = Configuration(
        codebase_path=str(args.codebase),
        embedding_model=args.embedding_model,
        token_limit=args.token_limit,
        max_search_results=args.max_results,
        persist_index=False,
    )

    service = IndexingService(config)
    await service.initialize()
    await service.index_codebase()

    searcher = Searcher(service.vector_db, service.embedder)

    total = len(golden)
    hits_at_1 = hits_at_5 = 0
    mrr_sum = 0.0
    per_query: list[dict[str, Any]] = []

    for item in golden:
        query = item["query"]
        relevant = set(item.get("relevant_paths", []))
        start = time.time()
        result = searcher.search(query, limit=args.max_results)
        duration_ms = int((time.time() - start) * 1000)
        results = result["results"]
        per_query.append(
            {
                "query": query,
                "relevant_paths": sorted(relevant),
                "results_returned": len(results),
                "hit_at_1": success_at_k(results, relevant, 1),
                "hit_at_k": success_at_k(results, relevant, args.max_results),
                "mrr": mrr(results, relevant),
                "duration_ms": duration_ms,
            }
        )
        hits_at_1 += int(success_at_k(results, relevant, 1))
        hits_at_5 += int(success_at_k(results, relevant, args.max_results))
        mrr_sum += mrr(results, relevant)

    summary = {
        "total_queries": total,
        "success_rate_at_1": hits_at_1 / total if total else 0.0,
        "success_rate_at_k": hits_at_5 / total if total else 0.0,
        "mean_mrr": mrr_sum / total if total else 0.0,
    }

    report = {"summary": summary, "queries": per_query}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
