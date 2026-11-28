"""Run the offline WebGL terrain and camera checks with Node's test runner."""

import shutil
import subprocess
import unittest
from pathlib import Path


class WebGLTerrainTests(unittest.TestCase):
    def test_terrain_mesh_and_camera(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        script = Path(__file__).with_name("webgl_terrain.mjs")
        result = subprocess.run([node, "--test", str(script)], capture_output=True,
                                encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
