import unittest
from pipeline.sources.commuting import parse_batch, observation


class CommutingTests(unittest.TestCase):
    def test_observation(self):
        for v in (None, "..", ":"):
            self.assertIsNone(observation(v))
        self.assertEqual(observation(25),25)
        for v in (-1,1.5,float("inf")):
            with self.assertRaises(ValueError):
                observation(v)

    def test_matrix(self):
        ids=["Bokommuen","ArbstedKomm","ContentsCode","Tid"]
        codes=[["0301","3205"],["0301","3205"],["Sysselsatte"],["2024"]]
        packet={"id":ids,"dimension":{d:{"category":{"index":v}} for d,v in zip(ids,codes)},
                "value":[100,25,24,None]}
        flows,audit=parse_batch(packet,{"0301","3205"},{"0301","3205"})
        self.assertEqual(flows,[["NO-0301","NO-3205",25]])
        self.assertEqual(audit,{"within_municipality":1,"published":1,"below_threshold":1,"missing":1})
        with self.assertRaises(ValueError):
            parse_batch(packet,{"0301"},{"0301","3205"})
