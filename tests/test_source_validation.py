"""Validation must report missing source inventories and continue checking recovered caches."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.check import Report, check_cache, load
from pipeline.core.source import File


class SourceValidationTests(unittest.TestCase):
    def test_missing_inventory_does_not_hide_other_sources(self):
        class Missing:
            id = "missing_grid"
            def files(self):
                raise FileNotFoundError("listing.txt missing")

        class Present:
            id = "recovered"
            def files(self):
                return [File("one.csv", "https://example.org/one.csv"),
                        File("two.csv", "https://example.org/two.csv")]

        report = Report("source")
        with patch("pipeline.sources.registry", return_value={"missing": Missing(), "present": Present()}), \
                patch("pipeline.core.fetch.verify", side_effect=[(True, "ok"), (False, "file missing")]) as verify, \
                contextlib.redirect_stdout(io.StringIO()):
            check_cache(report)
        self.assertEqual(verify.call_count, 2)
        self.assertTrue(report.failed)
        self.assertTrue(any("missing_grid" in msg and "listing.txt" in msg for _, msg in report.lines))
        self.assertTrue(any("recovered: 1/2" in msg for _, msg in report.lines))

    def test_load_uses_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "example.json").write_bytes('{"name":"Göteborg, Tromsø, Århus, ā"}'.encode("utf-8"))
            with patch("pipeline.check.WEB_DATA", path):
                self.assertEqual(load("example")["name"], "Göteborg, Tromsø, Århus, ā")
