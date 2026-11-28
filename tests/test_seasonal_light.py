"""Seasonal daylight calculations."""
import shutil
import subprocess
import unittest
from pathlib import Path


class SeasonalLightTests(unittest.TestCase):
    def test_seasonal_light(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        result = subprocess.run([node, "--test", str(Path(__file__).with_name("seasonal_light.mjs"))],
                                capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
