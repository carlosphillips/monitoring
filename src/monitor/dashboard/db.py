"""DuckDB connector for consolidated breach/attribution data.

Initializes at app startup, loads parquet files into memory, and provides
thread-safe query execution with retry logic and error handling.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any, Optional

import duckdb

logger = logging.getLogger(__name__)


class DuckDBConnector:
    """Singleton connector for DuckDB queries on consolidated parquet data.

    Thread-safe with cursor-per-thread pattern. Initializes at app startup
    with consolidated parquet files loaded into memory tables.
    """

    _instance: Optional[DuckDBConnector] = None
    _lock = Lock()

    def __new__(cls) -> DuckDBConnector:
        """Singleton pattern: only one instance per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize DuckDB connector (only on first instantiation)."""
        if hasattr(self, "_initialized"):
            return

        self.conn = duckdb.connect(":memory:", read_only=False)
        self._initialized = True
        logger.info("DuckDB connector initialized (in-memory)")

    def load_consolidated_parquet(
        self,
        breaches_path: Path,
        attributions_path: Path,
    ) -> None:
        """Load consolidated parquet files into memory tables.

        Args:
            breaches_path: Path to all_breaches_consolidated.parquet
            attributions_path: Path to all_attributions_consolidated.parquet

        Raises:
            FileNotFoundError: If parquet files not found
            duckdb.IOException: If parquet files cannot be read
        """
        if not breaches_path.exists():
            raise FileNotFoundError(f"Breaches parquet not found: {breaches_path}")
        if not attributions_path.exists():
            raise FileNotFoundError(f"Attributions parquet not found: {attributions_path}")

        try:
            # Resolve paths to absolute paths (eliminates directory traversal risk)
            breaches_path_resolved = breaches_path.resolve()
            attributions_path_resolved = attributions_path.resolve()

            # Convert to POSIX string for SQL (safe after Path.resolve validation)
            breaches_path_str = breaches_path_resolved.as_posix()
            attributions_path_str = attributions_path_resolved.as_posix()

            # Load breaches
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS breaches AS
                SELECT * FROM read_parquet('{breaches_path_str}')
                """
            )
            breach_count = self.conn.execute("SELECT COUNT(*) FROM breaches").fetchall()[0][0]
            logger.info("Loaded breaches table: %d rows from %s", breach_count, breaches_path_str)

            # Load attributions
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS attributions AS
                SELECT * FROM read_parquet('{attributions_path_str}')
                """
            )
            attr_count = self.conn.execute("SELECT COUNT(*) FROM attributions").fetchall()[0][0]
            logger.info("Loaded attributions table: %d rows from %s", attr_count, attributions_path_str)

            # Create indexes for fast filtering
            self._create_indexes()

        except duckdb.IOException as e:
            logger.error("Failed to load parquet files: %s", e)
            raise

    def _create_indexes(self) -> None:
        """Create indexes on frequently-filtered columns."""
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_portfolio ON breaches(portfolio)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_date ON breaches(end_date)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_breach_layer ON breaches(layer)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_attr_portfolio ON attributions(portfolio)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_attr_date ON attributions(end_date)")
            logger.info("Created indexes on portfolio and date columns")
        except duckdb.Error as e:
            logger.warning("Failed to create indexes: %s (continuing without indexes)", e)

    def execute(
        self,
        sql: str,
        params: Optional[dict[str, Any]] = None,
        retry_count: int = 3,
        retry_delay_ms: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute parameterized SQL query with retry logic.

        Args:
            sql: SQL query with named parameters ($param_name)
            params: Dict of parameter values
            retry_count: Number of retry attempts (default 3)
            retry_delay_ms: Delay between retries in milliseconds

        Returns:
            List of result rows as dicts

        Raises:
            duckdb.Error: If query fails after all retries
        """
        if params is None:
            params = {}

        for attempt in range(retry_count):
            try:
                # Each callback gets a new cursor (thread-safe)
                cursor = self.conn.cursor()
                result = cursor.execute(sql, params).fetch_df()
                return result.to_dict("records") if len(result) > 0 else []

            except duckdb.Error as e:
                is_last_attempt = attempt == (retry_count - 1)

                if is_last_attempt:
                    logger.error("Query failed after %d retries: %s", retry_count, e)
                    raise
                else:
                    logger.warning("Query failed (attempt %d/%d), retrying in %dms: %s",
                                 attempt + 1, retry_count, retry_delay_ms, e)
                    time.sleep(retry_delay_ms / 1000.0)

    def query_breaches(
        self,
        sql: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Execute query on breaches table.

        Args:
            sql: SQL query (should reference 'breaches' table)
            params: Parameter dict

        Returns:
            List of result rows as dicts
        """
        return self.execute(sql, params)

    def query_attributions(
        self,
        sql: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Execute query on attributions table.

        Args:
            sql: SQL query (should reference 'attributions' table)
            params: Parameter dict

        Returns:
            List of result rows as dicts
        """
        return self.execute(sql, params)

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("DuckDB connection closed")

    def __del__(self) -> None:
        """Cleanup on garbage collection."""
        try:
            self.close()
        except Exception as e:
            logger.error("Error closing DuckDB connection: %s", e)


# Global instance for use in app and callbacks
db: DuckDBConnector | None = None


def init_db(breaches_path: Path, attributions_path: Path) -> DuckDBConnector:
    """Initialize global DuckDB connector at app startup.

    Args:
        breaches_path: Path to all_breaches_consolidated.parquet
        attributions_path: Path to all_attributions_consolidated.parquet

    Returns:
        The initialized DuckDBConnector instance
    """
    global db
    db = DuckDBConnector()
    db.load_consolidated_parquet(breaches_path, attributions_path)
    return db


def get_db() -> DuckDBConnector:
    """Get the global DuckDB connector instance.

    Returns:
        The DuckDBConnector instance

    Raises:
        RuntimeError: If init_db() has not been called
    """
    if db is None:
        raise RuntimeError("DuckDB not initialized. Call init_db() at app startup.")
    return db
