import os
import tempfile
import unittest

import src.app as dashboard
from src.database.db import DatabaseManager


class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.original_db = dashboard.db
        dashboard.db = DatabaseManager(self.db_path)
        self.client = dashboard.app.test_client()

    def tearDown(self):
        dashboard.db = self.original_db
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_empty_database_shows_placeholders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("No photo yet.", page)
        self.assertIn("No readings yet.", page)
        self.assertNotIn("<img", page)

    def test_reading_without_photo_still_renders(self):
        dashboard.db.insert_reading(25.0, 77.0, 60.0, 1.27)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("77.0°F", page)
        self.assertIn("No photo yet.", page)

    def test_reading_with_photo_links_to_basename(self):
        dashboard.db.insert_reading(25.0, 77.0, 60.0, 1.27)
        dashboard.db.insert_photo("data/photos/10-06-2026.jpg")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('src="/photos/10-06-2026.jpg"', response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
