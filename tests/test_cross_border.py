import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class CrossBorderTests(unittest.TestCase):
    def test_selected_comp53_observations(self):
        data = json.loads((ROOT / "web/data/cross_border.json").read_text(encoding="utf-8"))
        self.assertEqual(data["period"], "2023")
        self.assertEqual(data["region"], "Øresund")
        self.assertEqual({(f["residence"], f["work"]):f["value"] for f in data["flows"]},
                         {("DK","SE"):1391, ("SE","DK"):20038})
        self.assertEqual(len(data["flows"]), 2)
        self.assertEqual(data["source"]["table"], "COMP53")
        self.assertRegex(data["source"]["sha256"], r"^[a-f0-9]{64}$")
