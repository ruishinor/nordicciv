"""Bounded terrain data and browser-independent mesh contracts."""
import subprocess
import unittest
from pathlib import Path

from pipeline.terrain_pilot import check


class TerrainPilotTests(unittest.TestCase):
    def test_shipped_heights_shared_edges_and_nested_levels(self):
        result = check()
        self.assertEqual(result["tiles"], 240)
        self.assertEqual(result["sharedEdges"], 390)
        self.assertLess(result["bytes"], 4_000_000)

    def test_loader_camera_and_mesh_contracts(self):
        result = subprocess.run(["node", "--test", str(Path(__file__).with_name("elevation_tiles.mjs"))],
                                capture_output=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
