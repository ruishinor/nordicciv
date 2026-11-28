"""Saved places and recent history storage tests."""
import shutil
import subprocess
import unittest
from pathlib import Path

class SavedPlaceTests(unittest.TestCase):
    def test_local_place_lists(self):
        node=shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        result=subprocess.run([node,"--test",str(Path(__file__).with_name("saved_places.mjs"))],
                              capture_output=True,encoding="utf-8",timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
