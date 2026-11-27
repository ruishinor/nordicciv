"""web/data/version.json: the release version shown on the opening screen, copied from VERSION.

The web app cannot read VERSION (it serves web/ only), so the build writes it here; `pipeline check` fails if the two
ever differ, so the screen never shows a version that is not the repository's.
"""
import re

from ..core.paths import ROOT, WEB_DATA
from ..core.store import write_json

PATTERN = re.compile(r"^\d+\.\d+\.\d+([-.][\w.]+)?$")


def read_version() -> str:
    v = (ROOT / "VERSION").read_text().strip()
    if not PATTERN.match(v):
        raise SystemExit(f"VERSION: not a release version: {v!r}")
    return v


def build():
    write_json(WEB_DATA / "version.json", {"version": read_version()})
