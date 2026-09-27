# src/tests/test_camera.py

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from src.sensors import camera


def _frame(brightness: int):
    return np.full((48, 64, 3), brightness, dtype=np.uint8)


class FakeCamera:
    """Stands in for cv2.VideoCapture, returning a scripted series of frames."""

    def __init__(self, brightnesses):
        self.brightnesses = list(brightnesses)
        self.reads = 0
        self.released = False

    def read(self):
        if self.reads >= len(self.brightnesses):
            return False, None
        frame = _frame(self.brightnesses[self.reads])
        self.reads += 1
        return True, frame

    def release(self):
        self.released = True


class TestCamera(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def _capture(self, fake):
        with patch("src.sensors.camera.cv2.VideoCapture", return_value=fake):
            return camera.capture_photo_and_save()

    def test_waits_for_exposure_to_settle(self):
        # Dark stale frames, then a ramp that levels off at 130
        fake = FakeCamera([37, 37] + list(range(40, 130, 3)) + [130] * 50)
        path = self._capture(fake)

        self.assertTrue(os.path.exists(path))
        self.assertGreater(fake.reads, 32)
        self.assertLess(fake.reads, camera.MAX_WARMUP_FRAMES)
        self.assertTrue(fake.released)

    def test_rejects_blown_out_frame(self):
        fake = FakeCamera([255] * camera.MAX_WARMUP_FRAMES)
        with self.assertRaisesRegex(RuntimeError, "exposure"):
            self._capture(fake)

        self.assertFalse(os.listdir("data/photos"))
        self.assertTrue(fake.released)

    def test_rejects_black_frame(self):
        fake = FakeCamera([0] * camera.MAX_WARMUP_FRAMES)
        with self.assertRaisesRegex(RuntimeError, "exposure"):
            self._capture(fake)

    def test_raises_when_camera_returns_nothing(self):
        fake = FakeCamera([])
        with self.assertRaisesRegex(RuntimeError, "Could not read frame"):
            self._capture(fake)
        self.assertTrue(fake.released)


if __name__ == "__main__":
    unittest.main()
