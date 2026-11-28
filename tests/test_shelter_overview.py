import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class ShelterOverviewTests(unittest.TestCase):
    def test_danish_inventory(self):
        raw=(ROOT/"web/js/ext/shelters/overview-data.js").read_text(encoding="utf-8")
        data=json.loads(raw.removeprefix("export const OVERVIEW = ").strip().removesuffix(";"))
        dk=data["DK"]
        cities=json.loads((ROOT/"web/data/cities.json").read_text(encoding="utf-8"))
        self.assertEqual(set(dk["municipalities"]),{c["id"] for c in cities if c["country"]=="DK"})
        for row in dk["municipalities"].values():
            self.assertEqual(len(row),5)
            self.assertTrue(all(type(v) is int and v>=0 for v in row))
            self.assertEqual(sum(row[:4]),row[4])
        self.assertEqual([sum(v[i] for v in dk["municipalities"].values()) for i in range(5)],[3437760,113018,57442,72527,3680747])
        self.assertEqual(dk["totals"],[3437760,113018,57442,72527,3680747])
        self.assertEqual(dk["municipalities"]["DK-101"],[410601,32450,12080,0,455131])
        self.assertEqual(dk["municipalities"]["DK-825"],[0,0,0,0,0])
        se=data["SE"]
        self.assertTrue(se["map"].startswith("https://www.mcf.se/"))
        if "municipalities" in se:
            self.assertEqual(set(se["municipalities"]),{c["id"] for c in cities if c["country"]=="SE"})
            for row in se["municipalities"].values():
                self.assertEqual(len(row),3)
                self.assertTrue(all(type(v) is int and v>=0 for v in row))
                self.assertLessEqual(row[2],row[0])
            self.assertEqual([sum(v[i] for v in se["municipalities"].values())+se["unassigned"][i] for i in range(3)],se["totals"])
            self.assertTrue(60000<=se["totals"][0]<=70000)
            self.assertTrue(6000000<=se["totals"][1]<=8000000)
            self.assertRegex(se["sha256"],r"^[a-f0-9]{64}$")
            self.assertRegex(se["boundary_sha256"],r"^[a-f0-9]{64}$")
