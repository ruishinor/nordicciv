import csv
import io
import unittest
from collections import Counter

from pipeline.core.paths import WEB_DATA
from pipeline.core.store import read_json
from pipeline.sources.climate import MONTHS, ClimateNormals, parse_station


def sample(*, counts=None, values=None, unit="Deg_C", value_id="2485", header=MONTHS):
    text = io.StringIO()
    rows = [
        ["World Meteorological Organization Climate Normals for 1991-2020"],
        ["Country_Name", "Sweden"], ["Station_Name", "Göteborg A"],
        ["WMO_Number", "Latitude", "Longitude", "Station_Height"],
        ["02485", "59|20|30|N", "18|03|18|E", "43"],
        ["Parameter_Code", "Parameter_Name", "Units"], ["5", "Daily_Mean_Temperature", unit],
        ["WMO_Number", "Parameter_Code", "Calculation_Name", "Calculation_Code", *header],
        [value_id, "5", "Mean", "1", *(values or [-1] * 13)],
    ]
    if counts is not None:
        rows.append(["2485", "5", "NOY", "98", *counts])
    csv.writer(text).writerows(rows)
    return text.getvalue().encode("cp1252")


class TestClimate(unittest.TestCase):
    def test_source_counts_and_missing_values(self):
        raw = sample(counts=[23, 24, "", "30.0", *([30] * 9)], values=[-1, 0, "NA", "-9999.0", *([8] * 9)])
        station = parse_station(raw, "SE", "")
        self.assertEqual(station["name"], "Göteborg A")
        self.assertEqual(station["temperature_c"][:4], [None, 0, None, None])
        self.assertEqual(station["temperature_years"][:4], [23, 24, None, 30])
        self.assertEqual(station["annual_temperature_c"], 8)
        self.assertEqual(station["precipitation_mm"], [None] * 12)
        self.assertEqual(parse_station(sample(), "SE", "")["temperature_years"], [None] * 13)

    def test_rejects_mixed_station_units_and_unexpected_columns(self):
        for raw, error in [(sample(value_id="2484"), "row"), (sample(unit="F"), "units"),
                           (sample(header=MONTHS[::-1]), "row"), (sample(counts=[24.2] * 13), "years")]:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                parse_station(raw, "SE", "")

    def test_published_reference_rows_and_station_identity(self):
        records = read_json(WEB_DATA / "climate.json")["stations"]
        stations = {s["id"]: s for s in records}
        self.assertEqual(Counter(s["country"] for s in records), {"NO": 18, "SE": 18, "DK": 12})
        self.assertEqual(len(stations), len(ClimateNormals().files()))
        oslo = stations["NO-01492"]
        self.assertEqual((oslo["temperature_c"][0], oslo["precipitation_mm"][7]), (-2.3, 102.8))
        self.assertEqual((oslo["annual_temperature_c"], oslo["annual_precipitation_mm"]), (7, 836.3))
        self.assertEqual(oslo["precipitation_years"], [None] * 13)
        stockholm = stations["SE-02485"]
        self.assertEqual((stockholm["temperature_c"][6], stockholm["annual_precipitation_mm"]), (18.7, 546.4))
        self.assertEqual(stockholm["temperature_years"], [30] * 13)
        copenhagen = stations["DK-06186"]
        self.assertEqual(copenhagen["temperature_c"], [None] * 12)
        self.assertEqual((copenhagen["precipitation_mm"][0], copenhagen["annual_precipitation_mm"]), (54.1, 661.9))
        self.assertEqual(stations["NO-01026"]["annual_precipitation_mm"], 1090.6)
