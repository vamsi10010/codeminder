"""FastMCP Server for CodeMinder - MCP tool implementations."""

from typing import Any

from fastmcp import FastMCP

from .config import Configuration
from .search.searcher import Searcher
from .server import IndexingService
from .utils.errors import IndexNotReadyError
from .utils.logger import get_logger

logger = get_logger(__name__)

mcp = FastMCP("CodeMinder")

# Global service instances (initialized on startup)
_indexing_service: IndexingService | None = None
_searcher: Searcher | None = None


async def initialize_server() -> None:
    """Initialize the MCP server and all components."""
    global _indexing_service, _searcher

    logger.info("Starting CodeMinder MCP server initialization...")

    config = Configuration.load_from_file()

    _indexing_service = IndexingService(config)
    await _indexing_service.initialize()

    _searcher = Searcher(
        vector_db=_indexing_service.vector_db, embedder=_indexing_service.embedder
    )

    logger.info("CodeMinder MCP server initialized successfully")


@mcp.tool()
async def index_codebase() -> dict[str, Any]:
    """Trigger indexing of the configured codebase.

    Scans the codebase directory, parses code files, generates embeddings,
    and stores chunks in the vector database. On subsequent runs, performs
    startup reconciliation to re-index only modified files.

    Returns:
        Dictionary with indexing summary including file counts, chunk counts,
        duration, and any errors encountered.

    Raises:
        Exception: If indexing service not initialized or indexing fails.
    """
    if not _indexing_service:
        raise Exception("Indexing service not initialized. Server startup failed.")

    try:
        result = await _indexing_service.index_codebase()
        return result
    except Exception as e:
        logger.error(f"index_codebase failed: {e}")
        return {
            "error": {
                "code": "INDEX_ERROR",
                "message": str(e),
                "recovery": "Check logs for details and retry",
            }
        }


@mcp.tool()
async def search_code(query: str, limit: int = 10) -> dict[str, Any]:
    """Search the indexed codebase for code snippets matching a query.

    Performs semantic search using natural language queries to find relevant
    code chunks. Returns ranked results with similarity scores and full code context.

    Args:
        query: Natural language description of desired code (e.g., "JWT authentication")
        limit: Maximum number of results to return (1-100, default 20)

    Returns:
        Dictionary with search results including ranked code chunks, file paths,
        context paths, and metadata about the search.

    Raises:
        Exception: If search service not initialized or search fails.
    """
    if not _searcher:
        raise Exception("Search service not initialized. Server startup failed.")

    if not query or not query.strip():
        return {
            "error": {
                "code": "INVALID_QUERY",
                "message": "Query cannot be empty",
                "recovery": "Provide a non-empty query string",
            }
        }

    try:
        result = _searcher.search(query, limit=limit)

        # Add suggestion if no results found
        if result["status"] == "success" and len(result["results"]) == 0:
            result["suggestion"] = (
                "No matching code found. Try broader keywords or ensure codebase is indexed."
            )

        return result

    except IndexNotReadyError as e:
        return {
            "error": {
                "code": "INDEX_NOT_READY",
                "message": str(e),
                "context": e.details,
                "recovery": "Run index_codebase tool first",
            }
        }
    except Exception as e:
        logger.error(f"search_code failed: {e}")
        return {
            "error": {
                "code": "SEARCH_ERROR",
                "message": str(e),
                "recovery": "Check query format and try again",
            }
        }


@mcp.tool()
async def get_index_status() -> dict[str, Any]:
    """Get current indexing status and statistics.

    Returns diagnostic information about the indexed codebase including
    file counts, chunk counts, registry status, and reconciliation details.

    Returns:
        Dictionary with comprehensive status information including:
        - Overall status (ready/not ready)
        - File and chunk statistics
        - Registry persistence info
        - Reconciliation history
        - Configuration details

    Raises:
        Exception: If indexing service not initialized.
    """
    if not _indexing_service:
        return {
            "status": "not_ready",
            "message": "Indexing service not initialized. Server startup failed.",
        }

    try:
        basic_status = _indexing_service.get_status()

        if not basic_status.get("ready"):
            return {
                "status": "not_ready",
                "message": basic_status.get("message", "Service not ready"),
            }

        # Get detailed stats
        db_stats = _indexing_service.vector_db.get_stats()
        files = _indexing_service.vector_db.load_file_registry()

        # Calculate index size (approximate)
        index_size_mb = db_stats.get("index_size_mb", 0.0)

        # Get last indexed timestamp from most recent file
        last_indexed = None
        if files:
            most_recent = max(files, key=lambda f: f.last_indexed)
            last_indexed = most_recent.last_indexed.isoformat()

        return {
            "status": "ready",
            "statistics": {
                "files_indexed": basic_status.get("file_count", 0),
                "total_chunks": basic_status.get("chunk_count", 0),
                "total_lines_of_code": db_stats.get("total_lines", 0),
                "index_size_mb": round(index_size_mb, 1),
                "last_indexed": last_indexed,
            },
            "registry": {
                "persisted": True,
                "files_in_registry": len(files),
                "registry_table_size_mb": db_stats.get("registry_size_mb", 0.0),
            },
            "configuration": {
                "codebase_path": _indexing_service.config.codebase_path,
                "token_limit": _indexing_service.config.token_limit,
                "concurrency_limit": _indexing_service.config.concurrency_limit,
            },
        }

    except Exception as e:
        logger.error(f"get_index_status failed: {e}")
        return {"status": "error", "message": str(e)}


def main() -> None:
    """Main entry point for the MCP server."""
    import asyncio

    asyncio.run(initialize_server())
    mcp.run()


if __name__ == "__main__":
    main()
