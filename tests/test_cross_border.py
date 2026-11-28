import hashlib
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
        raw = (ROOT / "tests/fixtures/comp53_2023.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), data["source"]["sha256"])
        source = json.loads(raw)
        self.assertEqual(source["size"], [2,1])
        self.assertEqual(source["dimension"]["time"]["category"]["index"], {"2023":0})
        codes = source["dimension"]["reporting country"]["category"]["index"]
        self.assertEqual({f["residence"]:f["value"] for f in data["flows"]},
                         {code:source["value"][index] for code,index in codes.items()})
