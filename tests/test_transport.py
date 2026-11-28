"""Transport CSV contract and endpoint semantics."""
import unittest

from pipeline.sources.transport import read_cells, SELECTIONS, FERRIES, AIRPORTS


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.selection = {"FROM": ["A"], "TO": ["B", "C"], "Tid": ["2024"]}
        self.header = "FROM;TO;TID;INDHOLD\n"

    def test_units_and_unknown_cells(self):
        self.assertEqual(
            read_cells("\ufeff" + self.header + "A;B;2024;1127\nA;C;2024;0\n", self.selection),
            {("A", "B", "2024"): 1127000, ("A", "C", "2024"): None},
        )
        for missing in ("", "..", "...", ":", "-"):
            with self.subTest(missing=missing):
                self.assertIsNone(read_cells(self.header + "A;B;2024;2\nA;C;2024;" + missing + "\n",
                                             self.selection)[("A", "C", "2024")])

    def test_reject_invalid_counts(self):
        for bad in ("-1", "NaN", "Infinity", "invalid", "0.0001"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                read_cells(self.header + f"A;B;2024;{bad}\nA;C;2024;1\n", self.selection)

    def test_reject_incomplete_duplicate_and_unexpected_cells(self):
        for rows in ("A;B;2024;1\n",
                     "A;B;2024;1\nA;B;2024;2\n",
                     "A;B;2024;1\nA;D;2024;2\n",
                     "A;B;2023;1\nA;C;2024;2\n",
                     "A;B;2024;1;extra\nA;C;2024;2\n",
                     "A;B;2024\nA;C;2024;2\n"):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                read_cells(self.header + rows, self.selection)

    def test_reject_changed_or_duplicate_header(self):
        for header in ("FROM;TO;YEAR;INDHOLD\n", "FROM;TO;TID;INDHOLD;INDHOLD\n"):
            with self.subTest(header=header), self.assertRaises(ValueError):
                read_cells(header + "A;B;2024;1\nA;C;2024;2\n", self.selection)

    def test_selection_is_bounded(self):
        self.assertEqual(len(AIRPORTS), 10)
        self.assertEqual(len(SELECTIONS["FLYV33"]["PÅSTIG1"]) *
                         len(SELECTIONS["FLYV33"]["AFSTIG1"]), 100)
        self.assertEqual(SELECTIONS["FLYV34"]["RET"], ["0003", "0005"])
        self.assertEqual({t: len(routes) for t, routes in FERRIES.items()},
                         {"SKIB31": 3, "SKIB32": 5})
