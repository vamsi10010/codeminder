import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import lancedb
import pyarrow as pa
from lancedb import DBConnection
from lancedb.table import Table

from ..utils.errors import DBUnavailableError
from ..utils.logger import get_logger
from .models import File, ParseStatus

logger = get_logger(__name__)


class VectorDB:
    def __init__(self, db_path: str = ".codeminder/vector_db", persist: bool = True):
        self.db_path = db_path
        self.persist = persist
        self._db: DBConnection | None = None
        self._table: Table | None = None
        self._table_name: str = "code_chunks"
        self._file_registry_table: Table | None = None
        self._reindex_lock = asyncio.Lock()

    def connect(self) -> None:
        try:
            if self.persist:
                db_path = Path(self.db_path)
                db_path.mkdir(parents=True, exist_ok=True)
                self._db = lancedb.connect(str(db_path))
            else:
                self._db = lancedb.connect(":memory:")

            logger.info(
                f"Connected to LanceDB at {self.db_path if self.persist else 'memory'}"
            )
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to connect to database: {str(e)}", {"db_path": self.db_path}
            ) from e

    def create_table(
        self, table_name: str = "code_chunks", schema: pa.Schema | None = None
    ) -> None:
        """Open existing table or prepare for creation on first insert.

        LanceDB cannot create tables from empty data, so we defer table creation
        until the first insert_chunks call.
        """
        if self._db is None:
            raise DBUnavailableError("Database not connected")

        self._table_name = table_name

        try:
            if table_name in self._db.table_names():
                self._table = self._db.open_table(table_name)
                logger.info(f"Opened existing table: {table_name}")
            else:
                # Table will be created on first insert
                logger.info(f"Table {table_name} will be created on first insert")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to open table: {str(e)}", {"table_name": table_name}
            ) from e

    def insert_chunks(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            logger.debug("No chunks to insert")
            return

        try:
            # Create table on first insert if it doesn't exist
            if self._table is None:
                if self._db is None:
                    raise DBUnavailableError("Database not connected")
                table_name = getattr(self, "_table_name", "code_chunks")
                self._table = self._db.create_table(table_name, chunks)
                logger.info(f"Created new table: {table_name}")
            else:
                self._table.add(chunks)

            logger.info(f"Inserted {len(chunks)} chunks into vector DB")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to insert chunks: {str(e)}", {"chunk_count": len(chunks)}
            ) from e

    async def atomic_reindex_file(
        self, file_id: UUID, new_chunks: list[dict[str, Any]]
    ) -> None:
        """Atomically delete old chunks and insert new chunks for a file.

        Args:
            file_id: UUID of the file being re-indexed.
            new_chunks: New chunks with embeddings to insert.
        """
        async with self._reindex_lock:
            try:
                self.delete_by_file_id(file_id)
                if new_chunks:
                    self.insert_chunks(new_chunks)
                logger.info(
                    f"Atomically re-indexed file {file_id}: "
                    f"inserted {len(new_chunks)} new chunks"
                )
            except Exception as e:
                raise DBUnavailableError(
                    f"Failed to atomically re-index file: {str(e)}",
                    {"file_id": str(file_id)},
                ) from e

    def search(
        self,
        query_vector: list[float],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for similar code chunks using vector similarity.

        Uses cosine similarity (default) for semantic code search.

        Args:
            query_vector: Embedding vector to search for.
            limit: Maximum number of results to return.

        Returns:
            List of chunk records with similarity scores and _distance field.
        """
        if self._table is None:
            raise DBUnavailableError("Table not initialized")

        try:
            results = (
                self._table.search(query_vector, vector_column_name="vector")
                .limit(limit)
                .to_list()
            )
            logger.info(f"Search returned {len(results)} results")
            return results
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to search: {str(e)}", {"limit": limit}
            ) from e

    def delete_by_file_id(self, file_id: UUID) -> None:
        if self._table is None:
            raise DBUnavailableError("Table not initialized")

        try:
            self._table.delete(f"file_id = '{str(file_id)}'")
            logger.info(f"Deleted chunks for file_id: {file_id}")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to delete chunks: {str(e)}", {"file_id": str(file_id)}
            ) from e

    def get_stats(self) -> dict[str, Any]:
        if self._table is None:
            raise DBUnavailableError("Table not initialized")

        try:
            count = self._table.count_rows()
            return {
                "total_chunks": count,
                "table_name": (
                    self._table.name if hasattr(self._table, "name") else "code_chunks"
                ),
            }
        except Exception as e:
            raise DBUnavailableError(f"Failed to get stats: {str(e)}") from e

    def create_file_registry_table(self) -> None:
        """Open or prepare file_registry table for persisting File metadata.

        This table enables:
        - Startup reconciliation by comparing persisted timestamps with filesystem
        - Efficient re-indexing by tracking last_indexed timestamps
        - Fast lookups by absolute_path during file watcher events
        - Crash recovery by resuming from last known state

        Table will be created on first upsert_file call if it doesn't exist.
        """
        if self._db is None:
            raise DBUnavailableError("Database not connected")

        try:
            table_name = "file_registry"
            if table_name in self._db.table_names():
                self._file_registry_table = self._db.open_table(table_name)
                logger.info("Opened existing file_registry table")
            else:
                # Table will be created on first upsert
                logger.info("File registry table will be created on first file insert")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to open file_registry table: {str(e)}"
            ) from e

    def load_file_registry(self) -> list[File]:
        """Load all File records from the file_registry table.

        Returns:
            List of File objects representing all indexed files.
        """
        # If table doesn't exist yet, return empty list
        if self._file_registry_table is None:
            logger.info("File registry table not yet created, returning empty list")
            return []

        try:
            records = self._file_registry_table.to_pandas().to_dict("records")
            files = []
            for record in records:
                files.append(
                    File(
                        file_id=UUID(record["file_id"]),
                        absolute_path=record["absolute_path"],
                        relative_path=record["relative_path"],
                        language=record["language"],
                        last_modified=datetime.fromisoformat(record["last_modified"]),
                        last_indexed=datetime.fromisoformat(record["last_indexed"]),
                        parse_status=ParseStatus(record["parse_status"]),
                        error_message=(
                            record["error_message"] if record["error_message"] else None
                        ),
                        chunk_count=record["chunk_count"],
                    )
                )
            logger.info(f"Loaded {len(files)} files from file registry")
            return files
        except Exception as e:
            raise DBUnavailableError(f"Failed to load file registry: {str(e)}") from e

    def upsert_file(self, file: File) -> None:
        """Insert or update a File record in the file_registry table.

        Args:
            file: File object to persist.
        """
        try:
            file_data = [
                {
                    "file_id": str(file.file_id),
                    "absolute_path": file.absolute_path,
                    "relative_path": file.relative_path,
                    "language": file.language,
                    "last_modified": file.last_modified.isoformat(),
                    "last_indexed": file.last_indexed.isoformat(),
                    "parse_status": file.parse_status.value,
                    "error_message": file.error_message if file.error_message else "",
                    "chunk_count": file.chunk_count,
                }
            ]

            # Create table on first insert if it doesn't exist
            if self._file_registry_table is None:
                if self._db is None:
                    raise DBUnavailableError("Database not connected")
                self._file_registry_table = self._db.create_table(
                    "file_registry", file_data
                )
                logger.info("Created new file_registry table")
            else:
                # Delete existing record if it exists
                self._file_registry_table.delete(f"file_id = '{str(file.file_id)}'")
                # Insert new record
                self._file_registry_table.add(file_data)

            logger.debug(f"Upserted file: {file.relative_path}")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to upsert file: {str(e)}", {"file_id": str(file.file_id)}
            ) from e

    def get_file_by_path(self, absolute_path: str) -> File | None:
        """Retrieve a File record by absolute_path.

        Args:
            absolute_path: Full filesystem path to look up.

        Returns:
            File object if found, None otherwise.
        """
        if not self._file_registry_table:
            raise DBUnavailableError("File registry table not initialized")

        try:
            # Query by absolute_path
            results = (
                self._file_registry_table.search()
                .where(f"absolute_path = '{absolute_path}'")
                .limit(1)
                .to_list()
            )

            if not results:
                return None

            record = results[0]
            return File(
                file_id=UUID(record["file_id"]),
                absolute_path=record["absolute_path"],
                relative_path=record["relative_path"],
                language=record["language"],
                last_modified=datetime.fromisoformat(record["last_modified"]),
                last_indexed=datetime.fromisoformat(record["last_indexed"]),
                parse_status=ParseStatus(record["parse_status"]),
                error_message=(
                    record["error_message"] if record["error_message"] else None
                ),
                chunk_count=record["chunk_count"],
            )
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to get file by path: {str(e)}",
                {"absolute_path": absolute_path},
            ) from e

    def delete_file(self, file_id: UUID) -> None:
        """Delete a File record from the file_registry table.

        Args:
            file_id: UUID of the file to delete.
        """
        if not self._file_registry_table:
            raise DBUnavailableError("File registry table not initialized")

        try:
            self._file_registry_table.delete(f"file_id = '{str(file_id)}'")
            logger.info(f"Deleted file record: {file_id}")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to delete file: {str(e)}", {"file_id": str(file_id)}
            ) from e

    def close(self) -> None:
        self._db = None
        self._table = None
        self._file_registry_table = None
        logger.info("Closed database connection")
