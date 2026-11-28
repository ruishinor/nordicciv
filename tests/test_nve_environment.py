import unittest
from pipeline.build.nve_environment import encode_feature
from pipeline.core.geo import Frame


class NveEnvironmentTests(unittest.TestCase):
    def test_polygon(self):
        frame=Frame(0,0)
        row={"properties":{"objectid":1,"flomsoneid":"sample"},
             "geometry":{"type":"Polygon","coordinates":[[[10.0,59.0],[10.01,59.0],[10.01,59.01],[10.0,59.01],[10.0,59.0]]]}}
        f=encode_feature(row,frame)
        self.assertEqual(f["id"],1)
        self.assertEqual(f["rings"][0][0],f["rings"][0][-1])
        self.assertGreaterEqual(len(f["rings"][0]),4)
        row["geometry"]["coordinates"][0]=[[0,0],[1,0],[1,1],[0,0]]
        with self.assertRaises(ValueError):
            encode_feature(row,frame)
