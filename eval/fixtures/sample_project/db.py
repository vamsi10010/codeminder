from dataclasses import dataclass
import sqlite3


@dataclass
class DatabaseConfig:
    path: str


def connect_db(config: DatabaseConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(config.path)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn
