"""Run the unit tests and write candidate-bound evidence (tests/results/unit.json).

    python tests/run_unit.py [--out DIR]

The evidence names the candidate id (pipeline/candidate.py) of this tree, every test with its outcome, and is written
only after the run completes; an existing unit.json is deleted first. Exit 1 on any failure, error or skip (a skipped
test has not verified anything, so it cannot certify a release).
"""
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.candidate import manifest  # noqa: E402


def main():
    a = sys.argv[1:]
    out = Path(a[a.index("--out") + 1]) if "--out" in a else ROOT / "tests" / "results"
    out.mkdir(parents=True, exist_ok=True)
    ev = out / "unit.json"
    if ev.exists():
        ev.unlink()
    cand = manifest(ROOT)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
    outcomes = {}

    class Result(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            outcomes[test.id()] = "PASS"

        def addFailure(self, test, err):
            super().addFailure(test, err)
            outcomes[test.id()] = "FAIL"

        def addError(self, test, err):
            super().addError(test, err)
            outcomes[test.id()] = "ERROR"

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            outcomes[test.id()] = "SKIP: " + reason

    r = unittest.TextTestRunner(resultclass=Result, verbosity=1).run(suite)
    doc = {"completed": True, "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "candidate": {"id": cand["id"], "parts": cand["parts"]},
           "candidate_unchanged": manifest(ROOT)["id"] == cand["id"], "ran": r.testsRun, "failures": len(r.failures),
           "errors": len(r.errors), "skipped": len(r.skipped), "tests": outcomes}
    tmp = out / "unit.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1))
    tmp.replace(ev)
    bad = r.failures or r.errors or r.skipped or not doc["candidate_unchanged"]
    print(f"unit: {r.testsRun} ran, {len(r.failures)} failed, {len(r.errors)} errors, {len(r.skipped)} skipped; candidate {cand['id'][:12]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
