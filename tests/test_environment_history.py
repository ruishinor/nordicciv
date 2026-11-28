"""Check selected environmental observations and scope rules."""
import shutil
import subprocess
import unittest
from pathlib import Path


class EnvironmentHistoryTests(unittest.TestCase):
    def test_environment_history(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        result = subprocess.run([node, "--test", str(Path(__file__).with_name("environment_history.mjs"))],
                                capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
