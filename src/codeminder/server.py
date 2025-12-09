"""CodeMinder Indexing Service - Core indexing logic."""

import asyncio
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .config import Configuration
from .embeddings.embedder import Embedder
from .parser.ast_parser import ASTParser
from .parser.chunker import create_chunker
from .parser.scanner import FileScanner
from .storage.models import File, ParseStatus
from .storage.vector_db import VectorDB
from .utils.errors import (
    IndexNotReadyError,
    ParseError,
)
from .utils.logger import get_logger

logger = get_logger(__name__)


class ReconciliationAction(str, Enum):
    """Actions to take during startup reconciliation."""

    INDEX = "INDEX"  # New file, needs indexing
    REINDEX = "REINDEX"  # Modified file, needs re-indexing
    DELETE = "DELETE"  # Removed file, delete from index


class IndexingError:
    """Represents an error encountered during file indexing."""

    def __init__(
        self,
        file_path: str,
        error_code: str,
        message: str,
        recovery: str | None = None,
    ):
        self.file_path = file_path
        self.error_code = error_code
        self.message = message
        self.recovery = recovery

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "file": self.file_path,
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.recovery:
            result["recovery"] = self.recovery
        return result


class IndexingService:
    """Service for indexing codebases and managing the vector database."""

    def __init__(self, config: Configuration):
        """Initialize the indexing service.

        Args:
            config: Configuration object with settings.
        """
        self.config = config
        self.scanner = FileScanner(config.codebase_path)
        self.chunker = create_chunker(
            strategy=config.chunking_strategy, token_limit=config.token_limit
        )
        self.embedder = Embedder(model_name=config.embedding_model)
        self.vector_db = VectorDB(persist=config.persist_index)
        self._semaphore: asyncio.Semaphore | None = None
        self._is_ready = False
        self._indexing_in_progress = False

    async def initialize(self) -> None:
        """Initialize all components and perform startup reconciliation.

        This method:
        1. Connects to vector database
        2. Loads embedding model
        3. Performs startup reconciliation (compares DB with filesystem)
        4. Re-indexes modified/new files
        """
        logger.info("Initializing IndexingService...")

        self._semaphore = asyncio.Semaphore(self.config.concurrency_limit)

        self.vector_db.connect()
        self.vector_db.create_table()
        self.vector_db.create_file_registry_table()

        self.embedder.load_model(token_limit=self.config.token_limit)

        await self._reconcile_index()

        self._is_ready = True
        logger.info("IndexingService initialized and ready")

    async def _reconcile_index(self) -> dict[str, Any]:
        """Reconcile persisted file registry with current filesystem state.

        Steps:
        1. Load file_registry from LanceDB
        2. Scan filesystem for current files
        3. Compare timestamps and paths
        4. Generate reconciliation actions (INDEX, REINDEX, DELETE)
        5. Process actions in parallel

        Returns:
            Summary dictionary with statistics about reconciliation actions.
        """
        logger.info("Starting index reconciliation...")
        start_time = time.time()

        # Load persisted file registry
        persisted_files = self.vector_db.load_file_registry()
        persisted_by_path = {f.absolute_path: f for f in persisted_files}
        logger.info(f"Loaded {len(persisted_files)} files from registry")

        # Scan filesystem
        discovered_paths = self.scanner.scan()
        discovered_path_set = {str(p) for p in discovered_paths}
        logger.info(f"Discovered {len(discovered_paths)} files in filesystem")

        if len(discovered_paths) == 0:
            logger.warning("No files found to index")
            return {
                "status": "success",
                "summary": {
                    "files_indexed": 0,
                    "chunks_created": 0,
                    "duration_seconds": 0.0,
                    "errors": [],
                },
            }

        # Generate reconciliation actions
        actions: list[tuple[ReconciliationAction, Path | File]] = []

        # Check for new and modified files
        for path in discovered_paths:
            path_str = str(path)
            if path_str not in persisted_by_path:
                # New file - needs indexing
                actions.append((ReconciliationAction.INDEX, path))
            else:
                # Existing file - check if modified
                persisted_file = persisted_by_path[path_str]
                current_mtime = datetime.fromtimestamp(path.stat().st_mtime)

                if current_mtime > persisted_file.last_indexed:
                    # File modified since last indexing
                    actions.append((ReconciliationAction.REINDEX, persisted_file))

        # Check for deleted files
        for path_str, file in persisted_by_path.items():
            if path_str not in discovered_path_set:
                # File no longer exists - delete from index
                actions.append((ReconciliationAction.DELETE, file))

        new_count = sum(1 for a, _ in actions if a == ReconciliationAction.INDEX)
        modified_count = sum(1 for a, _ in actions if a == ReconciliationAction.REINDEX)
        deleted_count = sum(1 for a, _ in actions if a == ReconciliationAction.DELETE)

        logger.info(
            f"Reconciliation actions: {new_count} new, {modified_count} modified, {deleted_count} deleted"
        )

        # Process reconciliation actions
        errors: list[IndexingError] = []
        files_indexed = 0
        total_chunks = 0
        files_failed = 0

        if actions:
            results = await self._process_reconciliation_actions(actions)

            # Aggregate results
            for result in results:
                if isinstance(result, Exception):
                    files_failed += 1
                    error_str = str(result)
                    file_path = "unknown"
                    if isinstance(result, ParseError) and "file" in result.details:
                        file_path = result.details["file"]

                    errors.append(
                        IndexingError(
                            file_path=file_path,
                            error_code="PARSE_ERROR",
                            message=error_str,
                            recovery="Fix syntax errors or exclude file from indexing",
                        )
                    )
                elif isinstance(result, File):
                    if result.parse_status == ParseStatus.SUCCESS:
                        files_indexed += 1
                        total_chunks += result.chunk_count
                    else:
                        files_failed += 1
                        errors.append(
                            IndexingError(
                                file_path=result.relative_path,
                                error_code=result.parse_status.value,
                                message=result.error_message or "Unknown error",
                                recovery="Check file syntax and format",
                            )
                        )
                elif result is None:
                    # DELETE actions return None
                    pass

        duration = time.time() - start_time
        logger.info(
            f"Reconciliation completed: {files_indexed} files indexed, "
            f"{total_chunks} chunks, {deleted_count} files deleted, "
            f"{files_failed} errors in {duration:.2f}s"
        )

        # Prepare response
        status = "success" if files_failed == 0 else "partial_success"
        summary = {
            "files_indexed": files_indexed,
            "chunks_created": total_chunks,
            "duration_seconds": round(duration, 2),
            "errors": [e.to_dict() for e in errors],
        }

        if files_failed > 0:
            summary["files_failed"] = files_failed

        return {
            "status": status,
            "summary": summary,
            "details": {
                "codebase_path": self.config.codebase_path,
                "languages": {"python": files_indexed},
            },
        }

    async def _process_reconciliation_actions(
        self, actions: list[tuple[ReconciliationAction, Path | File]]
    ) -> list[Any]:
        """Process reconciliation actions in parallel with periodic GPU cleanup.

        Args:
            actions: List of (action, file_or_path) tuples.

        Returns:
            List of results (File objects, None for deletes, or Exceptions).
        """
        tasks = []
        for action, target in actions:
            if action == ReconciliationAction.INDEX:
                # New file - index it
                tasks.append(self._index_file_async(target))  # type: ignore
            elif action == ReconciliationAction.REINDEX:
                # Modified file - re-index it
                tasks.append(self._reindex_file_async(target))  # type: ignore
            elif action == ReconciliationAction.DELETE:
                # Deleted file - remove from index
                tasks.append(self._delete_file_async(target))  # type: ignore

        # Execute all tasks in parallel (semaphore controls concurrency)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Reconciliation action failed: {result}")

        # Explicitly clear GPU cache after batch processing to prevent memory buildup
        # This is critical for large indexing operations that process many files
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.embedder.cleanup)

        return results

    async def _index_file_async(self, file_path: Path) -> File:
        """Index a single file asynchronously with semaphore control.

        Args:
            file_path: Path to file to index.

        Returns:
            File object with indexing results.
        """
        if not self._semaphore:
            raise RuntimeError("Semaphore not initialized")

        async with self._semaphore:
            # Run blocking I/O in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._index_file, file_path)

    def _index_file(self, file_path: Path) -> File:
        """Index a single file (blocking operation).

        Args:
            file_path: Path to file to index.

        Returns:
            File object with indexing results.
        """
        relative_path = self.scanner.get_relative_path(file_path)
        logger.debug(f"Indexing file: {relative_path}")

        file = File(
            absolute_path=str(file_path),
            relative_path=relative_path,
            language=self._detect_language(file_path),
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
            last_indexed=datetime.now(),
        )

        try:
            # Create embeddings and store in db
            chunks = self.chunker.chunk(file)

            if not chunks:
                logger.warning(f"No chunks extracted from {relative_path}")
                file.parse_status = ParseStatus.SKIPPED
                file.error_message = "No extractable code chunks"
                self.vector_db.upsert_file(file)
                return file

            chunk_dicts = [self._chunk_to_dict(chunk, file) for chunk in chunks]
            embeddings = self.embedder.encode_chunks(chunk_dicts)

            for chunk_dict, embedding in zip(chunk_dicts, embeddings, strict=True):
                chunk_dict["vector"] = embedding
                chunk_dict["model_version"] = self.embedder.model_name

            self.vector_db.insert_chunks(chunk_dicts)

            file.parse_status = ParseStatus.SUCCESS
            file.chunk_count = len(chunks)
            self.vector_db.upsert_file(file)

            logger.info(f"Successfully indexed {relative_path}: {len(chunks)} chunks")
            return file

        except Exception as e:
            logger.error(f"Failed to index {relative_path}: {e}")
            file.parse_status = ParseStatus.SYNTAX_ERROR
            file.error_message = str(e)
            self.vector_db.upsert_file(file)
            raise ParseError(
                f"Failed to parse {relative_path}",
                {"file": relative_path, "error": str(e)},
            ) from e

    async def _reindex_file_async(self, file: File) -> File:
        """Re-index a modified file asynchronously.

        Args:
            file: File object to re-index.

        Returns:
            Updated File object.
        """
        if not self._semaphore:
            raise RuntimeError("Semaphore not initialized")

        async with self._semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._reindex_file, file)

    def _reindex_file(self, file: File) -> File:
        """Re-index a modified file (blocking operation).

        Atomically deletes old chunks and inserts new ones.

        Args:
            file: File object to re-index.

        Returns:
            Updated File object.
        """
        logger.debug(f"Re-indexing file: {file.relative_path}")
        file_path = Path(file.absolute_path)

        file.last_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
        file.last_indexed = datetime.now()

        try:
            # Create new embeddings, remove old ones, and store in db
            chunks = self.chunker.chunk(file)

            chunk_dicts = []
            if chunks:
                chunk_dicts = [self._chunk_to_dict(chunk, file) for chunk in chunks]
                embeddings = self.embedder.encode_chunks(chunk_dicts)

                for chunk_dict, embedding in zip(chunk_dicts, embeddings, strict=True):
                    chunk_dict["vector"] = embedding
                    chunk_dict["model_version"] = self.embedder.model_name

            self.vector_db.delete_by_file_id(file.file_id)
            if chunk_dicts:
                self.vector_db.insert_chunks(chunk_dicts)

            file.parse_status = ParseStatus.SUCCESS
            file.chunk_count = len(chunks)
            self.vector_db.upsert_file(file)

            logger.info(
                f"Successfully re-indexed {file.relative_path}: {len(chunks)} chunks"
            )
            return file

        except Exception as e:
            logger.error(f"Failed to re-index {file.relative_path}: {e}")
            file.parse_status = ParseStatus.SYNTAX_ERROR
            file.error_message = str(e)
            self.vector_db.upsert_file(file)
            raise ParseError(
                f"Failed to re-parse {file.relative_path}",
                {"file": file.relative_path, "error": str(e)},
            ) from e

    async def _delete_file_async(self, file: File) -> None:
        """Delete a file from the index asynchronously.

        Args:
            file: File object to delete.
        """
        if not self._semaphore:
            raise RuntimeError("Semaphore not initialized")

        async with self._semaphore:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._delete_file, file)

    def _delete_file(self, file: File) -> None:
        """Delete a file from the index (blocking operation).

        Args:
            file: File object to delete.
        """
        logger.debug(f"Deleting file from index: {file.relative_path}")

        try:
            self.vector_db.delete_by_file_id(file.file_id)
            self.vector_db.delete_file(file.file_id)

            logger.info(f"Successfully deleted {file.relative_path} from index")

        except Exception as e:
            logger.error(f"Failed to delete {file.relative_path}: {e}")
            raise

    async def index_codebase(self) -> dict[str, Any]:
        """Index the entire codebase using reconciliation.

        This is the main entry point for indexing. It uses the reconciliation
        logic to intelligently handle new, modified, and deleted files instead
        of blindly re-indexing everything.

        Returns:
            Summary of indexing results with counts and errors.
        """
        if self._indexing_in_progress:
            raise IndexNotReadyError("Indexing already in progress")

        self._indexing_in_progress = True
        logger.info("Starting codebase indexing via reconciliation...")

        try:
            result = await self._reconcile_index()
            return result

        finally:
            self._indexing_in_progress = False
            # Final GPU cleanup after indexing completes
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.embedder.cleanup)
            logger.info("GPU memory cleaned up after indexing")

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension.

        Args:
            file_path: Path to file.

        Returns:
            Language name (e.g., "python").
        """
        return ASTParser.detect_language(file_path)

    def _chunk_to_dict(self, chunk: Any, file: File) -> dict[str, Any]:
        """Convert CodeChunk to dictionary for storage.

        Args:
            chunk: CodeChunk object.
            file: File object the chunk belongs to.

        Returns:
            Dictionary representation for LanceDB.
        """
        return {
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
            "sequence_number": 0,  # TODO: Implement sequence numbering for split nodes
            "language": file.language,
            "created_at": chunk.created_at.isoformat(),
        }

    def is_ready(self) -> bool:
        """Check if the indexing service is ready to serve requests.

        Returns:
            True if ready, False otherwise.
        """
        return self._is_ready

    def get_status(self) -> dict[str, Any]:
        """Get current indexing service status.

        Returns:
            Status information including file counts and readiness.
        """
        if not self._is_ready:
            return {
                "ready": False,
                "message": "Service not initialized",
            }

        try:
            # Get database stats
            db_stats = self.vector_db.get_stats()

            # Count files in registry
            files = self.vector_db.load_file_registry()
            file_count = len(files)

            return {
                "ready": True,
                "indexing_in_progress": self._indexing_in_progress,
                "file_count": file_count,
                "chunk_count": db_stats.get("total_chunks", 0),
                "codebase_path": self.config.codebase_path,
            }

        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {
                "ready": self._is_ready,
                "indexing_in_progress": self._indexing_in_progress,
                "error": str(e),
            }

    async def cleanup(self) -> None:
        """Clean up resources and release GPU memory.

        Should be called during graceful shutdown to free GPU resources.
        """
        logger.info("Cleaning up IndexingService resources...")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.embedder.cleanup)
        logger.info("IndexingService cleanup complete")
