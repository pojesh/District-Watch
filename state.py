"""
State persistence using SQLite
"""

import sqlite3
import logging
import json
from typing import Optional, Set
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class StateManager:
    """Manage persistent state in SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def initialize(self) -> None:
        """Initialize database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Database init failed: {e}")
            raise
    
    def _create_tables(self) -> None:
        """Create schema"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN,
                theaters_found INTEGER,
                error TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                theaters TEXT,
                message TEXT
            )
        """)
        
        self.conn.commit()
    
    def close(self) -> None:
        """Close database"""
        if self.conn:
            self.conn.close()
            logger.info("Database closed")
    
    def set_value(self, key: str, value: str) -> None:
        """Set state value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Set value error: {e}")
    
    def get_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get state value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM state WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default
        except Exception as e:
            logger.error(f"Get value error: {e}")
            return default
    
    def record_check(self, success: bool, theaters_found: int, error: Optional[str] = None) -> None:
        """Record check attempt"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO check_history (success, theaters_found, error)
                VALUES (?, ?, ?)
            """, (success, theaters_found, error))
            self.conn.commit()
            
            # Increment counter
            count = int(self.get_value("check_count", "0"))
            self.set_value("check_count", str(count + 1))
        except Exception as e:
            logger.error(f"Record check error: {e}")
    
    def record_alert(self, theaters: list, message: str) -> None:
        """Record alert sent"""
        try:
            cursor = self.conn.cursor()
            theater_names = json.dumps([t.name for t in theaters])
            cursor.execute("""
                INSERT INTO alert_history (theaters, message)
                VALUES (?, ?)
            """, (theater_names, message))
            self.conn.commit()
            
            count = int(self.get_value("alert_count", "0"))
            self.set_value("alert_count", str(count + 1))
        except Exception as e:
            logger.error(f"Record alert error: {e}")
    
    def get_check_count(self) -> int:
        """Get total checks"""
        return int(self.get_value("check_count", "0"))
    
    def get_alert_count(self) -> int:
        """Get total alerts"""
        return int(self.get_value("alert_count", "0"))
    
    def get_recent_checks(self, limit: int = 10) -> list:
        """Get recent checks"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM check_history
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except:
            return []
    
    def get_recent_alerts(self, limit: int = 10) -> list:
        """Get recent alerts"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM alert_history
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except:
            return []
    
    def cleanup_old_records(self, days: int = 30) -> None:
        """Remove old history"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM check_history
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days,))
            cursor.execute("""
                DELETE FROM alert_history
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days,))
            self.conn.commit()
            logger.info(f"Cleaned up records older than {days} days")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
