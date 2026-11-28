"""Offline tests for close zoom and illustration scaling."""
import shutil
import subprocess
import unittest
from pathlib import Path


class CloseZoomTests(unittest.TestCase):
    def test_camera_and_pattern_scale(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        result = subprocess.run([node, "--test", str(Path(__file__).with_name("close_zoom.mjs"))],
                                capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
