"""Run the offline daylight checks through the repository's unittest runner."""

import shutil
import subprocess
import unittest
from pathlib import Path


class SolarTests(unittest.TestCase):
    def test_daylight_calculations(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        script = Path(__file__).with_name("solar_cases.mjs")
        result = subprocess.run([node, "--test", str(script)], capture_output=True,
                                encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
