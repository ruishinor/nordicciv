"""CORINE class transitions: no invented observations and no missing-as-zero."""
import unittest
import numpy as np
from pipeline.build.land_history import aggregate


class LandHistoryTests(unittest.TestCase):
    def test_paired_class_transitions(self):
        a = aggregate(np.array([0,0,0,0,1,1,1,2,-1]), [23, 12, 23, 24, 11, 0, 44, np.nan, 12],
                      [12, 23, 24, 0, 12, 23, 11, 23, 23], 3)
        self.assertEqual(a["paired"].tolist(), [3,2,0])
        self.assertEqual(a["forest_change_gain"].tolist(), [1,0,0])
        self.assertEqual(a["forest_change_loss"].tolist(), [1,0,0])
        self.assertEqual(a["agriculture_change_gain"].tolist(), [1,1,0])
        self.assertEqual(a["agriculture_change_loss"].tolist(), [1,0,0])
        self.assertEqual(a["urban_gain"].tolist(), [0,1,0])
