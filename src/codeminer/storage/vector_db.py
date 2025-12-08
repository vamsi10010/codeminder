from pathlib import Path
from typing import Optional, List, Dict, Any
import lancedb
from lancedb import DBConnection
from lancedb.table import Table
import pyarrow as pa
from uuid import UUID

from ..utils.errors import DBUnavailableError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VectorDB:
    def __init__(self, db_path: str = ".codeminder/vector_db", persist: bool = True):
        self.db_path = db_path
        self.persist = persist
        self._db: Optional[DBConnection] = None
        self._table: Optional[Table] = None

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
            )

    def create_table(
        self, table_name: str = "code_chunks", schema: Optional[pa.Schema] = None
    ) -> None:
        if not self._db:
            raise DBUnavailableError("Database not connected")

        if schema is None:
            schema = pa.schema(
                [
                    pa.field("chunk_id", pa.string()),
                    pa.field("file_id", pa.string()),
                    pa.field("file_path", pa.string()),
                    pa.field("relative_path", pa.string()),
                    pa.field("source_code", pa.string()),
                    pa.field("context_path", pa.string()),
                    pa.field("start_line", pa.int32()),
                    pa.field("end_line", pa.int32()),
                    pa.field("token_count", pa.int32()),
                    pa.field("node_type", pa.string()),
                    pa.field("sequence_number", pa.int32()),
                    pa.field("language", pa.string()),
                    pa.field("vector", pa.list_(pa.float32())),
                    pa.field("model_version", pa.string()),
                    pa.field("created_at", pa.string()),
                ]
            )

        try:
            if table_name in self._db.table_names():
                self._table = self._db.open_table(table_name)
                logger.info(f"Opened existing table: {table_name}")
            else:
                empty_data = pa.Table.from_pylist([], schema=schema)
                self._table = self._db.create_table(table_name, empty_data)
                logger.info(f"Created new table: {table_name}")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to create/open table: {str(e)}", {"table_name": table_name}
            )

    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        if not self._table:
            raise DBUnavailableError("Table not initialized")

        try:
            self._table.add(chunks)
            logger.info(f"Inserted {len(chunks)} chunks into vector DB")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to insert chunks: {str(e)}", {"chunk_count": len(chunks)}
            )

    def search(
        self, query_vector: List[float], limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self._table:
            raise DBUnavailableError("Table not initialized")

        try:
            results = self._table.search(query_vector).limit(limit).to_list()
            logger.info(f"Search returned {len(results)} results")
            return results
        except Exception as e:
            raise DBUnavailableError(f"Failed to search: {str(e)}", {"limit": limit})

    def delete_by_file_id(self, file_id: UUID) -> None:
        if not self._table:
            raise DBUnavailableError("Table not initialized")

        try:
            self._table.delete(f"file_id = '{str(file_id)}'")
            logger.info(f"Deleted chunks for file_id: {file_id}")
        except Exception as e:
            raise DBUnavailableError(
                f"Failed to delete chunks: {str(e)}", {"file_id": str(file_id)}
            )

    def get_stats(self) -> Dict[str, Any]:
        if not self._table:
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
            raise DBUnavailableError(f"Failed to get stats: {str(e)}")

    def close(self) -> None:
        self._db = None
        self._table = None
        logger.info("Closed database connection")
