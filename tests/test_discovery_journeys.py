"""Check discovery journey rules and public link construction."""
import shutil
import subprocess
import unittest
from pathlib import Path


class DiscoveryJourneyTests(unittest.TestCase):
    def test_discovery_journeys(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        result = subprocess.run([node, "--test", str(Path(__file__).with_name("discovery_journeys.mjs"))],
                                capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
