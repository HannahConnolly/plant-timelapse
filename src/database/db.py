import sqlite3
from typing import List, Dict, Any, Optional
import logging
import os
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class DatabaseManager:
    def __init__(self, db_path: str = "data/plant_monitor.db"):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a database connection configured to return rows as dictionaries."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes the database schema if tables do not exist."""
        query = """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature_c REAL,
            temperature_f REAL,
            humidity REAL,
            vpd_kpa REAL,
            image_path TEXT
        );
        """
        try:
            with self.get_connection() as conn:
                conn.execute(query)
                conn.commit()
            logger.info("Database initialized successfully.")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def insert_reading(
        self,
        temp_c: Optional[float],
        temp_f: Optional[float],
        humidity: Optional[float],
        vpd_kpa: Optional[float],
        image_path: Optional[str] = None
    ) -> Optional[int]:
        """Inserts a new sensor reading into the database."""
        query = """
        INSERT INTO readings (temperature_c, temperature_f, humidity, vpd_kpa, image_path)
        VALUES (?, ?, ?, ?, ?)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (temp_c, temp_f, humidity, vpd_kpa, image_path))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Failed to insert reading into database: {e}")
            return None

    def get_recent_readings(self, limit: int = 24) -> List[Dict[str, Any]]:
        """Fetches the most recent sensor logs."""
        query = "SELECT * FROM readings ORDER BY timestamp DESC LIMIT ?"
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch recent readings: {e}")
            return []