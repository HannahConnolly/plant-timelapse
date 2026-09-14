import sqlite3
import tempfile
import unittest
import os
import datetime
from src.database.db import DatabaseManager

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database
        self.db_fd, self.db_path = tempfile.mkstemp()
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP TABLE IF EXISTS readings")
        conn.close()
        print("Temporary SQLite database created and existing 'readings' table dropped.")

    def tearDown(self):
        # Close and remove the temporary database
        os.close(self.db_fd)
        os.unlink(self.db_path)
        print("Temporary SQLite database closed and removed.")

    def test_init_db(self):
        # Initialize the database
        db_manager = DatabaseManager(self.db_path)
        db_manager._init_db()
        print("Database initialized with 'readings' table.")

        # Connect to the database and check if the table exists
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='readings'")
        table_exists = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(table_exists, "Table 'readings' should exist")

    def test_insert_and_retrieve_data(self):
        # Initialize the database
        db_manager = DatabaseManager(self.db_path)
        db_manager._init_db()
        print("Database initialized with 'readings' table.")

        # Connect to the database and insert data
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO readings (temperature_c, temperature_f, humidity, vpd_kpa)
        VALUES (25.0, 77.0, 50.0, 10.0)
        """)
        conn.commit()
        conn.close()
        print("Data inserted into 'readings' table.")

        # Connect to the database and retrieve data
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM readings")
        data = cursor.fetchone()
        print(f"Data retrieved from 'readings' table: {data}")
        conn.close()

        self.assertIsNotNone(data, "Data should be inserted and retrieved successfully")
        self.assertEqual(data[2:], (25.0, 77.0, 50.0, 10.0))

    def test_photo_path_is_normalized_for_file_server(self):
        from src.app import normalize_photo_path

        self.assertEqual(normalize_photo_path("data/photos/demo.jpg"), "demo.jpg")
        self.assertEqual(normalize_photo_path("/tmp/project/data/photos/demo.jpg"), "demo.jpg")
        self.assertEqual(normalize_photo_path("demo.jpg"), "demo.jpg")

if __name__ == '__main__':
    unittest.main()