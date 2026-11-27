from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
RELAY = DATA / "relay"
WEB = ROOT / "web"
WEB_DATA = WEB / "data"
DOCS = ROOT / "docs"
