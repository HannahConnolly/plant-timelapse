import tempfile
import unittest
from datetime import date
from pathlib import Path

from PIL import Image

from src.services.animation import collect_photos, create_growth_animation


class TestGrowthAnimation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.photos_dir = Path(self.tmp.name)
        for day in range(10, 20):
            Image.new("RGB", (800, 600), (0, day * 10, 0)).save(
                self.photos_dir / f"09-{day}-2026.jpg"
            )
        (self.photos_dir / "demo.jpg").write_bytes(b"not an image")

    def tearDown(self):
        self.tmp.cleanup()

    def test_collect_photos_returns_all_dated_photos_in_order(self):
        photos = collect_photos(self.photos_dir)

        self.assertEqual([d for d, _ in photos], [date(2026, 9, d) for d in range(10, 20)])

    def test_create_growth_animation_writes_looping_gif(self):
        photos = collect_photos(self.photos_dir)
        output = create_growth_animation(photos, self.photos_dir / "out" / "growth.gif")

        with Image.open(output) as gif:
            self.assertEqual(gif.format, "GIF")
            self.assertEqual(gif.n_frames, 10)
            self.assertEqual(gif.width, 640)

    def test_create_growth_animation_skips_unreadable_photos(self):
        photos = [(date(2026, 9, 1), self.photos_dir / "demo.jpg")]

        self.assertIsNone(create_growth_animation(photos, self.photos_dir / "bad.gif"))


if __name__ == "__main__":
    unittest.main()
