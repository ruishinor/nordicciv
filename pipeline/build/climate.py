"""Publish the selected WMO station normals and their individual source hashes."""
from ..core.paths import INTERIM, WEB_DATA
from ..core.store import read_json, write_json
from ..sources.climate import ClimateNormals
from .catalog import update_source


def build():
    climate = read_json(INTERIM / "climate_normals.json")
    write_json(WEB_DATA / "climate.json", climate)
    update_source(ClimateNormals())
