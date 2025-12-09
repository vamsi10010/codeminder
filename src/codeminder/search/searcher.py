import time
from typing import Any

from ..embeddings.embedder import Embedder
from ..storage.vector_db import VectorDB
from ..utils.errors import IndexNotReadyError, SearchError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SearchResult:
    def __init__(
        self,
        rank: int,
        similarity_score: float,
        file_path: str,
        relative_path: str,
        context_path: str,
        code: str,
        start_line: int,
        end_line: int,
        token_count: int,
    ):
        self.rank = rank
        self.similarity_score = similarity_score
        self.file_path = file_path
        self.relative_path = relative_path
        self.context_path = context_path
        self.code = code
        self.start_line = start_line
        self.end_line = end_line
        self.token_count = token_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "similarity_score": self.similarity_score,
            "file": {
                "path": self.file_path,
                "relative_path": self.relative_path,
            },
            "chunk": {
                "context_path": self.context_path,
                "code": self.code,
                "start_line": self.start_line,
                "end_line": self.end_line,
                "token_count": self.token_count,
            },
        }


class Searcher:
    def __init__(self, vector_db: VectorDB, embedder: Embedder):
        self.vector_db = vector_db
        self.embedder = embedder

    def search(
        self,
        query: str,
        limit: int = 20,
        similarity_threshold: float = 0.0,
    ) -> dict[str, Any]:
        """Search for code chunks matching the query.

        Args:
            query: Natural language search query.
            limit: Maximum number of results to return.
            similarity_threshold: Minimum similarity score to include (0-1).

        Returns:
            Dictionary containing search results and metadata, formatted per MCP contract.
        """
        if limit < 1 or limit > 100:
            raise SearchError("Limit must be between 1 and 100", {"limit": limit})

        start_time = time.time()

        try:
            stats = self.vector_db.get_stats()
            total_chunks = stats.get("total_chunks", 0)

            if total_chunks == 0:
                raise IndexNotReadyError(
                    "Codebase has not been indexed yet", {"indexed_files": 0}
                )

            logger.info(f"Searching for: {query[:100]}...")

            query_vector = self.embedder.encode_single(query)

            raw_results = self.vector_db.search(query_vector, limit=limit)

            results = self._format_and_rank_results(
                raw_results, similarity_threshold=similarity_threshold
            )

            search_duration_ms = int((time.time() - start_time) * 1000)

            return {
                "status": "success",
                "query": query,
                "results": [r.to_dict() for r in results],
                "metadata": {
                    "total_chunks_searched": total_chunks,
                    "search_duration_ms": search_duration_ms,
                    "results_returned": len(results),
                },
            }

        except IndexNotReadyError:
            raise
        except Exception as e:
            raise SearchError(
                f"Search failed: {str(e)}",
                {"query": query[:100], "limit": limit},
            ) from e

    def _format_and_rank_results(
        self, raw_results: list[dict[str, Any]], similarity_threshold: float = 0.0
    ) -> list[SearchResult]:
        """Format raw database results and apply ranking/filtering.

        Args:
            raw_results: Raw results from vector DB with _distance field.
            similarity_threshold: Minimum similarity score to include.

        Returns:
            List of formatted SearchResult objects, ranked by similarity.
        """
        results = []
        for idx, result in enumerate(raw_results):
            distance = result.get("_distance", 0.0)
            similarity_score = self._distance_to_similarity(distance)

            if similarity_score < similarity_threshold:
                continue

            search_result = SearchResult(
                rank=idx + 1,
                similarity_score=round(similarity_score, 4),
                file_path=result.get("file_path", ""),
                relative_path=result.get("relative_path", ""),
                context_path=result.get("context_path", ""),
                code=result.get("source_code", ""),
                start_line=result.get("start_line", 0),
                end_line=result.get("end_line", 0),
                token_count=result.get("token_count", 0),
            )
            results.append(search_result)

        return results

    def _distance_to_similarity(self, distance: float) -> float:
        """Convert distance metric to similarity score (0-1).

        LanceDB returns L2 distance by default. For cosine similarity:
        similarity = 1 - (distance / 2)

        Args:
            distance: Distance from vector search (typically L2 or cosine distance).

        Returns:
            Similarity score between 0 and 1 (higher is better).
        """
        if distance < 0:
            distance = 0
        similarity = 1.0 - (distance / 2.0)
        return max(0.0, min(1.0, similarity))
