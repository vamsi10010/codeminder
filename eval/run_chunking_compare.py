"""Compare AST chunking vs line-based chunking on retrieval quality."""

import argparse
import asyncio
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from codeminder.config import Configuration
from codeminder.embeddings.embedder import Embedder
from codeminder.parser.chunker import Chunker
from codeminder.parser.scanner import FileScanner
from codeminder.parser.token_counter import count_tokens
from codeminder.search.searcher import Searcher
from codeminder.storage.models import CodeChunk, File, ParseStatus
from codeminder.storage.vector_db import VectorDB
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


@dataclass
class EvalResult:
    success_at_1: float
    success_at_k: float
    mean_mrr: float
    chunk_stats: dict[str, Any]


def evaluate(searcher: Searcher, golden: list[dict[str, Any]], k: int) -> EvalResult:
    total = len(golden)
    hits_at_1 = hits_at_k = 0
    mrr_sum = 0.0
    for item in golden:
        query = item["query"]
        relevant = set(item.get("relevant_paths", []))
        results = searcher.search(query, limit=k)["results"]
        hits_at_1 += int(success_at_k(results, relevant, 1))
        hits_at_k += int(success_at_k(results, relevant, k))
        mrr_sum += mrr(results, relevant)

    return EvalResult(
        success_at_1=hits_at_1 / total if total else 0.0,
        success_at_k=hits_at_k / total if total else 0.0,
        mean_mrr=mrr_sum / total if total else 0.0,
        chunk_stats={},  # filled by caller
    )


def line_chunks_for_file(
    file: File, max_lines: int, token_limit: int
) -> list[CodeChunk]:
    """Create simple line-based chunks capped by max_lines and token_limit."""
    chunks: list[CodeChunk] = []
    text = Path(file.absolute_path).read_text().splitlines()
    start = 0
    while start < len(text):
        end = min(len(text), start + max_lines)
        window = "\n".join(text[start:end])
        # If token limit exceeded, halve window until under limit (coarse but safe)
        while count_tokens(window) > token_limit and end - start > 1:
            end = start + math.ceil((end - start) / 2)
            window = "\n".join(text[start:end])

        chunk = CodeChunk(
            file_id=file.file_id,
            source_code=window,
            context_path=f"{file.relative_path}:{start + 1}-{end}",
            start_line=start + 1,
            end_line=end,
            token_count=count_tokens(window),
            node_type="line_chunk",
        )
        chunks.append(chunk)
        start = end
    return chunks


def build_line_index(
    codebase: Path,
    embedder: Embedder,
    line_span: int,
    token_limit: int,
) -> tuple[VectorDB, dict[str, Any]]:
    scanner = FileScanner(str(codebase))
    vector_db = VectorDB(persist=False)
    vector_db.connect()
    vector_db.create_table()
    vector_db.create_file_registry_table()

    chunk_counts: list[int] = []

    for file_path in scanner.scan():
        relative_path = scanner.get_relative_path(file_path)
        file = File(
            file_id=uuid4(),
            absolute_path=str(file_path),
            relative_path=relative_path,
            language="python",
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
            last_indexed=datetime.now(),
            parse_status=ParseStatus.SUCCESS,
        )

        chunks = line_chunks_for_file(file, max_lines=line_span, token_limit=token_limit)
        chunk_counts.append(len(chunks))
        chunk_dicts: list[dict[str, Any]] = []
        for chunk in chunks:
            chunk_dicts.append(
                {
                    "chunk_id": str(chunk.chunk_id),
                    "file_id": str(chunk.file_id),
                    "file_path": file.absolute_path,
                    "relative_path": file.relative_path,
                    "source_code": chunk.source_code,
                    "context_path": chunk.context_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "token_count": chunk.token_count,
                    "node_type": chunk.node_type,
                    "sequence_number": 0,
                    "language": file.language,
                    "created_at": chunk.created_at.isoformat(),
                }
            )

        if chunk_dicts:
            embeddings = embedder.encode_chunks(chunk_dicts)
            for chunk_dict, embedding in zip(chunk_dicts, embeddings, strict=True):
                chunk_dict["vector"] = embedding
                chunk_dict["model_version"] = embedder.model_name
            vector_db.insert_chunks(chunk_dicts)

        file.chunk_count = len(chunks)
        vector_db.upsert_file(file)

    chunk_stats = {
        "files_indexed": len(chunk_counts),
        "chunks_total": sum(chunk_counts),
        "chunks_per_file_avg": sum(chunk_counts) / len(chunk_counts) if chunk_counts else 0.0,
    }
    return vector_db, chunk_stats


async def build_ast_index(config: Configuration) -> tuple[VectorDB, Embedder, dict[str, Any]]:
    service = IndexingService(config)
    await service.initialize()
    await service.index_codebase()
    files = service.vector_db.load_file_registry()
    chunk_stats = {
        "files_indexed": len(files),
        "chunks_total": sum(f.chunk_count for f in files),
        "chunks_per_file_avg": (
            sum(f.chunk_count for f in files) / len(files) if files else 0.0
        ),
    }
    return service.vector_db, service.embedder, chunk_stats


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare AST vs line chunking for retrieval quality"
    )
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
    parser.add_argument("--max-results", type=int, default=5, help="Top-k for evaluation")
    parser.add_argument("--token-limit", type=int, default=512, help="Token limit per chunk")
    parser.add_argument("--line-span", type=int, default=40, help="Max lines per line chunk")
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformers model name",
    )
    args = parser.parse_args()

    golden = load_golden(args.golden)

    ast_config = Configuration(
        codebase_path=str(args.codebase),
        embedding_model=args.embedding_model,
        token_limit=args.token_limit,
        max_search_results=args.max_results,
        persist_index=False,
    )

    ast_db, embedder, ast_chunk_stats = await build_ast_index(ast_config)
    ast_searcher = Searcher(ast_db, embedder)
    ast_eval = evaluate(ast_searcher, golden, args.max_results)
    ast_eval.chunk_stats = ast_chunk_stats

    line_db, line_chunk_stats = build_line_index(
        args.codebase, embedder, args.line_span, args.token_limit
    )
    line_searcher = Searcher(line_db, embedder)
    line_eval = evaluate(line_searcher, golden, args.max_results)
    line_eval.chunk_stats = line_chunk_stats

    report = {
        "ast": {
            "success_at_1": ast_eval.success_at_1,
            "success_at_k": ast_eval.success_at_k,
            "mean_mrr": ast_eval.mean_mrr,
            "chunk_stats": ast_eval.chunk_stats,
        },
        "line": {
            "success_at_1": line_eval.success_at_1,
            "success_at_k": line_eval.success_at_k,
            "mean_mrr": line_eval.mean_mrr,
            "chunk_stats": line_eval.chunk_stats,
        },
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
