import sqlite3
from typing import List, Dict, Any, Optional
import logging

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
        """Initializes tables and summary view if they do not exist."""
        readings_table = """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature_c REAL,
            temperature_f REAL,
            humidity REAL,
            vpd_kpa REAL
        );
        """
        
        photos_table = """
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT NOT NULL
        );
        """

        # Computed View for daily summaries & daily photo path
        daily_summary_view = """
        CREATE VIEW IF NOT EXISTS daily_timelapse_summary AS
        SELECT 
            DATE(r.timestamp) AS log_date,
            ROUND(AVG(r.temperature_c), 2) AS avg_temp_c,
            ROUND(AVG(r.temperature_f), 2) AS avg_temp_f,
            ROUND(AVG(r.humidity), 2) AS avg_humidity,
            ROUND(AVG(r.vpd_kpa), 2) AS avg_vpd_kpa,
            p.file_path AS photo_path
        FROM readings r
        LEFT JOIN photos p ON DATE(r.timestamp) = DATE(p.timestamp)
        GROUP BY DATE(r.timestamp);
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(readings_table)
                cursor.execute(photos_table)
                cursor.execute(daily_summary_view)
                conn.commit()
            logger.info("Database and views initialized successfully.")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def insert_reading(
        self,
        temp_c: Optional[float],
        temp_f: Optional[float],
        humidity: Optional[float],
        vpd_kpa: Optional[float],
    ) -> Optional[int]:
        """Inserts a new sensor reading into the database."""
        query = """
        INSERT INTO readings (temperature_c, temperature_f, humidity, vpd_kpa)
        VALUES (?, ?, ?, ?)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (temp_c, temp_f, humidity, vpd_kpa))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Failed to insert reading into database: {e}")
            return None

    def insert_photo(self, file_path: str) -> Optional[int]:
        """Inserts a daily photo file path with timestamp."""
        query = "INSERT INTO photos (file_path) VALUES (?)"
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (file_path,))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Failed to insert photo path into database: {e}")
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

    def get_daily_timelapse_summary(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetches calculated daily averages alongside matching photo paths via the VIEW."""
        query = "SELECT * FROM daily_timelapse_summary ORDER BY log_date DESC LIMIT ?"
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch daily summary: {e}")
            return []