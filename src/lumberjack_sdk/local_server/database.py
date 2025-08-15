"""
Database management for Lumberjack Local Server.

Handles SQLite operations for storing and retrieving logs from multiple services.
"""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Generator
from pathlib import Path

from ..internal_utils.fallback_logger import fallback_logger


@dataclass
class LogEntry:
    """Represents a log entry in the database."""
    id: str = ""  # Changed to UUID string
    timestamp: int = 0
    level: str = ""
    message: str = ""
    service: str = ""
    attributes: Dict[str, Any] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.attributes is None:
            self.attributes = {}
        # Generate UUID if not provided
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'level': self.level,
            'message': self.message,
            'service': self.service,
            'attributes': self.attributes,
            'trace_id': self.trace_id,
            'span_id': self.span_id,
        }


class LogDatabase:
    """
    SQLite database manager for storing logs from multiple services.
    
    Supports both in-memory and persistent storage with thread-safe operations.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database.
        
        Args:
            db_path: Path to SQLite database file. If None, uses in-memory database.
        """
        self.db_path = db_path or ":memory:"
        self._lock = threading.RLock()
        self._connection: Optional[sqlite3.Connection] = None
        self._initialize_db()
    
    def _initialize_db(self) -> None:
        """Initialize database schema."""
        try:
            with self._get_connection() as conn:
                # Check if we need to migrate from old schema
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
                table_exists = cursor.fetchone() is not None
                
                if table_exists:
                    # Check if id column is still INTEGER
                    cursor = conn.execute("PRAGMA table_info(logs)")
                    columns = {row[1]: row[2] for row in cursor.fetchall()}
                    if columns.get('id') == 'INTEGER':
                        # Need to migrate - drop and recreate table
                        fallback_logger.info("Migrating database schema to use UUID for id field")
                        conn.execute("DROP TABLE logs")
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id TEXT PRIMARY KEY,
                        timestamp INTEGER NOT NULL,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        service TEXT NOT NULL,
                        attributes TEXT,
                        trace_id TEXT,
                        span_id TEXT
                    )
                """)
                
                # Create indexes for efficient queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON logs(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_level 
                    ON logs(level)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_service 
                    ON logs(service)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_service_timestamp 
                    ON logs(service, timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_trace_id 
                    ON logs(trace_id)
                """)
                
                conn.commit()
                fallback_logger.debug(f"Initialized log database at {self.db_path}")
        except Exception as e:
            fallback_logger.error(f"Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a thread-safe database connection."""
        with self._lock:
            if self._connection is None:
                self._connection = sqlite3.connect(
                    self.db_path, 
                    check_same_thread=False,
                    timeout=30.0
                )
                self._connection.row_factory = sqlite3.Row
            yield self._connection
    
    def insert_log(self, log_entry: LogEntry) -> str:
        """
        Insert a log entry into the database.
        
        Args:
            log_entry: The log entry to insert
            
        Returns:
            The UUID of the inserted log entry
        """
        try:
            # Ensure the log entry has a UUID
            if not log_entry.id:
                log_entry.id = str(uuid.uuid4())
            
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO logs (
                        id, timestamp, level, message, service, 
                        attributes, trace_id, span_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_entry.id,
                    log_entry.timestamp,
                    log_entry.level,
                    log_entry.message,
                    log_entry.service,
                    json.dumps(log_entry.attributes) if log_entry.attributes else None,
                    log_entry.trace_id,
                    log_entry.span_id,
                ))
                conn.commit()
                return log_entry.id
        except Exception as e:
            fallback_logger.error(f"Failed to insert log: {e}")
            raise
    
    def get_logs(
        self, 
        limit: int = 100, 
        offset: int = 0,
        service: Optional[str] = None,
        level: Optional[str] = None,
        search_query: Optional[str] = None,
        since_timestamp: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Retrieve logs with optional filtering.
        
        Args:
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            service: Filter by service name
            level: Filter by log level
            search_query: Search in message content
            since_timestamp: Get logs after this timestamp
            
        Returns:
            List of log entries
        """
        try:
            with self._get_connection() as conn:
                conditions = []
                params = []
                
                if service:
                    conditions.append("service = ?")
                    params.append(service)
                
                if level:
                    conditions.append("level = ?")
                    params.append(level)
                
                if search_query:
                    conditions.append("message LIKE ?")
                    params.append(f"%{search_query}%")
                
                if since_timestamp:
                    conditions.append("timestamp > ?")
                    params.append(since_timestamp)
                
                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)
                
                query = f"""
                    SELECT * FROM logs 
                    {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_log_entry(row) for row in rows]
        except Exception as e:
            fallback_logger.error(f"Failed to get logs: {e}")
            raise
    
    def get_recent_logs(self, limit: int = 50) -> List[LogEntry]:
        """Get the most recent logs."""
        return self.get_logs(limit=limit, offset=0)
    
    def get_services(self) -> List[str]:
        """Get list of all services that have sent logs."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT DISTINCT service 
                    FROM logs 
                    ORDER BY service
                """)
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            fallback_logger.error(f"Failed to get services: {e}")
            return []
    
    def get_log_count(
        self, 
        service: Optional[str] = None,
        level: Optional[str] = None,
        since_timestamp: Optional[int] = None
    ) -> int:
        """Get count of logs with optional filtering."""
        try:
            with self._get_connection() as conn:
                conditions = []
                params = []
                
                if service:
                    conditions.append("service = ?")
                    params.append(service)
                
                if level:
                    conditions.append("level = ?")
                    params.append(level)
                
                if since_timestamp:
                    conditions.append("timestamp > ?")
                    params.append(since_timestamp)
                
                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)
                
                query = f"SELECT COUNT(*) FROM logs {where_clause}"
                cursor = conn.execute(query, params)
                return cursor.fetchone()[0]
        except Exception as e:
            fallback_logger.error(f"Failed to get log count: {e}")
            return 0
    
    def cleanup_old_logs(self, max_age_seconds: int = 86400) -> int:
        """
        Remove logs older than specified age.
        
        Args:
            max_age_seconds: Maximum age in seconds (default: 24 hours)
            
        Returns:
            Number of logs deleted
        """
        try:
            cutoff_timestamp = int(time.time() * 1000000000) - (max_age_seconds * 1000000000)
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM logs WHERE timestamp < ?
                """, (cutoff_timestamp,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    fallback_logger.debug(f"Cleaned up {deleted_count} old logs")
                
                return deleted_count
        except Exception as e:
            fallback_logger.error(f"Failed to cleanup old logs: {e}")
            return 0
    
    def _row_to_log_entry(self, row: sqlite3.Row) -> LogEntry:
        """Convert database row to LogEntry."""
        attributes = {}
        if row['attributes']:
            try:
                attributes = json.loads(row['attributes'])
            except json.JSONDecodeError:
                fallback_logger.warning(f"Failed to parse attributes for log {row['id']}")
        
        return LogEntry(
            id=row['id'],
            timestamp=row['timestamp'],
            level=row['level'],
            message=row['message'],
            service=row['service'],
            attributes=attributes,
            trace_id=row['trace_id'],
            span_id=row['span_id'],
        )
    
    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
    
    def __del__(self) -> None:
        """Ensure database connection is closed."""
        try:
            self.close()
        except Exception:
            pass  # Ignore errors during cleanup


# Global database instance
_db_instance: Optional[LogDatabase] = None
_db_lock = threading.Lock()


def get_database(db_path: Optional[str] = None) -> LogDatabase:
    """
    Get or create the global database instance.
    
    Args:
        db_path: Path to database file. Only used on first call.
        
    Returns:
        The global database instance
    """
    global _db_instance
    
    with _db_lock:
        if _db_instance is None:
            _db_instance = LogDatabase(db_path)
        return _db_instance


def close_database() -> None:
    """Close the global database instance."""
    global _db_instance
    
    with _db_lock:
        if _db_instance:
            _db_instance.close()
            _db_instance = None