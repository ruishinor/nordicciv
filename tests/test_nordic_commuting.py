import unittest
from pipeline.sources.nordic_commuting import parse_scb, parse_dst, classify

class NordicCommutingTests(unittest.TestCase):
    def test_scb_direction_and_coverage(self):
        ids=["Bostadskommun","Arbetsstallekommun","Kon","ContentsCode","Tid"]
        codes=[["0180","0184"],["0180","0184"],["1+2"],["000000QT"],["2024"]]
        packet={"id":ids,"dimension":{d:{"category":{"index":v}} for d,v in zip(ids,codes)},
                "value":[100,35,28,None]}
        pairs=parse_scb(packet,{"0180","0184"},{"0180","0184"})
        self.assertEqual(classify("SE",pairs),([["SE-0180","SE-0184",35],["SE-0184","SE-0180",28]],
            {"within_municipality":1,"published":2,"missing":1}))
        with self.assertRaises(ValueError):
            parse_scb(packet,{"0180"},{"0180","0184"})

    def test_dst_suppression_and_coverage(self):
        header="BOPKOM;ARBEJDSSTED;KØN;TID;INDHOLD\n"
        text=header+"101;147;M;2024;30\n101;147;K;2024;20\n147;147;M;2024;35\n147;147;K;2024;0\n"
        pairs=parse_dst(text,{"101","147"},{"147"})
        self.assertEqual(pairs,{("101","147"):50,("147","147"):None})
        self.assertEqual(classify("DK",pairs),([["DK-101","DK-147",50]],{"published":1,"missing":1}))
        with self.assertRaises(ValueError):
            parse_dst(text+"101;147;M;2024;30\n",{"101","147"},{"147"})
        with self.assertRaises(ValueError):
            parse_dst(text,{"101","147"},{"101","147"})
